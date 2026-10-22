"""Write DataFrames to BigQuery tables in project GCP_PROJECT_ID, dataset BQ_DATASET.

Auth is Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS). The service
account needs BigQuery Data Editor + BigQuery Job User on the project.

Column names: BigQuery rejects dots, so 'snippet.title' is stored as 'snippet_title'.
Column types: an existing table's types win (so a run where a count column is all-NULL
doesn't flip INT64 -> FLOAT64); otherwise inferred from the DataFrame.
"""

import os
import re
import sys
import warnings

import pandas as pd
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import GCP_PROJECT_ID, BQ_DATASET, BQ_LOCATION

# Loading a DataFrame works without pandas-gbq today; the library only warns that a future version will want it.
warnings.filterwarnings("ignore", message="Loading pandas DataFrame into BigQuery will require pandas-gbq")

# publishedAt, actualStartTime, recordingDate, pulled_at ... all arrive as ISO strings.
TIMESTAMP_NAME = re.compile(r"(At|Time|Date)$|_at$")
LEGACY_TYPES = {"INTEGER": "INT64", "FLOAT": "FLOAT64", "BOOL": "BOOLEAN"}


def get_client():
    client = bigquery.Client(project=GCP_PROJECT_ID, location=BQ_LOCATION)
    dataset = bigquery.Dataset(f"{GCP_PROJECT_ID}.{BQ_DATASET}")
    dataset.location = BQ_LOCATION
    client.create_dataset(dataset, exists_ok=True)
    return client


def get_existing_ids(client, table_name):
    """Set of video ids already in a table (a set, not a list: membership is checked per playlist item)."""
    try:
        rows = client.query(f"SELECT id FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.{table_name}`").result()
        return {row.id for row in rows}
    except NotFound:
        return set()


def query_rows(client, sql, params=None):
    """Rows of a query as a list, or [] when a table it reads doesn't exist yet."""
    try:
        return list(client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params or [])).result())
    except NotFound:
        return []


def set_column_descriptions(client, table_name, descriptions):
    """Set BigQuery column descriptions from a {column: text} dict; other columns keep theirs."""
    table = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{table_name}")
    table.schema = [
        bigquery.SchemaField(field.name, field.field_type, mode=field.mode, description=descriptions.get(field.name, field.description))
        for field in table.schema
    ]
    client.update_table(table, ["schema"])


SNAPSHOT_TABLES_DDL = """
CREATE TABLE IF NOT EXISTS `{dataset}.video_daily_snapshots` (
  snapshot_date DATE NOT NULL OPTIONS(description="UTC date of the pull; the partition key"),
  snapshot_at TIMESTAMP NOT NULL OPTIONS(description="Exact time of the pull (runs are ~24 h apart, not exactly)"),
  video_id STRING NOT NULL,
  channel_id STRING,
  published_at TIMESTAMP,
  age_days FLOAT64 OPTIONS(description="Days between publish and snapshot_at"),
  view_count INT64 OPTIONS(description="Lifetime views at snapshot_at (cumulative: diff consecutive days for daily gain)"),
  like_count INT64 OPTIONS(description="Lifetime likes; NULL when the creator hides likes"),
  comment_count INT64 OPTIONS(description="Lifetime comments; NULL when comments are off"),
  is_available BOOL NOT NULL OPTIONS(description="FALSE when the API no longer returns the video (deleted or private)")
)
PARTITION BY snapshot_date
CLUSTER BY channel_id, video_id
OPTIONS(description="Periodic snapshot fact table: one row per video per day");

CREATE TABLE IF NOT EXISTS `{dataset}.channel_daily_snapshots` (
  snapshot_date DATE NOT NULL,
  snapshot_at TIMESTAMP NOT NULL,
  channel_id STRING NOT NULL,
  channel_title STRING,
  subscriber_count INT64 OPTIONS(description="Rounded by YouTube to 3 significant figures; NULL when hidden"),
  view_count INT64,
  video_count INT64
)
PARTITION BY snapshot_date
CLUSTER BY channel_id
OPTIONS(description="Periodic snapshot fact table: one row per channel per day");
"""


def ensure_snapshot_tables(client):
    """Create the daily snapshot tables (date-partitioned, explicit schema) if they don't exist."""
    client.query(SNAPSHOT_TABLES_DDL.format(dataset=f"{GCP_PROJECT_ID}.{BQ_DATASET}")).result()


def write_partition(client, table_name, df, partition_date):
    """Replace one day's partition of a date-partitioned table with df. Rerunning a day overwrites that day
    instead of appending duplicates, so a failed or repeated run is safe to replay."""
    table = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{table_name}")
    job_config = bigquery.LoadJobConfig(schema=table.schema, write_disposition="WRITE_TRUNCATE")
    destination = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{table_name}${partition_date:%Y%m%d}"
    client.load_table_from_dataframe(df, destination, job_config=job_config).result()
    print(f"BigQuery: wrote {len(df)} rows to {table_name} partition {partition_date}")


def delete_channel_rows(client, table_name, channel_column, channel_ids):
    """Delete every row of the given channels from a table; a table that doesn't exist yet is skipped."""
    try:
        job = client.query(
            f"DELETE FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.{table_name}` WHERE {channel_column} IN UNNEST(@channel_ids)",
            job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("channel_ids", "STRING", channel_ids)]),
        )
        job.result()
        print(f"BigQuery: deleted {job.num_dml_affected_rows} rows from {table_name}")
    except NotFound:
        pass


def write_table(client, table_name, df, mode):
    """mode: 'replace' (overwrite table), 'append', or 'upsert' (delete rows whose `id` is in df, then append)."""
    table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{table_name}"
    try:
        existing_types = {field.name: LEGACY_TYPES.get(field.field_type, field.field_type) for field in client.get_table(table_id).schema}
    except NotFound:
        existing_types = {}
    if mode == "replace":
        existing_types = {}

    df_bq = df.copy()
    df_bq.columns = [re.sub(r"\W", "_", column) for column in df_bq.columns]
    schema = []
    for column in df_bq.columns:
        if column in existing_types:
            field_type = existing_types[column]
        elif TIMESTAMP_NAME.search(column):
            field_type = "TIMESTAMP"
        elif pd.api.types.is_bool_dtype(df_bq[column]):
            field_type = "BOOLEAN"
        elif pd.api.types.is_integer_dtype(df_bq[column]):
            field_type = "INT64"
        elif pd.api.types.is_float_dtype(df_bq[column]):
            field_type = "FLOAT64"
        else:
            field_type = "STRING"

        if field_type == "TIMESTAMP":
            df_bq[column] = pd.to_datetime(df_bq[column], utc=True, errors="coerce")
        elif field_type == "INT64":
            df_bq[column] = pd.to_numeric(df_bq[column], errors="coerce").astype("Int64")
        elif field_type == "FLOAT64":
            df_bq[column] = pd.to_numeric(df_bq[column], errors="coerce").astype("float64")
        elif field_type == "BOOLEAN":
            df_bq[column] = df_bq[column].astype("boolean")
        else:
            df_bq[column] = df_bq[column].astype("string")
        schema.append(bigquery.SchemaField(column, field_type))

    if mode == "upsert" and existing_types:
        client.query(
            f"DELETE FROM `{table_id}` WHERE id IN UNNEST(@ids)",
            job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("ids", "STRING", df_bq["id"].tolist())]),
        ).result()

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition="WRITE_TRUNCATE" if mode == "replace" else "WRITE_APPEND",
        # Lets a later pull add a column the API only returns for some videos.
        schema_update_options=[] if mode == "replace" else [bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
    )
    client.load_table_from_dataframe(df_bq, table_id, job_config=job_config).result()
    print(f"BigQuery: wrote {len(df_bq)} rows to {table_id} ({mode})")
