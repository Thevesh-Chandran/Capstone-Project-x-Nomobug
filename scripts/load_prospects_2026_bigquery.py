"""LIVE Sheets -> BigQuery raw snapshot. Neon remains untouched.

Requires --upload and explicit configuration/cost-control acknowledgement.
Each distinct snapshot uses one immutable table, limited to five for now.
No streaming, SQL queries, automatic deletion, or automatic provider fallback.
"""
import argparse
import hashlib
import json
import os
import re
import runpy
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery
from google.auth.exceptions import GoogleAuthError
from google.api_core.exceptions import GoogleAPICallError, NotFound

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--upload", action="store_true")
args = parser.parse_args()
if not args.upload:
    raise SystemExit("No upload performed. Use --upload only after setup and cost controls are checked.")
root = Path(__file__).resolve().parents[1]
load_dotenv(root / ".env")
project = os.getenv("NOMOBUG_BQ_PROJECT", "").strip()
location = os.getenv("NOMOBUG_BQ_LOCATION", "").strip()
if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project) or not location:
    raise SystemExit("Set NOMOBUG_BQ_PROJECT and NOMOBUG_BQ_LOCATION first.")
if os.getenv("NOMOBUG_BQ_UPLOAD_APPROVED") != "yes":
    raise SystemExit("Upload blocked. Confirm region/privacy, billing and cost controls before setting NOMOBUG_BQ_UPLOAD_APPROVED=yes.")

client = None
try:
    client = bigquery.Client(project=project, location=location)
    dataset = client.get_dataset(f"{project}.bronze")
    if dataset.location.lower() != location.lower():
        raise SystemExit("Bronze dataset location mismatch. No upload performed.")
    if dataset.default_table_expiration_ms is not None:
        raise SystemExit("Bronze has automatic table expiry. Review retention before loading raw data.")

    source = runpy.run_path(str(root / "scripts/extract_prospects_2026.py"))
    df = source["df"]
    columns = source["columns"]
    headers = source["header_map"]["original_header"].tolist()
    # Load relative to this file so direct execution and runpy use the same guard.
    contract = runpy.run_path(str(root / "scripts/prospects_source_contract.py"))
    contract["validate_headers"](headers)
    raw_rows = df[columns].values.tolist()
    if not raw_rows:
        raise SystemExit("Empty source extraction. No upload performed.")
    # Same snapshot identity structure as the retained Neon loader.
    snapshot = {"format_version": 1, "spreadsheet_id": source["spreadsheet_id"],
                "tab": source["tab_name"], "headers": source["header_map"].to_dict(orient="records"),
                "rows": raw_rows}
    digest = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    table_id = f"{project}.bronze.prospects_2026_{digest}"
    metadata = {"format_version": 1, "snapshot_id": digest, "source_tab": source["tab_name"],
                "extracted_at": source["extracted_at"], "extraction_started_at": source["extraction_started_at"],
                "source_row_count": len(df), "source_column_count": len(columns)}
    try:
        table = client.get_table(table_id)
        new_snapshot = False
    except NotFound:
        new_snapshot = True
        # A local safety gate, NOT a billing cap. Run only one loader at a time.
        snapshots = [t for t in client.list_tables(dataset) if t.table_id.startswith("prospects_2026_")]
        if len(snapshots) >= 5:
            raise SystemExit("Five raw snapshots already stored. Stop for retention/storage review; Neon was not activated.")
        if len(json.dumps(snapshot).encode("utf-8")) > 100 * 1024**2:
            raise SystemExit("Snapshot exceeds this first-loader 100 MiB payload gate. Review before uploading.")
        schema = [bigquery.SchemaField("source_sheet_row", "INTEGER", mode="REQUIRED")]
        schema += [bigquery.SchemaField(c, "STRING", mode="REQUIRED", description=h)
                   for c, h in zip(columns, headers)]
        config = bigquery.LoadJobConfig(
            schema=schema, write_disposition="WRITE_EMPTY",
            destination_table_description=json.dumps(metadata),
        )
        records = df.to_dict(orient="records")
        print("Uploading one atomic batch to BigQuery; no Neon writes.")
        job = client.load_table_from_json(records, table_id, job_config=config, location=location)
        job.result(timeout=180)
        table = client.get_table(table_id)

    # list_rows reads directly: no SQL scan/query job. Do not print returned values.
    expected_schema = [("source_sheet_row", "INTEGER", "REQUIRED")] + [(c, "STRING", "REQUIRED") for c in columns]
    if [(f.name, f.field_type, f.mode) for f in table.schema] != expected_schema:
        raise ValueError("Schema mismatch")
    if [(f.description or "") for f in table.schema[1:]] != headers:
        raise ValueError("Header mismatch")
    if json.loads(table.description or "{}").get("snapshot_id") != digest:
        raise ValueError("Snapshot metadata mismatch")
    # For identical content, lineage uses the ORIGINAL stored extraction time.
    verified_metadata = json.loads(table.description)
    returned = list(client.list_rows(table))
    returned.sort(key=lambda row: row["source_sheet_row"])
    if len(returned) != len(df) or any(
        row["source_sheet_row"] != position + 2 or [row[c] for c in columns] != raw_rows[position]
        for position, row in enumerate(returned)
    ):
        raise ValueError("Stored values mismatch")
    print("\nBigQuery Bronze verification:")
    print("Status:", "New snapshot loaded and verified" if new_snapshot else "Identical snapshot verified; skipped")
    print("API/DataFrame rows:", len(df))
    print("Stored rows:", len(returned))
    print("Original headers, values and row positions: PASS")
    print("Neon unchanged. No Silver writes. No automatic fallback or deletion.")
except (GoogleAuthError, GoogleAPICallError, ValueError, TimeoutError):
    raise SystemExit("BigQuery load not confirmed. A submitted job may still have committed; rerun safely checks the same snapshot table. Do not share raw errors or tokens. Neon unchanged.") from None
finally:
    if client is not None:
        client.close()
