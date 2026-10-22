"""Wrappers over the YouTube Data API v3 (google-api-python-client).

Quota (units per call, 10,000/day default):
  channels.list 1 | playlistItems.list 1 (50 videos/page) | videos.list 1 (50 videos/call)
One channel with 300 videos in the window costs roughly 1 + 6 + 6 = 13 units.

Every field the API returns (for the parts an API key can access) is kept and flattened
to dotted column names, e.g. snippet.title, statistics.viewCount, contentDetails.duration.
"""

import os
import sys
from urllib.parse import urlparse

import pandas as pd
from googleapiclient.discovery import build

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import YOUTUBE_API_KEY

# auditDetails / contentOwnerDetails (channels) and fileDetails / processingDetails /
# suggestions (videos) need owner OAuth, so they're excluded. localizations and player
# are excluded as noise (per-language title copies, embed HTML).
CHANNEL_PARTS = "id,snippet,contentDetails,statistics,status,topicDetails,brandingSettings"
VIDEO_PARTS = "id,snippet,contentDetails,statistics,status,topicDetails,liveStreamingDetails,recordingDetails,paidProductPlacementDetails"


def get_client():
    if not YOUTUBE_API_KEY:
        sys.exit("YOUTUBE_API_KEY is empty. Set it in .env (local runs) or as the YOUTUBE_API_KEY repository secret (GitHub Actions).")
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def flatten(items):
    """API items (nested dicts) -> flat DataFrame; list-valued fields joined with '|'."""
    df_flat = pd.json_normalize(items)
    for column in df_flat.columns:
        if df_flat[column].apply(lambda value: isinstance(value, list)).any():
            df_flat[column] = df_flat[column].apply(lambda value: "|".join(map(str, value)) if isinstance(value, list) else value)
    return df_flat


def channel_lookup_params(url):
    """Map a channel URL to the channels.list filter the API supports for it."""
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    if path_parts[0].startswith("@"):
        return {"forHandle": path_parts[0]}
    if path_parts[0] == "channel":
        return {"id": path_parts[1]}
    if path_parts[0] == "user":
        return {"forUsername": path_parts[1]}
    sys.exit(f"Cannot resolve {url}: legacy /c/ URLs aren't supported by the API. Use the channel's @handle URL.")


def get_channels(youtube, channel_urls):
    """One flattened row per channel URL, with the source URL kept as channel_url."""
    items = []
    for url in channel_urls:
        resp = youtube.channels().list(part=CHANNEL_PARTS, **channel_lookup_params(url)).execute()
        if not resp.get("items"):
            print(f"No channel found for {url}, skipping")
            continue
        items.append({"channel_url": url, **resp["items"][0]})
    return flatten(items)


def get_video_ids(youtube, playlist_id, published_after, published_before, known_ids):
    """IDs of videos in a playlist (use the channel's uploads playlist) published between
    `published_after` and `published_before` (tz-aware datetimes) that aren't in `known_ids`.
    Pages newest-first and stops at the cutoff or at the first already-known video."""
    video_ids = []
    page_token = None
    while True:
        resp = youtube.playlistItems().list(
            part="contentDetails", playlistId=playlist_id, maxResults=50, pageToken=page_token
        ).execute()
        for item in resp.get("items", []):
            video_id = item["contentDetails"]["videoId"]
            published = pd.Timestamp(item["contentDetails"]["videoPublishedAt"])
            if video_id in known_ids or published < published_after:
                return video_ids
            if published <= published_before:
                video_ids.append(video_id)
        page_token = resp.get("nextPageToken")
        if not page_token:
            return video_ids


def get_videos(youtube, video_ids):
    """Flattened metadata + engagement for a list of video IDs (50 per call)."""
    items = []
    for start in range(0, len(video_ids), 50):
        resp = youtube.videos().list(part=VIDEO_PARTS, id=",".join(video_ids[start:start + 50])).execute()
        items.extend(resp.get("items", []))
    df_videos = flatten(items)
    if "contentDetails.duration" in df_videos:
        # pandas parses ISO-8601 durations like PT1H2M3S directly.
        df_videos["duration_seconds"] = df_videos["contentDetails.duration"].apply(lambda value: pd.Timedelta(value).total_seconds())
    for column in ["statistics.viewCount", "statistics.likeCount", "statistics.commentCount", "statistics.favoriteCount"]:
        if column in df_videos:
            df_videos[column] = pd.to_numeric(df_videos[column], errors="coerce")
    return df_videos
