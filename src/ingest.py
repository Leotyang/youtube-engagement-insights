"""Nightly ingest for the channels on the Google Sheet: upsert their latest metadata and metrics, snapshot engagement.

Only channels currently on the sheet are pulled; nothing is ever deleted. Rows of a channel removed from the
sheet stay in BigQuery untouched until they are cleaned up by hand.

Each run:
  1. channels                 upsert of the sheet's channels (all API fields).
  2. New videos               each channel's uploads from the last LOOKBACK_DAYS that aren't in BigQuery yet
                              (a new channel gets its whole window; known channels stop at their first known video).
  3. Every video of these channels is re-fetched (videos.list, 50 ids per quota unit) and written to
       videos                   one row per video, latest metadata and counts. pulled_at and age_days_at_pull
                                describe this pull, first_pulled_at the first one.
       video_daily_snapshots    one row per video per day; a video the API no longer returns (deleted or
                                private) gets is_available = FALSE
       channel_daily_snapshots  one row per channel per day
     Snapshot writes replace today's partition, so rerunning a day is safe.

Usage:
  python src/ingest.py --env local    BigQuery plus CSV copies in config.DATA_DIR (default)
  python src/ingest.py --env github   BigQuery only (the GitHub Action)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bigquery_io import (get_client as get_bq_client, get_existing_ids, query_rows, write_table, write_partition,
                         ensure_snapshot_tables)
from config import (GCP_PROJECT_ID, BQ_DATASET, LOOKBACK_DAYS, DATA_DIR, CHANNELS_PATH, VIDEOS_PATH,
                    VIDEO_SNAPSHOTS_PATH, CHANNEL_SNAPSHOTS_PATH)
from sheet import get_creators
from youtube_api import get_client, get_channels, get_video_ids, get_videos

parser = argparse.ArgumentParser()
parser.add_argument("--env", choices=["local", "github"], default="local")
args = parser.parse_args()

df_creators = get_creators()
if df_creators.empty:
    sys.exit("No usable channel URLs in the Google Sheet.")

dataset = f"{GCP_PROJECT_ID}.{BQ_DATASET}"
print(f"About to query the YouTube API for {len(df_creators)} channels")
youtube = get_client()
now = datetime.now(timezone.utc)
pulled_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
bq_client = get_bq_client()
ensure_snapshot_tables(bq_client)

df_channels = get_channels(youtube, df_creators["channel_url"].tolist())
df_channels = df_channels.merge(df_creators, on="channel_url", how="left")
df_channels["pulled_at"] = pulled_at
write_table(bq_client, "channels", df_channels, "upsert")

known_ids = get_existing_ids(bq_client, "videos")
print(f"{len(known_ids)} videos already in BigQuery")
published_after = pd.Timestamp(now - timedelta(days=LOOKBACK_DAYS))
new_ids = []
for _, channel in df_channels.iterrows():
    video_ids = get_video_ids(youtube, channel["contentDetails.relatedPlaylists.uploads"], published_after, pd.Timestamp(now), known_ids)
    print(f"{channel['snippet.title']}: {len(video_ids)} new videos")
    new_ids += video_ids

df_known = pd.DataFrame([dict(row.items()) for row in query_rows(
    bq_client, f"SELECT id, snippet_channelId AS channel_id, snippet_publishedAt AS published_at, first_pulled_at FROM `{dataset}.videos`")],
    columns=["id", "channel_id", "published_at", "first_pulled_at"])
df_known = df_known[df_known["channel_id"].isin(df_channels["id"])]

all_ids = df_known["id"].tolist() + new_ids
print(f"Refreshing {len(all_ids)} videos ({len(new_ids)} new) in {(len(all_ids) + 49) // 50} API calls")
df_videos = get_videos(youtube, all_ids)
df_videos["pulled_at"] = pulled_at
df_videos["age_days_at_pull"] = (now - pd.to_datetime(df_videos["snippet.publishedAt"], utc=True)).dt.total_seconds() / 86400
df_videos["first_pulled_at"] = df_videos["id"].map(df_known.set_index("id")["first_pulled_at"]).fillna(pd.Timestamp(now))
write_table(bq_client, "videos", df_videos, "upsert")

df_available = pd.DataFrame({
    "video_id": df_videos["id"],
    "channel_id": df_videos["snippet.channelId"],
    "published_at": pd.to_datetime(df_videos["snippet.publishedAt"], utc=True),
    "view_count": df_videos.get("statistics.viewCount"),
    "like_count": df_videos.get("statistics.likeCount"),
    "comment_count": df_videos.get("statistics.commentCount"),
    "is_available": True,
})
df_missing = df_known[~df_known["id"].isin(df_videos["id"])].rename(columns={"id": "video_id"})[["video_id", "channel_id", "published_at"]]
df_missing["published_at"] = pd.to_datetime(df_missing["published_at"], utc=True)
df_missing["is_available"] = False
if len(df_missing):
    print(f"{len(df_missing)} known videos were not returned (deleted or private)")
df_video_snapshot = pd.concat([df_available, df_missing], ignore_index=True)
df_video_snapshot["snapshot_date"] = now.date()
df_video_snapshot["snapshot_at"] = pd.Timestamp(now)
df_video_snapshot["age_days"] = (pd.Timestamp(now) - df_video_snapshot["published_at"]).dt.total_seconds() / 86400
for column in ["view_count", "like_count", "comment_count"]:
    df_video_snapshot[column] = pd.to_numeric(df_video_snapshot[column], errors="coerce").round().astype("Int64")
df_video_snapshot["is_available"] = df_video_snapshot["is_available"].astype(bool)
df_video_snapshot = df_video_snapshot[["snapshot_date", "snapshot_at", "video_id", "channel_id", "published_at", "age_days",
                                       "view_count", "like_count", "comment_count", "is_available"]]
write_partition(bq_client, "video_daily_snapshots", df_video_snapshot, now.date())

df_channel_snapshot = pd.DataFrame({
    "snapshot_date": now.date(),
    "snapshot_at": pd.Timestamp(now),
    "channel_id": df_channels["id"],
    "channel_title": df_channels["snippet.title"],
    "subscriber_count": pd.to_numeric(df_channels.get("statistics.subscriberCount"), errors="coerce").astype("Int64"),
    "view_count": pd.to_numeric(df_channels.get("statistics.viewCount"), errors="coerce").astype("Int64"),
    "video_count": pd.to_numeric(df_channels.get("statistics.videoCount"), errors="coerce").astype("Int64"),
})
write_partition(bq_client, "channel_daily_snapshots", df_channel_snapshot, now.date())

if args.env == "local":
    os.makedirs(DATA_DIR, exist_ok=True)
    df_channels.to_csv(CHANNELS_PATH, index=False)
    df_videos.to_csv(VIDEOS_PATH, index=False)
    # Snapshot CSVs accumulate one day per run, keyed like their tables, so a rerun replaces that day.
    for df_today, path, key in [(df_video_snapshot, VIDEO_SNAPSHOTS_PATH, "video_id"),
                                (df_channel_snapshot, CHANNEL_SNAPSHOTS_PATH, "channel_id")]:
        df_all = df_today.astype({"snapshot_date": str})
        if os.path.exists(path):
            df_all = pd.concat([pd.read_csv(path), df_all], ignore_index=True)
        df_all.drop_duplicates([key, "snapshot_date"], keep="last").to_csv(path, index=False)
    print(f"CSV copies written to {DATA_DIR}")

print(f"Done: {len(df_channels)} channels, {len(df_videos)} videos refreshed ({len(new_ids)} new), "
      f"{len(df_video_snapshot)} video and {len(df_channel_snapshot)} channel snapshot rows for {now.date()}.")
