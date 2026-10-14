"""Pull videos + engagement for every creator in the team Google Sheet and load BigQuery.

BigQuery tables (project/dataset set in config.py):
  channels               one row per channel, all API fields (replaced each run)
  videos                 one row per video, all API fields, latest pull wins (upsert on id)
  engagement_snapshots   one row per video per run, appended -> engagement over time

Usage:
  python src/ingest.py --env local    also writes CSV backups to config.DATA_DIR (default)
  python src/ingest.py --env github   BigQuery only (used by the GitHub Action)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bigquery_io import get_client as get_bq_client, write_table
from config import LOOKBACK_DAYS, DATA_DIR, CHANNELS_PATH, VIDEOS_PATH, SNAPSHOTS_PATH
from sheet import get_creators
from youtube_api import get_client, get_channels, get_video_ids, get_videos

parser = argparse.ArgumentParser()
parser.add_argument("--env", choices=["local", "github"], default="local")
args = parser.parse_args()

df_creators = get_creators()
if df_creators.empty:
    sys.exit("No usable channel URLs in the Google Sheet.")

youtube = get_client()
now = datetime.now(timezone.utc)
pulled_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
published_after = pd.Timestamp(now - timedelta(days=LOOKBACK_DAYS))

df_channels = get_channels(youtube, df_creators["channel_url"].tolist())
df_channels = df_channels.merge(df_creators, on="channel_url", how="left")
df_channels["pulled_at"] = pulled_at

df_video_batches = []
for _, channel in df_channels.iterrows():
    video_ids = get_video_ids(youtube, channel["contentDetails.relatedPlaylists.uploads"], published_after)
    print(f"{channel['snippet.title']}: {len(video_ids)} videos since {published_after.date()}")
    df_video_batches.append(get_videos(youtube, video_ids))

df_videos = pd.concat(df_video_batches, ignore_index=True)
df_videos["pulled_at"] = pulled_at
df_snapshot = df_videos[
    ["id", "snippet.channelId", "pulled_at", "statistics.viewCount", "statistics.likeCount", "statistics.commentCount"]
]

bq_client = get_bq_client()
write_table(bq_client, "channels", df_channels, "replace")
write_table(bq_client, "videos", df_videos, "upsert")
write_table(bq_client, "engagement_snapshots", df_snapshot, "append")

if args.env == "local":
    os.makedirs(DATA_DIR, exist_ok=True)
    df_channels.to_csv(CHANNELS_PATH, index=False)
    df_videos_csv = df_videos
    if os.path.exists(VIDEOS_PATH):
        df_videos_csv = pd.concat([pd.read_csv(VIDEOS_PATH), df_videos], ignore_index=True)
    df_videos_csv.drop_duplicates("id", keep="last").to_csv(VIDEOS_PATH, index=False)
    df_snapshot.to_csv(SNAPSHOTS_PATH, mode="a", index=False, header=not os.path.exists(SNAPSHOTS_PATH))
    print(f"CSV backups written to {DATA_DIR}")

print(f"Done: {len(df_channels)} channels, {len(df_videos)} videos, {len(df_snapshot)} snapshot rows.")
