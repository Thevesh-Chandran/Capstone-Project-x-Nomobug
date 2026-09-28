"""Read and optionally load all six approved Nomobug Calendars as one Bronze snapshot.

The default is a read-only plan. ``--upload`` writes one content-addressed
snapshot to BigQuery after the same pagination, region and approval checks.
Event descriptions are retained in restricted Bronze for lineage; no raw event
text is printed by this script.
"""
import argparse
import hashlib
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.api_core.exceptions import NotFound, GoogleAPICallError
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.cloud import bigquery
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parents[1]
LOCAL_TZ_NAME = "Asia/Kuala_Lumpur"
DEFAULT_START = date(2000, 1, 1)
FIELDS = [
    "calendar_event_row", "calendar_name", "calendar_id", "event_id", "ical_uid",
    "status", "event_type", "start_raw", "end_raw", "is_all_day", "summary",
    "description", "location", "created_raw", "updated_raw", "recurring_event_id",
]


def _local_path(value: str | None, default: str) -> Path:
    path = Path(value or default)
    return path if path.is_absolute() else ROOT / path


def _credentials() -> Credentials:
    token = _local_path(os.getenv("NOMOBUG_GOOGLE_TOKEN"), "secrets/google_token.json")
    credentials = Credentials.from_authorized_user_file(str(token), [
        "https://www.googleapis.com/auth/calendar.readonly",
    ])
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except GoogleAuthError:
                raise SystemExit("Google Calendar sign-in needs renewal: python scripts/renew_google_access.py") from None
        else:
            raise SystemExit("Google Calendar sign-in needs renewal: python scripts/renew_google_access.py")
    return credentials


def _targets(metadata_path: Path) -> list[dict]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    targets = [c for c in metadata.get("calendars", []) if c.get("target_name_match")]
    names = [str(c.get("summary", "")).strip() for c in targets]
    if len(targets) != 6 or len(set(names)) != 6 or any(not c.get("id") for c in targets):
        raise SystemExit("Expected six unique approved Calendar IDs; stop for inventory review.")
    return targets


def _window(start_date: date, end_date: date) -> tuple[str, str]:
    tz = ZoneInfo(LOCAL_TZ_NAME)
    start = datetime.combine(start_date, time.min, tzinfo=tz)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    return start.isoformat(), end.isoformat()


def _fetch(targets: list[dict], start_date: date, end_date: date) -> list[dict]:
    credentials = _credentials()
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    time_min, time_max = _window(start_date, end_date)
    records = []
    try:
        for target in targets:
            page_token = None
            while True:
                response = service.events().list(
                    calendarId=target["id"], timeMin=time_min, timeMax=time_max,
                    timeZone=LOCAL_TZ_NAME, maxResults=2500, singleEvents=True,
                    orderBy="startTime", showDeleted=True, pageToken=page_token,
                ).execute(num_retries=2)
                for event in response.get("items", []):
                    start = event.get("start") or {}
                    end = event.get("end") or {}
                    records.append({
                        "calendar_event_row": len(records) + 1,
                        "calendar_name": target["summary"],
                        "calendar_id": target["id"],
                        "event_id": event.get("id"),
                        "ical_uid": event.get("iCalUID"),
                        "status": event.get("status"),
                        "event_type": event.get("eventType"),
                        "start_raw": start.get("dateTime") or start.get("date"),
                        "end_raw": end.get("dateTime") or end.get("date"),
                        "is_all_day": bool(start.get("date") and not start.get("dateTime")),
                        "summary": event.get("summary"),
                        "description": event.get("description"),
                        "location": event.get("location"),
                        "created_raw": event.get("created"),
                        "updated_raw": event.get("updated"),
                        "recurring_event_id": event.get("recurringEventId"),
                    })
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
    except (GoogleAuthError, HttpError, OSError) as error:
        raise SystemExit(f"Google Calendar read failed: {type(error).__name__}. No warehouse changes.") from None
    finally:
        service.close()
    return records


def _snapshot(records: list[dict], targets: list[dict], start_date: date, end_date: date) -> dict:
    # Extraction timestamps belong in metadata, not the digest, so an identical
    # rerun reuses the same immutable table.
    payload = {"version": 1, "source_calendar_ids": [c["id"] for c in targets],
        "window_start": start_date.isoformat(), "window_end": end_date.isoformat(),
        "fields": FIELDS, "records": records}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()
    schema = [bigquery.SchemaField("calendar_event_row", "INTEGER", mode="REQUIRED")]
    schema += [bigquery.SchemaField("is_all_day", "BOOLEAN", mode="REQUIRED")]
    schema += [bigquery.SchemaField(field, "STRING", mode="NULLABLE") for field in FIELDS[1:9]]
    schema += [bigquery.SchemaField(field, "STRING", mode="NULLABLE") for field in FIELDS[10:]]
    now = datetime.now(timezone.utc).isoformat()
    metadata = {"format_version": 1, "snapshot_id": digest, "source_type": "Google Calendar",
        "calendar_count": len(targets), "event_row_count": len(records),
        "window_start": start_date.isoformat(), "window_end": end_date.isoformat(),
        "extracted_at": now, "timezone": LOCAL_TZ_NAME, "show_deleted": True}
    return {"table_name": f"calendar_events_{digest}", "schema": schema,
        "records": records, "metadata": metadata}


def _verify_load(client: bigquery.Client, project: str, location: str, snapshot: dict) -> dict:
    table_id = f"{project}.bronze.{snapshot['table_name']}"
    try:
        table = client.get_table(table_id)
        status = "REUSED"
    except NotFound:
        config = bigquery.LoadJobConfig(schema=snapshot["schema"], write_disposition="WRITE_EMPTY",
            destination_table_description=json.dumps(snapshot["metadata"]))
        client.load_table_from_json(snapshot["records"], table_id, job_config=config,
            location=location).result(timeout=300)
        table = client.get_table(table_id)
        status = "LOADED"
    stored_metadata = json.loads(table.description or "{}")
    expected_schema = [(field.name, field.field_type, field.mode) for field in snapshot["schema"]]
    actual_schema = [(field.name, field.field_type, field.mode) for field in table.schema]
    if actual_schema != expected_schema or stored_metadata.get("snapshot_id") != snapshot["metadata"]["snapshot_id"]:
        raise ValueError("Calendar Bronze schema or metadata mismatch")
    actual = sorted((dict(row) for row in client.list_rows(table)), key=lambda row: row["calendar_event_row"])
    if actual != snapshot["records"]:
        raise ValueError("Calendar Bronze rows/values mismatch")
    return {"status": status, "table": table_id, "rows": len(actual)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--start-date", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--private-snapshot-json", type=Path,
        help="Save read-only source evidence inside the project's ignored outputs folder.")
    args = parser.parse_args()
    if args.private_snapshot_json:
        private_path = args.private_snapshot_json.resolve()
        if not private_path.is_relative_to((ROOT / "outputs").resolve()):
            raise SystemExit("Private Calendar snapshots must stay inside ignored project outputs.")
        if private_path.exists():
            raise SystemExit("Private Calendar snapshot already exists; choose a new filename.")
    load_dotenv(ROOT / ".env")
    if args.end_date < args.start_date:
        raise SystemExit("End date must be on or after start date.")
    if args.upload and os.getenv("NOMOBUG_BQ_UPLOAD_APPROVED") != "yes":
        raise SystemExit("Upload blocked: NOMOBUG_BQ_UPLOAD_APPROVED=yes is required.")
    project = os.getenv("NOMOBUG_BQ_PROJECT", "").strip()
    location = os.getenv("NOMOBUG_BQ_LOCATION", "").strip()
    if project != "profound-keel-500007-s4" or location.lower() != "asia-southeast1":
        raise SystemExit("Unexpected BigQuery project/region. No work performed.")
    metadata_path = _local_path(os.getenv("NOMOBUG_GOOGLE_METADATA"),
        "data/profiles/google_source_metadata.json")
    targets = _targets(metadata_path)
    records = _fetch(targets, args.start_date, args.end_date)
    snapshot = _snapshot(records, targets, args.start_date, args.end_date)
    if args.private_snapshot_json:
        private_path.parent.mkdir(parents=True, exist_ok=True)
        with private_path.open("x", encoding="utf-8") as handle:
            json.dump({"metadata": snapshot["metadata"], "records": records}, handle,
                ensure_ascii=False)
    print(f"Calendar window: {args.start_date} through {args.end_date} ({LOCAL_TZ_NAME})")
    print(f"Approved calendars: {len(targets)} | event rows: {len(records)}")
    print(f"Distinct event IDs within calendar: {len({(r['calendar_id'], r['event_id']) for r in records})}")
    print(f"Cancelled rows retained: {sum(r['status'] == 'cancelled' for r in records)}")
    print(f"All-day rows: {sum(r['is_all_day'] for r in records)}")
    print(f"Missing summaries: {sum(not r['summary'] for r in records)}")
    print(f"Missing descriptions: {sum(not r['description'] for r in records)}")
    if not args.upload:
        print("PLAN PASS. No upload. Run with --upload after reviewing this scope.")
        return
    client = bigquery.Client(project=project, location=location)
    try:
        dataset = client.get_dataset(f"{project}.bronze")
        if dataset.location.lower() != location.lower() or dataset.default_table_expiration_ms is not None:
            raise ValueError("Bronze dataset region/expiry mismatch")
        existing = [table.table_id for table in client.list_tables(dataset)]
        if sum(name.startswith("calendar_events_") for name in existing) >= 5 and snapshot["table_name"] not in existing:
            raise ValueError("Five Calendar snapshots already stored; retention review required")
        result = _verify_load(client, project, location, snapshot)
        print(f"{result['status']} {result['table']} | rows: {result['rows']} | exact values: PASS")
        print("CALENDAR BRONZE PASS. No Calendar edits, Silver changes or Neon writes.")
    except (GoogleAPICallError, GoogleAuthError, ValueError, TimeoutError) as error:
        raise SystemExit(f"CALENDAR LOAD NOT CONFIRMED: {type(error).__name__}. Rerun verifies/reuses; no deletion.") from None
    finally:
        client.close()


if __name__ == "__main__":
    main()
