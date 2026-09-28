"""Validate and load cached daily Open-Meteo ECMWF IFS data to BigQuery Quality."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from fetch_open_meteo_weather import DAILY_FIELDS, LOCATION, OUTPUT, PROJECT


TABLE = f"{PROJECT}.quality.open_meteo_weather_daily_grid_2023_2026_v5"


def expanded_rows(records: list[dict]) -> list[dict]:
    rows = []
    seen_locations: set[str] = set()
    seen_grain: set[tuple[str, str]] = set()
    for record in records:
        location_id = record["weather_location_id"]
        if location_id in seen_locations:
            raise ValueError(f"duplicate weather location {location_id}")
        seen_locations.add(location_id)
        response = record["response"]
        daily = response["daily"]
        dates = daily["time"]
        for index, weather_date in enumerate(dates):
            grain = (location_id, weather_date)
            if grain in seen_grain:
                raise ValueError("weather date grain expanded")
            seen_grain.add(grain)
            row = {
                "weather_location_id": location_id,
                "requested_latitude": record["requested_latitude"],
                "requested_longitude": record["requested_longitude"],
                "grid_latitude": response.get("latitude"),
                "grid_longitude": response.get("longitude"),
                "weather_date": weather_date,
                "weather_model": record["model"],
                "temperature_2m_mean_c": daily["temperature_2m_mean"][index],
                "precipitation_sum_mm": daily["precipitation_sum"][index],
                "rain_sum_mm": daily["rain_sum"][index],
                "relative_humidity_2m_mean_pct": daily["relative_humidity_2m_mean"][index],
                "soil_moisture_0_to_7cm_mean": daily["soil_moisture_0_to_7cm_mean"][index],
            }
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not OUTPUT.exists():
        raise SystemExit("Weather cache missing; no BigQuery write")
    records = [json.loads(line) for line in OUTPUT.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    rows = expanded_rows(records)
    if not rows:
        raise SystemExit("No validated weather rows; no BigQuery write")
    print(f"Cached weather locations: {len(records)}")
    print(f"Daily weather rows: {len(rows)}")
    print("Weather is reanalysis, not a property-level observation.")
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
            bigquery.SchemaField("weather_location_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("requested_latitude", "FLOAT", mode="REQUIRED"),
            bigquery.SchemaField("requested_longitude", "FLOAT", mode="REQUIRED"),
            bigquery.SchemaField("grid_latitude", "FLOAT"),
            bigquery.SchemaField("grid_longitude", "FLOAT"),
            bigquery.SchemaField("weather_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("weather_model", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("temperature_2m_mean_c", "FLOAT"),
            bigquery.SchemaField("precipitation_sum_mm", "FLOAT"),
            bigquery.SchemaField("rain_sum_mm", "FLOAT"),
            bigquery.SchemaField("relative_humidity_2m_mean_pct", "FLOAT"),
            bigquery.SchemaField("soil_moisture_0_to_7cm_mean", "FLOAT"),
        ]
        config = bigquery.LoadJobConfig(
            schema=schema, write_disposition=bigquery.WriteDisposition.WRITE_EMPTY,
            time_partitioning=bigquery.TimePartitioning(field="weather_date"),
            clustering_fields=["weather_location_id"],
        )
        job = client.load_table_from_json(rows, TABLE, job_config=config, location=LOCATION)
        job.result()
        table = client.get_table(TABLE)
        if table.num_rows != len(rows):
            raise SystemExit(f"Row-count verification failed: expected {len(rows)}, stored {table.num_rows}")
        print(f"LOADED {TABLE}: {table.num_rows} rows; row count PASS")
        print(f"Completed UTC: {datetime.now(timezone.utc).isoformat()}")
        print("No source Sheet, Calendar, geocode, or Neon changes.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
