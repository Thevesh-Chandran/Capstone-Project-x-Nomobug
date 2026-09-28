"""Fetch cached historical daily ECMWF IFS weather for service coordinates."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from google.cloud import bigquery


ROOT = Path(__file__).resolve().parents[1]
PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
SOURCE = f"{PROJECT}.quality.calendar_event_geocodes_all_v2"
OUTPUT = ROOT / "data" / "processed" / "weather" / "open_meteo_ifs_grid_2023_2026_v3.jsonl"
API_URL = "https://archive-api.open-meteo.com/v1/archive"
START_DATE = date(2022, 12, 18)  # Supports prior-14-day features for 2023 visits.
END_DATE = date(2026, 9, 14)  # Immutable snapshot boundary.
MAX_BYTES = 100 * 1024 * 1024
DAILY_FIELDS = [
    "temperature_2m_mean", "precipitation_sum", "rain_sum",
    "relative_humidity_2m_mean", "soil_moisture_0_to_7cm_mean",
]


def location_id(latitude: float, longitude: float) -> str:
    value = f"{float(latitude):.5f},{float(longitude):.5f}"
    return hashlib.sha256(value.encode()).hexdigest()


def fetch_locations() -> list[dict]:
    sql = f"""
    -- ECMWF IFS reanalysis is a coarse grid. One request per 0.1-degree
    -- analysis cell avoids pretending that property-level coordinates imply
    -- property-level weather precision.
    select round(latitude, 1) as latitude, round(longitude, 1) as longitude
    from `{SOURCE}`
    group by 1, 2
    order by latitude, longitude
    """
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False), location=LOCATION)
        if dry.total_bytes_processed > MAX_BYTES:
            raise SystemExit("Weather-location query exceeds 100 MiB cap")
        rows = client.query(sql, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION).result()
        locations = [{"latitude": float(row.latitude), "longitude": float(row.longitude)}
                     for row in rows]
        if len({location_id(**item) for item in locations}) != len(locations):
            raise SystemExit("Rounded weather-location grain is not unique")
        return locations
    finally:
        client.close()


def validate_response(payload: dict) -> None:
    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    expected = (END_DATE - START_DATE).days + 1
    if len(dates) != expected or dates[0] != START_DATE.isoformat() or dates[-1] != END_DATE.isoformat():
        raise ValueError("unexpected daily date coverage")
    for field in DAILY_FIELDS:
        if len(daily.get(field) or []) != expected:
            raise ValueError(f"unexpected {field} coverage")


def fetch_batch(items: list[dict]) -> list[dict]:
    params = urllib.parse.urlencode({
        "latitude": ",".join(f"{item['latitude']:.5f}" for item in items),
        "longitude": ",".join(f"{item['longitude']:.5f}" for item in items),
        "start_date": START_DATE.isoformat(), "end_date": END_DATE.isoformat(),
        "daily": ",".join(DAILY_FIELDS), "timezone": "Asia/Kuala_Lumpur",
        "models": "ecmwf_ifs", "cell_selection": "land",
    })
    request = urllib.request.Request(f"{API_URL}?{params}", headers={
        "Accept": "application/json", "User-Agent": "nomobug-capstone-weather/1.0",
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    responses = payload if isinstance(payload, list) else [payload]
    if len(responses) != len(items):
        raise ValueError("unexpected number of location responses")
    records = []
    for item, location_payload in zip(items, responses, strict=True):
        validate_response(location_payload)
        records.append({
            "weather_location_id": location_id(**item),
            "requested_latitude": item["latitude"],
            "requested_longitude": item["longitude"],
            "model": "ecmwf_ifs", "start_date": START_DATE.isoformat(),
            "end_date": END_DATE.isoformat(), "response": location_payload,
        })
    return records


def cached_ids() -> set[str]:
    if not OUTPUT.exists():
        return set()
    return {json.loads(line)["weather_location_id"]
            for line in OUTPUT.read_text(encoding="utf-8").splitlines() if line.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-new-locations", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.max_new_locations <= 1000:
        raise SystemExit("Location cap must be between 1 and 1000")
    locations = fetch_locations()
    cached = cached_ids()
    pending = [item for item in locations if location_id(**item) not in cached]
    selected = pending[:args.max_new_locations]
    print(f"Distinct sanitized coordinates: {len(locations)}")
    print(f"Cached: {len(cached & {location_id(**x) for x in locations})}; pending: {len(pending)}")
    print(f"Would request: {len(selected)} locations, {START_DATE} through {END_DATE}")
    print("Only coordinates are sent; no address or contact fields.")
    if not args.execute:
        print("PLAN ONLY: no Open-Meteo calls or file writes.")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    succeeded = 0
    failed = 0
    failure_reasons: Counter[str] = Counter()
    with OUTPUT.open("a", encoding="utf-8") as handle:
        for start in range(0, len(selected), 10):
            batch = selected[start:start + 10]
            records = None
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    records = fetch_batch(batch)
                    break
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                        ValueError, json.JSONDecodeError) as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(2 ** (attempt + 1))
            if records is None:
                failed += len(batch)
                if isinstance(last_error, urllib.error.HTTPError):
                    reason = f"HTTP_{last_error.code}"
                else:
                    reason = type(last_error).__name__
                failure_reasons[reason] += len(batch)
                continue
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                succeeded += 1
            time.sleep(1.0)
    print(f"Successful weather locations: {succeeded}; failures left uncached: {failed}")
    if failure_reasons:
        print("Failure categories: " + ", ".join(
            f"{key}={failure_reasons[key]}" for key in sorted(failure_reasons)
        ))
    print(f"Private cache: {OUTPUT.relative_to(ROOT)}")
    print("No BigQuery, source Sheet, Calendar, or Neon writes.")


if __name__ == "__main__":
    main()
