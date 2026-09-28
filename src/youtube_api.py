"""Thin wrappers over the YouTube Data API v3 (REST, via requests).

Quota reference (units per call, default daily budget 10,000):
  channels.list      1
  playlistItems.list 1  (50 videos per page)
  videos.list        1  (50 videos per call)
So one channel with 200 videos costs roughly 1 + 4 + 4 = 9 units.
"""

import requests
from config import YOUTUBE_API_KEY

BASE_URL = "https://www.googleapis.com/youtube/v3"


def _get(endpoint, params):
    params["key"] = YOUTUBE_API_KEY
    response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"{endpoint} failed ({response.status_code}): {response.text[:300]}")
    return response.json()


def channel_id_from_handle(handle):
    """'@mkbhd' -> 'UC...' channel ID."""
    data = _get("channels", {"part": "id", "forHandle": handle.lstrip("@")})
    return data["items"][0]["id"]


def get_channel_info(channel_ids):
    """Returns one dict per channel: id, title, uploads_playlist_id, subscriber/video counts."""
    channels = []
    for start in range(0, len(channel_ids), 50):
        data = _get("channels", {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(channel_ids[start:start + 50]),
        })
        for item in data.get("items", []):
            channels.append({
                "channel_id": item["id"],
                "channel_title": item["snippet"]["title"],
                "uploads_playlist_id": item["contentDetails"]["relatedPlaylists"]["uploads"],
                "subscriber_count": item["statistics"].get("subscriberCount"),
                "channel_video_count": item["statistics"].get("videoCount"),
            })
    return channels


def get_video_ids(playlist_id, max_videos=None):
    """All video IDs in a playlist (use a channel's uploads playlist), newest first."""
    video_ids = []
    page_token = None
    while True:
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        data = _get("playlistItems", params)
        video_ids.extend(item["contentDetails"]["videoId"] for item in data.get("items", []))
        page_token = data.get("nextPageToken")
        if not page_token or (max_videos and len(video_ids) >= max_videos):
            break
    return video_ids[:max_videos] if max_videos else video_ids


def get_video_details(video_ids):
    """Metadata + engagement counts for a list of video IDs (batched 50 per call)."""
    videos = []
    for start in range(0, len(video_ids), 50):
        data = _get("videos", {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(video_ids[start:start + 50]),
        })
        for item in data.get("items", []):
            snippet = item["snippet"]
            stats = item["statistics"]
            videos.append({
                "video_id": item["id"],
                "channel_id": snippet["channelId"],
                "channel_title": snippet["channelTitle"],
                "title": snippet["title"],
                "description": snippet.get("description", ""),
                "tags": "|".join(snippet.get("tags", [])),
                "category_id": snippet.get("categoryId"),
                "published_at": snippet["publishedAt"],
                "duration_iso": item["contentDetails"]["duration"],
                "definition": item["contentDetails"].get("definition"),
                "caption_available": item["contentDetails"].get("caption"),
                "view_count": stats.get("viewCount"),
                "like_count": stats.get("likeCount"),
                "comment_count": stats.get("commentCount"),
            })
    return videos
