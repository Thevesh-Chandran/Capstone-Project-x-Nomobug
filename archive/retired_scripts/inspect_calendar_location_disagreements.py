"""Read-only private review of Calendar/SALES postcode-shaped disagreements.

The Calendar event address is the candidate physical visit location; the linked
SALES address describes a package and may legitimately be different. No output
is saved, sent to a geocoder, or written to BigQuery.
"""

from google.cloud import bigquery

from inspect_calendar_address_blocks import address_block
from inspect_weather_location_readiness import (
    LOCATION, MAX_BYTES, calendar_address_expr, calendar_source_table,
)


PROJECT = "profound-keel-500007-s4"


def main() -> None:
    sql = f"""
    with source_events as (
        select e.calendar_event_row, e.event_date_local, b.summary,
            b.description, m.matched_sales_record_id,
            s.address_raw as sale_address,
            regexp_replace(regexp_replace(coalesce(b.description, ''),
                r'(?i)</?(?:p|div|li|br)\\b[^>]*>', '\\n'),
                r'<[^>]+>', '') as description_text
        from `{PROJECT}.silver.calendar_events` e
        join {calendar_source_table()} b using (calendar_event_row)
        join `{PROJECT}.silver.calendar_event_matches` m
            using (calendar_event_row)
        left join `{PROJECT}.silver.sales` s
            on s.sales_record_id = m.matched_sales_record_id
        where e.service_candidate
            and e.event_date_local between date '2026-01-01' and date '2026-12-31'
    ), extracted as (
        select *, {calendar_address_expr('description_text')} as event_address
        from source_events
    ), postcodes as (
        select *, regexp_extract(event_address, r'\\b[0-9]{{5}}\\b')
            as event_postcode_shape,
            regexp_extract(sale_address, r'\\b[0-9]{{5}}\\b')
            as sale_postcode_shape
        from extracted
    )
    select calendar_event_row, event_date_local, summary, description,
        matched_sales_record_id, event_address, sale_address,
        event_postcode_shape, sale_postcode_shape
    from postcodes
    where event_postcode_shape is not null and sale_postcode_shape is not null
        and event_postcode_shape != sale_postcode_shape
    order by event_date_local, calendar_event_row
    """
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False), location=LOCATION)
        if dry.total_bytes_processed > MAX_BYTES:
            raise SystemExit("Location disagreement query exceeds 100 MiB cap")
        rows = list(client.query(sql, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION).result())
        if len({row.calendar_event_row for row in rows}) != len(rows):
            raise SystemExit("Location disagreement query expanded event grain")
        print(f"Disagreements: {len(rows)} Calendar event rows")
        for row in rows:
            block, _ = address_block(row.description, row.event_address)
            print(f"\nevent {row.calendar_event_row} | {row.event_date_local} "
                  f"| sale {row.matched_sales_record_id} | {row.summary}")
            print(f"  visit postcode-shaped: {row.event_postcode_shape} "
                  f"| Calendar address: {block or row.event_address}")
            print(f"  sale postcode-shaped: {row.sale_postcode_shape} "
                  f"| SALES address: {row.sale_address}")
        print("Postcode-shaped tokens are not validated postcodes or coordinates.")
        print("No source, warehouse, weather, or geocoder writes.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
