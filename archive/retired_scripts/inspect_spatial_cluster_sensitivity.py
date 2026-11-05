"""Aggregate-only DBSCAN sensitivity summary for repeat-signal service events."""

from google.cloud import bigquery


PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
MAX_BYTES = 100 * 1024 * 1024
SQL = """
select radius_km,
  count(*) as signal_events,
  countif(cluster_id is not null) as clustered_events,
  countif(cluster_id is null) as noise_events,
  count(distinct cluster_id) as clusters
from `profound-keel-500007-s4.gold.spatial_repeat_signal_events`
cross join unnest([
  struct('1' as radius_km, cluster_1km as cluster_id),
  struct('2' as radius_km, cluster_2km as cluster_id),
  struct('5' as radius_km, cluster_5km as cluster_id)
])
group by radius_km
order by cast(radius_km as int64)
"""
AREA_SQL = """
select count(*) as area_cells,
  countif(sufficient_volume_for_comparison) as comparable_cells,
  countif(repeat_signal_event_rows > 0) as cells_with_repeat_signals,
  sum(scheduled_service_event_rows) as scheduled_service_events,
  sum(repeat_signal_event_rows) as repeat_signal_events
from `profound-keel-500007-s4.gold.spatial_service_area_metrics`
"""


def main() -> None:
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        dry = client.query(SQL, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False), location=LOCATION)
        print(f"Estimated query bytes: {dry.total_bytes_processed:,}")
        if dry.total_bytes_processed > MAX_BYTES:
            raise SystemExit("Cluster summary exceeds 100 MiB cap")
        rows = client.query(SQL, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION).result()
        print("radius_km | signal events | clustered | noise | clusters")
        for row in rows:
            print(f"{row.radius_km} | {row.signal_events} | {row.clustered_events} | "
                  f"{row.noise_events} | {row.clusters}")
        area_dry = client.query(AREA_SQL, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False), location=LOCATION)
        if area_dry.total_bytes_processed > MAX_BYTES:
            raise SystemExit("Area summary exceeds 100 MiB cap")
        area = next(iter(client.query(AREA_SQL, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION).result()))
        print(f"Area cells: {area.area_cells}; comparable (>=5 events): {area.comparable_cells}; "
              f"with repeat signals: {area.cells_with_repeat_signals}")
        print(f"Fine-location scheduled events: {area.scheduled_service_events}; "
              f"repeat signals: {area.repeat_signal_events}")
        print("Radius is an analytical sensitivity parameter, not a biological spread radius.")
        print("Aggregate-only; no source or warehouse writes.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
