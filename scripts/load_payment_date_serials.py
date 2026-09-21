"""Read-only preview by default; preserve the PAYMENTS date cell's underlying value.

The operational Bronze snapshot keeps displayed strings exactly as received.
This sidecar pins the unformatted date cell to that snapshot only when the
live A/B date/reference cells still agree with every stored source row.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google.api_core.exceptions import NotFound
from google.auth.transport.requests import Request
from google.cloud import bigquery
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


ROOT = Path(__file__).resolve().parents[1]
SOURCE_TABLE = "payments_edbb6850cf6e869051a3d067090e04c87b6c0167d7e2881de47f26d3706c21e4"
PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
load_dotenv(ROOT / ".env")


def private_path(key, default):
    path = Path(os.getenv(key) or default)
    return path if path.is_absolute() else ROOT / path


def payment_source_id():
    metadata = json.loads(private_path("NOMOBUG_GOOGLE_METADATA", "data/profiles/google_source_metadata.json").read_text(encoding="utf-8-sig"))
    approved = json.loads(private_path("NOMOBUG_GOOGLE_SOURCE_IDS", "secrets/google_source_ids.json").read_text(encoding="utf-8-sig"))["spreadsheet_ids"]
    matches = [item["spreadsheetId"] for item in metadata["spreadsheets"]
               if item["properties"]["title"] == "SESSION & PAYMENT (NMB)- CHIA"
               and item["spreadsheetId"] in approved]
    if len(matches) != 1:
        raise ValueError("Approved PAYMENTS source is missing or ambiguous")
    return matches[0]


def value_rows(service, spreadsheet_id, option):
    return service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range="'PAYMENTS'!A2:B",
        valueRenderOption=option, dateTimeRenderOption="SERIAL_NUMBER",
        majorDimension="ROWS",
    ).execute(num_retries=2).get("values", [])


def prepare_rows(stored, formatted, unformatted):
    expected_positions = list(range(2, len(stored) + 2))
    if [row["source_sheet_row"] for row in stored] != expected_positions:
        raise ValueError("Stored PAYMENTS row positions are not contiguous")
    if len(formatted) > len(stored) or len(unformatted) > len(stored):
        raise ValueError("Live PAYMENTS has more rows than the selected Bronze snapshot")
    records = []
    for index, source in enumerate(stored):
        display = formatted[index] if index < len(formatted) else []
        raw = unformatted[index] if index < len(unformatted) else []
        display_date = str(display[0]) if display else ""
        display_reference = str(display[1]) if len(display) > 1 else ""
        if (display_date, display_reference) != (source["payment_date_raw"], source["sales_references_raw"]):
            raise ValueError(f"Live date/reference differs from Bronze at row {source['source_sheet_row']}; no upload")
        value = raw[0] if raw else ""
        if value == "":
            value_type = "blank"
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            value_type = "serial"
        else:
            value_type = "text"
        records.append({"source_sheet_row": source["source_sheet_row"],
                        "payment_date_display_raw": display_date,
                        "unformatted_value": str(value), "unformatted_type": value_type})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    if os.getenv("NOMOBUG_BQ_PROJECT") != PROJECT or os.getenv("NOMOBUG_BQ_LOCATION", "").lower() != LOCATION:
        raise SystemExit("Unexpected project/region; no work performed")
    if args.upload and os.getenv("NOMOBUG_BQ_UPLOAD_APPROVED") != "yes":
        raise SystemExit("Upload approval gate is not set; no work performed")
    credentials = Credentials.from_authorized_user_file(str(private_path("NOMOBUG_GOOGLE_TOKEN", "secrets/google_token.json")), [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
    ])
    if not credentials.valid:
        credentials.refresh(Request())
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    source_id = payment_source_id()
    live = service.spreadsheets().get(spreadsheetId=source_id,
        fields="properties(title),sheets(properties(title))").execute(num_retries=2)
    if live["properties"]["title"] != "SESSION & PAYMENT (NMB)- CHIA" or "PAYMENTS" not in [s["properties"]["title"] for s in live["sheets"]]:
        raise SystemExit("Live PAYMENTS workbook/tab changed; no work performed")
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        query = (f"SELECT source_sheet_row, source_column_001 AS payment_date_raw, "
                 f"source_column_002 AS sales_references_raw FROM `{PROJECT}.bronze.{SOURCE_TABLE}` "
                 "ORDER BY source_sheet_row")
        stored = [dict(row) for row in client.query(query, location=LOCATION,
            job_config=bigquery.QueryJobConfig(maximum_bytes_billed=104857600)).result(timeout=120)]
        if not stored:
            raise ValueError("Selected Bronze PAYMENTS snapshot is empty")
        formatted = value_rows(service, source_id, "FORMATTED_VALUE")
        unformatted = value_rows(service, source_id, "UNFORMATTED_VALUE")
        records = prepare_rows(stored, formatted, unformatted)
        counts = {kind: sum(row["unformatted_type"] == kind for row in records)
                  for kind in ("serial", "text", "blank")}
        digest = hashlib.sha256(json.dumps({"source_table": SOURCE_TABLE, "records": records},
            ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        table_name = "payments_date_serials_" + digest
        print("PAYMENTS date sidecar plan:", len(records), "rows;", counts,
              "date/reference lineage: PASS; snapshot:", table_name)
        if not args.upload:
            print("No upload. Run with --upload only after reviewing this plan.")
            return
        dataset = client.get_dataset(f"{PROJECT}.bronze")
        if dataset.location.lower() != LOCATION or dataset.default_table_expiration_ms is not None:
            raise ValueError("Bronze dataset region/expiry mismatch")
        existing = [table.table_id for table in client.list_tables(dataset)]
        if table_name not in existing and sum(name.startswith("payments_date_serials_") for name in existing) >= 5:
            raise ValueError("Five date sidecars already stored; retention review required")
        table_id = f"{PROJECT}.bronze.{table_name}"
        schema = [bigquery.SchemaField("source_sheet_row", "INTEGER", mode="REQUIRED")]
        schema += [bigquery.SchemaField(field, "STRING", mode="REQUIRED") for field in
                   ("payment_date_display_raw", "unformatted_value", "unformatted_type")]
        metadata = {"snapshot_id": digest, "source_table": SOURCE_TABLE,
                    "source_row_count": len(records), "extracted_at": datetime.now(timezone.utc).isoformat()}
        try:
            table = client.get_table(table_id)
            status = "REUSED"
        except NotFound:
            config = bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_EMPTY",
                destination_table_description=json.dumps(metadata))
            client.load_table_from_json(records, table_id, job_config=config,
                location=LOCATION).result(timeout=180)
            table = client.get_table(table_id)
            status = "LOADED"
        if [(f.name, f.field_type, f.mode) for f in table.schema] != [(f.name, f.field_type, f.mode) for f in schema]:
            raise ValueError("Stored date sidecar schema mismatch")
        actual_meta = json.loads(table.description or "{}")
        if any(actual_meta.get(k) != metadata[k] for k in ("snapshot_id", "source_table", "source_row_count")):
            raise ValueError("Stored date sidecar metadata mismatch")
        actual = sorted((dict(row) for row in client.list_rows(table)), key=lambda row: row["source_sheet_row"])
        if actual != records:
            raise ValueError("Stored date sidecar rows/values mismatch")
        print(status, table_id, "| exact row/date values: PASS")
    finally:
        client.close()


if __name__ == "__main__":
    main()
