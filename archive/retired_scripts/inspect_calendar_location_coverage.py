"""Aggregate-only coverage of usable Calendar coordinates by event category."""

from google.cloud import bigquery


PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
MAX_BYTES = 100 * 1024 * 1024
SQL = """
select
  event_category,
  count(*) as event_rows,
  countif(latitude is not null) as any_usable_location,
  countif(heatmap_eligible) as heatmap_location,
  countif(weather_eligible) as weather_location,
  countif(warranty_claim_candidate) as repeat_signal_rows,
  countif(warranty_claim_candidate and heatmap_eligible) as repeat_signal_with_heatmap_location
from `profound-keel-500007-s4.gold.calendar_service_event_facts`
where event_date_local between date '2026-01-01' and date '2026-12-31'
group by event_category
order by event_category
"""
WEATHER_SQL = """
select
  coalesce(weather_coverage_status, 'no_usable_location') as weather_status,
  count(*) as event_rows,
  countif(warranty_claim_candidate) as repeat_signal_rows,
  countif(warranty_claim_candidate and complete_prior_14d_weather) as repeat_with_complete_14d
from `profound-keel-500007-s4.gold.calendar_service_event_facts`
where event_date_local between date '2026-01-01' and date '2026-12-31'
group by weather_status
order by weather_status
"""


def main() -> None:
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        dry = client.query(SQL, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False), location=LOCATION)
        print(f"Estimated query bytes: {dry.total_bytes_processed:,}")
        if dry.total_bytes_processed > MAX_BYTES:
            raise SystemExit("Coverage query exceeds 100 MiB cap")
        rows = client.query(SQL, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION).result()
        print("category | events | usable | heatmap | weather | repeat signals | repeat with heatmap")
        for row in rows:
            print(f"{row.event_category} | {row.event_rows} | {row.any_usable_location} | "
                  f"{row.heatmap_location} | {row.weather_location} | {row.repeat_signal_rows} | "
                  f"{row.repeat_signal_with_heatmap_location}")
        weather_dry = client.query(WEATHER_SQL, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False), location=LOCATION)
        if weather_dry.total_bytes_processed > MAX_BYTES:
            raise SystemExit("Weather coverage query exceeds 100 MiB cap")
        print("weather status | events | repeat signals | repeat with complete prior 14d")
        weather_rows = client.query(WEATHER_SQL, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION).result()
        for row in weather_rows:
            print(f"{row.weather_status} | {row.event_rows} | {row.repeat_signal_rows} | "
                  f"{row.repeat_with_complete_14d}")
        print("Scheduled entries are not proof of completed treatment or repeat infestation.")
        print("Aggregate-only; no source, geocoder, or weather writes.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
