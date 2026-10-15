"""Pull videos + engagement for every creator in the team Google Sheet and load BigQuery.

Each video is scraped once: only videos older than MIN_VIDEO_AGE_DAYS that aren't already
in BigQuery are fetched, and their engagement is frozen at that pull. Both tables are one
row per video and join on `id`.

BigQuery tables (project/dataset set in config.py):
  channels               one row per channel, all API fields (replaced each run)
  videos                 one row per video, all API fields + age_days_at_pull
  engagement_snapshots   one row per video: id, channel, pulled_at, counts, age_days_at_pull

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
from bigquery_io import get_client as get_bq_client, get_existing_ids, write_table
from config import LOOKBACK_DAYS, MIN_VIDEO_AGE_DAYS, DATA_DIR, CHANNELS_PATH, VIDEOS_PATH, SNAPSHOTS_PATH
from sheet import get_creators
from youtube_api import get_client, get_channels, get_video_ids, get_videos

parser = argparse.ArgumentParser()
parser.add_argument("--env", choices=["local", "github"], default="local")
args = parser.parse_args()

df_creators = get_creators()
if df_creators.empty:
    sys.exit("No usable channel URLs in the Google Sheet.")

print(f"About to query the YouTube API for {len(df_creators)} channels")
youtube = get_client()
now = datetime.now(timezone.utc)
pulled_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
published_after = pd.Timestamp(now - timedelta(days=LOOKBACK_DAYS))
published_before = pd.Timestamp(now - timedelta(days=MIN_VIDEO_AGE_DAYS))
bq_client = get_bq_client()
known_ids = get_existing_ids(bq_client, "videos")
print(f"{len(known_ids)} videos already in BigQuery; fetching only new videos aged {MIN_VIDEO_AGE_DAYS}+ days")

df_channels = get_channels(youtube, df_creators["channel_url"].tolist())
df_channels = df_channels.merge(df_creators, on="channel_url", how="left")
df_channels["pulled_at"] = pulled_at

df_video_batches = []
for _, channel in df_channels.iterrows():
    video_ids = get_video_ids(
        youtube, channel["contentDetails.relatedPlaylists.uploads"], published_after, published_before, known_ids
    )
    print(f"{channel['snippet.title']}: {len(video_ids)} new videos")
    df_video_batches.append(get_videos(youtube, video_ids))

write_table(bq_client, "channels", df_channels, "replace")
if args.env == "local":
    os.makedirs(DATA_DIR, exist_ok=True)
    df_channels.to_csv(CHANNELS_PATH, index=False)

df_videos = pd.concat(df_video_batches, ignore_index=True)
if df_videos.empty:
    print("No new videos to add; channels refreshed.")
    sys.exit(0)
df_videos["pulled_at"] = pulled_at
df_videos["age_days_at_pull"] = (now - pd.to_datetime(df_videos["snippet.publishedAt"], utc=True)).dt.total_seconds() / 86400
df_snapshot = df_videos[
    ["id", "snippet.channelId", "pulled_at", "age_days_at_pull",
     "statistics.viewCount", "statistics.likeCount", "statistics.commentCount"]
]

# Snapshots go first: if the run dies between the two writes, the untouched `videos` table
# still lacks these ids, so the rerun re-scrapes them (the upsert keeps that idempotent).
write_table(bq_client, "engagement_snapshots", df_snapshot, "upsert")
write_table(bq_client, "videos", df_videos, "upsert")

if args.env == "local":
    for df_new, path in [(df_videos, VIDEOS_PATH), (df_snapshot, SNAPSHOTS_PATH)]:
        if os.path.exists(path):
            df_new = pd.concat([pd.read_csv(path, low_memory=False), df_new], ignore_index=True)
        df_new.drop_duplicates("id", keep="last").to_csv(path, index=False)
    print(f"CSV backups written to {DATA_DIR}")

print(f"Done: {len(df_channels)} channels, {len(df_videos)} new videos and snapshot rows.")
