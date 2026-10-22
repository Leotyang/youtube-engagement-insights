"""Nightly ingest: sync the creator list from the Google Sheet, refresh every video, snapshot engagement.

Each run:
  1. Channels no longer on the sheet: delete their rows from every table (stops if more than
     MAX_CHANNELS_REMOVED_PER_RUN would go; pass --allow-mass-removal to proceed).
  2. channels: replaced with the sheet's current channels (all API fields).
  3. Discover videos published in the last LOOKBACK_DAYS that aren't in BigQuery yet (new channels
     get their whole year; existing channels stop paging at their first known video).
  4. Re-fetch every known video plus the new ones (videos.list, 50 ids per quota unit) and write:
       videos                   one row per video, latest metadata and counts. pulled_at and
                                age_days_at_pull describe this pull; first_pulled_at the first one.
       video_daily_snapshots    one row per video per day; unavailable videos get is_available = FALSE
       channel_daily_snapshots  one row per channel per day
     Snapshot writes overwrite today's partition, so rerunning a day is safe.

engagement_snapshots (one pull per video, 2026-10-15) is legacy and no longer written; its rows seed
video_daily_snapshots for that date (src/seed_snapshots.py).

Usage:
  python src/ingest.py --env local    also writes CSV backups to config.DATA_DIR (default)
  python src/ingest.py --env github   BigQuery only (used by the GitHub Action)
  BQ_DATASET=youtube_dev python src/ingest.py ...   run against the dev dataset
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bigquery_io import (get_client as get_bq_client, get_existing_ids, query_rows, write_table, write_partition,
                         ensure_snapshot_tables, delete_channel_rows)
from config import (GCP_PROJECT_ID, BQ_DATASET, LOOKBACK_DAYS, MAX_CHANNELS_REMOVED_PER_RUN, DATA_DIR,
                    CHANNELS_PATH, VIDEOS_PATH, VIDEO_SNAPSHOTS_PATH)
from sheet import get_creators
from youtube_api import get_client, get_channels, get_video_ids, get_videos

# Every table that holds per-channel rows, and the column naming the channel.
CHANNEL_COLUMNS = {
    "videos": "snippet_channelId",
    "engagement_snapshots": "snippet_channelId",
    "llm_tagged": "channel_id",
    "video_daily_snapshots": "channel_id",
    "channel_daily_snapshots": "channel_id",
}

parser = argparse.ArgumentParser()
parser.add_argument("--env", choices=["local", "github"], default="local")
parser.add_argument("--allow-mass-removal", action="store_true", help=f"remove more than {MAX_CHANNELS_REMOVED_PER_RUN} channels in one run")
args = parser.parse_args()

df_creators = get_creators()
if df_creators.empty:
    sys.exit("No usable channel URLs in the Google Sheet.")

dataset = f"{GCP_PROJECT_ID}.{BQ_DATASET}"
print(f"Dataset {dataset}; about to query the YouTube API for {len(df_creators)} channels")
youtube = get_client()
now = datetime.now(timezone.utc)
pulled_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
bq_client = get_bq_client()
ensure_snapshot_tables(bq_client)

# Removed channels are matched by URL against last run's channels table, not by which channels resolve
# tonight, so a channel the API fails to look up once is never mistaken for a removal.
sheet_urls = df_creators["channel_url"].tolist()
removed = [row for row in query_rows(bq_client, f"SELECT id, snippet_title, channel_url FROM `{dataset}.channels`")
           if row.channel_url not in sheet_urls]
if removed:
    print(f"Channels no longer on the sheet: {[row.snippet_title for row in removed]}")
    if len(removed) > MAX_CHANNELS_REMOVED_PER_RUN and not args.allow_mass_removal:
        sys.exit(f"Refusing to delete {len(removed)} channels in one run (limit {MAX_CHANNELS_REMOVED_PER_RUN}). "
                 "Check the sheet, or rerun with --allow-mass-removal.")
    for table_name, channel_column in CHANNEL_COLUMNS.items():
        delete_channel_rows(bq_client, table_name, channel_column, [row.id for row in removed])

df_channels = get_channels(youtube, sheet_urls)
df_channels = df_channels.merge(df_creators, on="channel_url", how="left")
df_channels["pulled_at"] = pulled_at
write_table(bq_client, "channels", df_channels, "replace")

known_ids = get_existing_ids(bq_client, "videos")
print(f"{len(known_ids)} videos already in BigQuery")
published_after = pd.Timestamp(now - timedelta(days=LOOKBACK_DAYS))
new_ids = []
for _, channel in df_channels.iterrows():
    video_ids = get_video_ids(youtube, channel["contentDetails.relatedPlaylists.uploads"], published_after, pd.Timestamp(now), known_ids)
    print(f"{channel['snippet.title']}: {len(video_ids)} new videos")
    new_ids += video_ids

# first_pulled_at keeps the first pull of each video; tables written before it existed fall back to pulled_at.
videos_table = bq_client.get_table(f"{dataset}.videos") if known_ids else None
first_pulled_column = "first_pulled_at" if videos_table and "first_pulled_at" in [field.name for field in videos_table.schema] else "pulled_at"
df_known = pd.DataFrame([dict(row.items()) for row in query_rows(
    bq_client, f"SELECT id, snippet_channelId AS channel_id, snippet_publishedAt AS published_at, {first_pulled_column} AS first_pulled_at FROM `{dataset}.videos`")],
    columns=["id", "channel_id", "published_at", "first_pulled_at"])

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
    df_snapshot_csv = df_video_snapshot
    if os.path.exists(VIDEO_SNAPSHOTS_PATH):
        df_snapshot_csv = pd.concat([pd.read_csv(VIDEO_SNAPSHOTS_PATH), df_video_snapshot.astype({"snapshot_date": str})], ignore_index=True)
    df_snapshot_csv.astype({"snapshot_date": str}).drop_duplicates(["video_id", "snapshot_date"], keep="last").to_csv(VIDEO_SNAPSHOTS_PATH, index=False)
    print(f"CSV backups written to {DATA_DIR}")

print(f"Done: {len(df_channels)} channels, {len(df_videos)} videos refreshed ({len(new_ids)} new), "
      f"{len(df_video_snapshot)} video and {len(df_channel_snapshot)} channel snapshot rows for {now.date()}.")
