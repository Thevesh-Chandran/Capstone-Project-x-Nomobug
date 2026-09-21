"""Validate and load historical Calendar geocode candidates to BigQuery Quality."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone

from google.cloud import bigquery
from google.api_core.exceptions import NotFound

from pilot_geoapify_calendar import OUTPUT, analysis_tier, fetch_candidates


PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
TABLE = f"{PROJECT}.quality.calendar_event_geocodes_all_v2"
USABLE_TIERS = {
    "precise_candidate", "street_candidate", "postcode_area_candidate",
    "area_analysis_candidate", "text_agreement_candidate", "proximity_candidate",
    "peer_address_candidate", "google_hinted_area_candidate",
    "manual_verified", "area_reference_verified",
}
MALAYSIA_BOUNDS = (0.5, 7.6, 99.0, 120.0)


def sanitized_rows(records: list[dict], candidates: dict[str, dict] | None = None) -> list[dict]:
    rows: list[dict] = []
    seen_events: set[int] = set()
    for record in records:
        tier = analysis_tier(record)
        if tier not in USABLE_TIERS:
            continue
        latitude = record.get("latitude")
        longitude = record.get("longitude")
        if latitude is None or longitude is None:
            continue
        latitude = float(latitude)
        longitude = float(longitude)
        min_lat, max_lat, min_lon, max_lon = MALAYSIA_BOUNDS
        if not (min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon):
            continue
        candidate = (candidates or {}).get(record.get("address_hash"))
        if candidate is None:
            # Backward-compatible pure validation path used by unit tests and
            # older one-shot caches. Production loading always supplies the
            # freshly queried candidate mapping.
            candidate = {"event_rows": record.get("calendar_event_rows") or []}
        # Rejoin the current Calendar snapshot by sanitized address hash. This
        # safely reuses one provider result across historical visits without
        # trusting the event-row list captured during an earlier pilot run.
        for event_row in candidate["event_rows"]:
            event_row = int(event_row)
            if event_row in seen_events:
                raise ValueError(f"Calendar event grain expanded at row {event_row}")
            seen_events.add(event_row)
            rows.append({
                "calendar_event_row": event_row,
                "address_hash": record["address_hash"],
                "latitude": latitude,
                "longitude": longitude,
                "geocode_provider": (
                    "manual"
                    if record.get("coordinate_source") == "manual_user_verified"
                    else "external_reference"
                    if record.get("coordinate_source") == "external_area_reference"
                    else record.get("provider") or "geoapify"
                ),
                "coordinate_source": record.get("coordinate_source") or record.get("provider") or "geoapify",
                "manual_override_protected": bool(record.get("manual_override_protected")),
                "precision_tier": tier,
                "provider_result_type": record.get("result_type"),
                "provider_confidence": record.get("confidence"),
                "postcode_agrees": record.get("postcode_agrees"),
                "geocoded_at_utc": record.get("geocoded_at_utc"),
            })
    return sorted(rows, key=lambda item: item["calendar_event_row"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2023, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 12, 31))
    args = parser.parse_args()
    if not OUTPUT.exists():
        raise SystemExit("Private Geoapify cache not found; no BigQuery write")
    records = [json.loads(line) for line in OUTPUT.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    candidates = fetch_candidates(args.start_date, args.end_date)
    rows = sanitized_rows(records, candidates)
    if not rows:
        raise SystemExit("No validated coordinate candidates; no BigQuery write")
    print(f"Sanitized event-coordinate rows: {len(rows)}")
    print("Raw addresses and contact fields excluded.")
    if not args.execute:
        print(f"PLAN ONLY: would create new table {TABLE}; no warehouse write.")
        return

    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        try:
            client.get_table(TABLE)
        except NotFound:
            pass
        else:
            raise SystemExit(f"Target already exists: {TABLE}; refusing to overwrite")
        schema = [
            bigquery.SchemaField("calendar_event_row", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("address_hash", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("latitude", "FLOAT", mode="REQUIRED"),
            bigquery.SchemaField("longitude", "FLOAT", mode="REQUIRED"),
            bigquery.SchemaField("geocode_provider", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("coordinate_source", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("manual_override_protected", "BOOLEAN", mode="REQUIRED"),
            bigquery.SchemaField("precision_tier", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("provider_result_type", "STRING"),
            bigquery.SchemaField("provider_confidence", "FLOAT"),
            bigquery.SchemaField("postcode_agrees", "BOOLEAN"),
            bigquery.SchemaField("geocoded_at_utc", "TIMESTAMP"),
        ]
        config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_EMPTY,
        )
        job = client.load_table_from_json(rows, TABLE, job_config=config, location=LOCATION)
        job.result()
        table = client.get_table(TABLE)
        if table.num_rows != len(rows):
            raise SystemExit(f"Row-count verification failed: expected {len(rows)}, stored {table.num_rows}")
        print(f"LOADED {TABLE}: {table.num_rows} rows; row count PASS")
        print(f"Completed UTC: {datetime.now(timezone.utc).isoformat()}")
        print("Source Calendar and Sales unchanged. No weather writes.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
