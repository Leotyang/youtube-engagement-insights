"""Pull every video for the channels in config.CHANNEL_IDS and save to data/raw.

Run repeatedly (e.g. weekly). Two outputs:
  videos.csv                 one row per video, latest metadata (overwritten on rerun)
  engagement_snapshots.csv   one row per video per run, appended -> engagement over time

Usage:  python src/ingest.py
"""

import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CHANNEL_IDS, MAX_VIDEOS_PER_CHANNEL, VIDEOS_PATH, SNAPSHOTS_PATH, YOUTUBE_API_KEY
from youtube_api import get_channel_info, get_video_ids, get_video_details

if not YOUTUBE_API_KEY:
    sys.exit("YOUTUBE_API_KEY is empty. Copy .env.example to .env and fill it in.")
if not CHANNEL_IDS:
    sys.exit("CHANNEL_IDS in src/config.py is empty. Add channel IDs first.")

pulled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

all_videos = []
for channel in get_channel_info(CHANNEL_IDS):
    video_ids = get_video_ids(channel["uploads_playlist_id"], max_videos=MAX_VIDEOS_PER_CHANNEL)
    print(f"{channel['channel_title']}: {len(video_ids)} videos")
    all_videos.extend(get_video_details(video_ids))

df_videos = pd.DataFrame(all_videos)
df_videos["pulled_at"] = pulled_at

# Master list: keep the latest row per video across runs.
if os.path.exists(VIDEOS_PATH):
    df_videos = pd.concat([pd.read_csv(VIDEOS_PATH), df_videos])
df_videos = df_videos.drop_duplicates("video_id", keep="last")
df_videos.to_csv(VIDEOS_PATH, index=False)

df_snapshot = df_videos[df_videos["pulled_at"] == pulled_at][
    ["video_id", "channel_id", "pulled_at", "view_count", "like_count", "comment_count"]
]
df_snapshot.to_csv(SNAPSHOTS_PATH, mode="a", index=False, header=not os.path.exists(SNAPSHOTS_PATH))

print(f"Saved {len(df_videos)} videos to {VIDEOS_PATH}; appended {len(df_snapshot)} snapshot rows.")
