"""Pull videos + engagement for every channel in config.CHANNEL_URLS and save CSVs.

Run repeatedly (e.g. weekly). Outputs in config.DATA_DIR:
  channels.csv               one row per channel, all API fields (overwritten)
  videos.csv                 one row per video, all API fields, latest pull wins (deduped)
  engagement_snapshots.csv   one row per video per run, appended -> engagement over time

Usage:  python src/ingest.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CHANNEL_URLS, LOOKBACK_DAYS, DATA_DIR, CHANNELS_PATH, VIDEOS_PATH, SNAPSHOTS_PATH
from youtube_api import get_client, get_channels, get_video_ids, get_videos

if not CHANNEL_URLS:
    sys.exit("CHANNEL_URLS in src/config.py is empty. Add channel URLs first.")

youtube = get_client()
now = datetime.now(timezone.utc)
pulled_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
published_after = pd.Timestamp(now - timedelta(days=LOOKBACK_DAYS))
os.makedirs(DATA_DIR, exist_ok=True)

df_channels = get_channels(youtube, CHANNEL_URLS)
df_channels["pulled_at"] = pulled_at
df_channels.to_csv(CHANNELS_PATH, index=False)

df_video_batches = []
for _, channel in df_channels.iterrows():
    video_ids = get_video_ids(youtube, channel["contentDetails.relatedPlaylists.uploads"], published_after)
    print(f"{channel['snippet.title']}: {len(video_ids)} videos since {published_after.date()}")
    df_video_batches.append(get_videos(youtube, video_ids))

df_videos = pd.concat(df_video_batches, ignore_index=True)
df_videos["pulled_at"] = pulled_at

if os.path.exists(VIDEOS_PATH):
    df_videos = pd.concat([pd.read_csv(VIDEOS_PATH), df_videos], ignore_index=True)
df_videos = df_videos.drop_duplicates("id", keep="last")
df_videos.to_csv(VIDEOS_PATH, index=False)

df_snapshot = df_videos[df_videos["pulled_at"] == pulled_at][
    ["id", "snippet.channelId", "pulled_at", "statistics.viewCount", "statistics.likeCount", "statistics.commentCount"]
]
df_snapshot.to_csv(SNAPSHOTS_PATH, mode="a", index=False, header=not os.path.exists(SNAPSHOTS_PATH))

print(f"Saved {len(df_channels)} channels, {len(df_videos)} videos to {DATA_DIR}; appended {len(df_snapshot)} snapshot rows.")
