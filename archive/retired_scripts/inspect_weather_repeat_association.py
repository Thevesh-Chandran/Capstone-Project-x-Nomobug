"""Aggregate descriptive weather comparison for complete-coverage Calendar events."""

from google.cloud import bigquery


PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
MAX_BYTES = 100 * 1024 * 1024
SQL = """
select
  if(warranty_claim_candidate, 'warranty_claim_candidate', 'normal_scheduled_service') as event_group,
  count(*) as event_rows,
  round(avg(prior_3d_precipitation_mm), 2) as avg_prior_3d_rain_mm,
  round(avg(prior_7d_precipitation_mm), 2) as avg_prior_7d_rain_mm,
  round(avg(prior_14d_precipitation_mm), 2) as avg_prior_14d_rain_mm,
  round(avg(prior_7d_relative_humidity_mean_pct), 2) as avg_prior_7d_humidity_pct,
  round(avg(prior_7d_soil_moisture_0_to_7cm_mean), 4) as avg_prior_7d_soil_moisture
from `profound-keel-500007-s4.gold.calendar_service_event_facts`
where complete_prior_14d_weather
  and event_date_local between date '2026-01-15' and date '2026-09-14'
group by event_group
order by event_group
"""


def main() -> None:
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        dry = client.query(SQL, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False), location=LOCATION)
        print(f"Estimated query bytes: {dry.total_bytes_processed:,}")
        if dry.total_bytes_processed > MAX_BYTES:
            raise SystemExit("Weather comparison exceeds 100 MiB cap")
        rows = client.query(SQL, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION).result()
        print("group | rows | rain 3d | rain 7d | rain 14d | humidity 7d | soil moisture 7d")
        for row in rows:
            print(f"{row.event_group} | {row.event_rows} | {row.avg_prior_3d_rain_mm} | "
                  f"{row.avg_prior_7d_rain_mm} | {row.avg_prior_14d_rain_mm} | "
                  f"{row.avg_prior_7d_humidity_pct} | {row.avg_prior_7d_soil_moisture}")
        print("Descriptive association only; no adjustment for season, area, service mix, or repeated properties.")
        print("Scheduled Calendar entries are not confirmed completed treatments or infestations.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
