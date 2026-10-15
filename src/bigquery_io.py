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
