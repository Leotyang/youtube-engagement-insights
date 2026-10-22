"""One-time backfill: copy the pre-snapshot pulls into the daily snapshot tables as their first day.

  engagement_snapshots (one pull per video, 2026-10-15) -> video_daily_snapshots
  channels (as last written, 2026-10-15)                -> channel_daily_snapshots

Run it before the first ingest that writes snapshots: ingest replaces `channels`, so its
2026-10-15 subscriber counts are gone afterwards. Each insert skips a date that already has rows,
so rerunning is a no-op.

Usage:
  python src/seed_snapshots.py
  BQ_DATASET=youtube_dev python src/seed_snapshots.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bigquery_io import get_client, ensure_snapshot_tables
from config import GCP_PROJECT_ID, BQ_DATASET

dataset = f"{GCP_PROJECT_ID}.{BQ_DATASET}"
client = get_client()
ensure_snapshot_tables(client)

video_job = client.query(f"""
    INSERT INTO `{dataset}.video_daily_snapshots`
    SELECT DATE(e.pulled_at), e.pulled_at, e.id, e.snippet_channelId, v.snippet_publishedAt, e.age_days_at_pull,
           CAST(e.statistics_viewCount AS INT64), CAST(e.statistics_likeCount AS INT64),
           CAST(e.statistics_commentCount AS INT64), TRUE
    FROM `{dataset}.engagement_snapshots` AS e
    LEFT JOIN `{dataset}.videos` AS v USING (id)
    WHERE DATE(e.pulled_at) NOT IN (SELECT DISTINCT snapshot_date FROM `{dataset}.video_daily_snapshots`)
""")
video_job.result()
print(f"video_daily_snapshots: inserted {video_job.num_dml_affected_rows} rows")

channel_job = client.query(f"""
    INSERT INTO `{dataset}.channel_daily_snapshots`
    SELECT DATE(pulled_at), pulled_at, id, snippet_title, CAST(statistics_subscriberCount AS INT64),
           CAST(statistics_viewCount AS INT64), CAST(statistics_videoCount AS INT64)
    FROM `{dataset}.channels`
    WHERE DATE(pulled_at) NOT IN (SELECT DISTINCT snapshot_date FROM `{dataset}.channel_daily_snapshots`)
""")
channel_job.result()
print(f"channel_daily_snapshots: inserted {channel_job.num_dml_affected_rows} rows")
