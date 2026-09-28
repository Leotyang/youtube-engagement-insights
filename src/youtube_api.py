"""Thin wrappers over the YouTube Data API v3 (google-api-python-client).

Quota (units per call, 10,000/day default):
  channels.list 1 | playlistItems.list 1 (50 videos/page) | videos.list 1 (50 videos/call)
One channel with 200 videos costs roughly 1 + 4 + 4 = 9 units.
"""

import pandas as pd
from googleapiclient.discovery import build

from src import config


def get_client():
    if not config.YOUTUBE_API_KEY:
        return None
    return build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)


def channel_id_from_handle(youtube, handle):
    """'@mkbhd' -> 'UC...' channel ID."""
    resp = youtube.channels().list(part="id", forHandle=handle.lstrip("@")).execute()
    return resp["items"][0]["id"]


def get_channel_info(youtube, channel_ids):
    """One dict per channel: id, title, uploads playlist, subscriber/video counts."""
    channels = []
    for start in range(0, len(channel_ids), 50):
        resp = youtube.channels().list(
            part="snippet,contentDetails,statistics",
            id=",".join(channel_ids[start:start + 50]),
        ).execute()
        for item in resp.get("items", []):
            channels.append({
                "channel_id": item["id"],
                "channel_title": item["snippet"]["title"],
                "uploads_playlist_id": item["contentDetails"]["relatedPlaylists"]["uploads"],
                "subscriber_count": int(item["statistics"].get("subscriberCount", 0)),
                "channel_video_count": int(item["statistics"].get("videoCount", 0)),
            })
    return channels


def get_video_ids(youtube, playlist_id, max_videos=None):
    """All video IDs in a playlist (use the channel's uploads playlist), newest first."""
    video_ids = []
    page_token = None
    while True:
        resp = youtube.playlistItems().list(
            part="contentDetails", playlistId=playlist_id, maxResults=50, pageToken=page_token
        ).execute()
        video_ids.extend(item["contentDetails"]["videoId"] for item in resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token or (max_videos and len(video_ids) >= max_videos):
            break
    return video_ids[:max_videos] if max_videos else video_ids


def get_video_details(youtube, video_ids):
    """Metadata + engagement counts for a list of video IDs (batched 50 per call)."""
    videos = []
    for start in range(0, len(video_ids), 50):
        resp = youtube.videos().list(
            part="snippet,statistics,contentDetails", id=",".join(video_ids[start:start + 50])
        ).execute()
        for item in resp.get("items", []):
            snippet = item["snippet"]
            stats = item["statistics"]
            details = item["contentDetails"]
            videos.append({
                "video_id": item["id"],
                "channel_id": snippet["channelId"],
                "channel_title": snippet["channelTitle"],
                "title": snippet["title"],
                "description": snippet.get("description", ""),
                "tags": "|".join(snippet.get("tags", [])),
                "category_id": snippet.get("categoryId"),
                "published_at": snippet["publishedAt"],
                # pandas parses ISO-8601 durations like PT1H2M3S directly; no isodate needed.
                "duration_seconds": pd.Timedelta(details["duration"]).total_seconds(),
                "definition": details.get("definition"),
                "caption_available": details.get("caption"),
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
            })
    return videos
