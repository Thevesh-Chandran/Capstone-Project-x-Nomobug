"""Read newest stored BigQuery snapshot into the shared preview's DataFrames.

Metadata and table-data reads only; no SQL query jobs or writes.
"""
import json
import os
import re
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery
from google.auth.exceptions import GoogleAuthError
from google.api_core.exceptions import GoogleAPICallError

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
project = os.getenv("NOMOBUG_BQ_PROJECT", "").strip()
location = os.getenv("NOMOBUG_BQ_LOCATION", "").strip()
if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project) or not location:
    raise SystemExit("Set NOMOBUG_BQ_PROJECT and NOMOBUG_BQ_LOCATION, or explicitly select NOMOBUG_WAREHOUSE=neon.")
client = None
try:
    client = bigquery.Client(project=project, location=location)
    dataset = client.get_dataset(f"{project}.bronze")
    if dataset.location.lower() != location.lower():
        raise ValueError("Location mismatch")
    snapshots = []
    for item in client.list_tables(dataset):
        if re.fullmatch(r"prospects_2026_[0-9a-f]{64}", item.table_id):
            table = client.get_table(item.reference)
            metadata = json.loads(table.description or "{}")
            if table.table_id != "prospects_2026_" + metadata["snapshot_id"] or metadata["source_tab"] != "2026":
                raise ValueError("Invalid snapshot metadata")
            snapshots.append((pd.to_datetime(metadata["extracted_at"], utc=True), table, metadata))
    if not snapshots:
        raise SystemExit("No BigQuery Prospects snapshot stored yet. No automatic Neon fallback.")
    _, table, metadata = max(snapshots, key=lambda item: (item[0], item[2]["snapshot_id"]))
    fields = [field for field in table.schema if field.name != "source_sheet_row"]
    records = list(client.list_rows(table))
    records.sort(key=lambda row: row["source_sheet_row"])
    stored_df = pd.DataFrame({
        "source_sheet_row": [row["source_sheet_row"] for row in records],
        "raw_values": [[row[field.name] for field in fields] for row in records],
    })
    batch = pd.Series({**metadata, "header_map": [
        {"dataframe_column": field.name, "original_header": field.description or ""} for field in fields
    ]})
except (GoogleAuthError, GoogleAPICallError, ValueError, KeyError):
    raise SystemExit("BigQuery snapshot read failed. No writes or automatic fallback. Check setup/snapshot metadata; do not share credentials.") from None
finally:
    if client is not None:
        client.close()
