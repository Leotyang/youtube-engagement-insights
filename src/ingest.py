"""Pull every video for config.CHANNEL_IDS and save to data/raw.

Run repeatedly (e.g. weekly). Two outputs:
  videos.csv                 one row per video, latest metadata (deduped on rerun)
  engagement_snapshots.csv   one row per video per run, appended -> engagement over time

Usage:  python -m src.ingest        (from the repo root)
Colab:  from src import ingest; df_videos = ingest.load_or_ingest()
"""

import os
from datetime import datetime, timezone

import pandas as pd

from src import config
from src.youtube_api import get_client, get_channel_info, get_video_ids, get_video_details


def ingest_channels(youtube, channel_ids):
    pulled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    all_videos = []
    for channel in get_channel_info(youtube, channel_ids):
        video_ids = get_video_ids(youtube, channel["uploads_playlist_id"], max_videos=config.MAX_VIDEOS_PER_CHANNEL)
        print(f"{channel['channel_title']}: {len(video_ids)} videos")
        all_videos.extend(get_video_details(youtube, video_ids))

    df_videos = pd.DataFrame(all_videos)
    df_videos["pulled_at"] = pulled_at

    if os.path.exists(config.VIDEOS_PATH):
        df_videos = pd.concat([pd.read_csv(config.VIDEOS_PATH), df_videos])
    df_videos = df_videos.drop_duplicates("video_id", keep="last")
    df_videos.to_csv(config.VIDEOS_PATH, index=False)

    df_snapshot = df_videos[df_videos["pulled_at"] == pulled_at][
        ["video_id", "channel_id", "pulled_at", "view_count", "like_count", "comment_count"]
    ]
    df_snapshot.to_csv(config.SNAPSHOTS_PATH, mode="a", index=False, header=not os.path.exists(config.SNAPSHOTS_PATH))

    print(f"Saved {len(df_videos)} videos to {config.VIDEOS_PATH}; appended {len(df_snapshot)} snapshot rows.")
    return df_videos


def load_or_ingest(channel_ids=None):
    """Pull fresh data if a key and channels are set; otherwise load the last saved pull."""
    channel_ids = config.CHANNEL_IDS if channel_ids is None else channel_ids
    youtube = get_client()

    if channel_ids and youtube:
        return ingest_channels(youtube, channel_ids)

    if os.path.exists(config.VIDEOS_PATH):
        df_videos = pd.read_csv(config.VIDEOS_PATH)
        print(f"Loaded {len(df_videos)} previously ingested videos from {config.VIDEOS_PATH}")
        return df_videos

    print("Set YOUTUBE_API_KEY (.env or Colab secret) and CHANNEL_IDS in src/config.py, then re-run.")
    return pd.DataFrame()


if __name__ == "__main__":
    load_or_ingest()
