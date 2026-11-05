"""Read-only private terminal review of competing SALES for linked Calendar events.

Uses the pinned Silver views. Prints personal details only when explicitly run
with sale IDs; never writes source, warehouse, or local exports.
"""

from __future__ import annotations

import argparse

from google.cloud import bigquery

from inspect_weather_location_readiness import LOCATION, MAX_BYTES, calendar_source_table


PROJECT = "profound-keel-500007-s4"


def run_capped(client: bigquery.Client, sql: str, params: list) -> list:
    dry_config = bigquery.QueryJobConfig(
        query_parameters=params, dry_run=True, use_query_cache=False)
    dry = client.query(sql, job_config=dry_config, location=LOCATION)
    if dry.total_bytes_processed > MAX_BYTES:
        raise SystemExit("Review query exceeds 100 MiB safety cap")
    config = bigquery.QueryJobConfig(
        query_parameters=params, maximum_bytes_billed=MAX_BYTES)
    return list(client.query(sql, job_config=config, location=LOCATION).result())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sale_ids", nargs="+", help="SALES IDs to inspect privately")
    args = parser.parse_args()
    ids = sorted(set(args.sale_ids))
    params = [bigquery.ArrayQueryParameter("sale_ids", "STRING", ids)]
    events_sql = f"""
    select m.matched_sales_record_id as current_sale_id, m.calendar_event_row,
        m.event_date_local, m.match_status, m.invoice_match_count,
        m.phone_date_session_match_count, m.calendar_sequence_anchor_match_count,
        m.phone_match_count, m.email_match_count, m.address_match_count,
        b.summary
    from `{PROJECT}.silver.calendar_event_matches` m
    join {calendar_source_table()} b using (calendar_event_row)
    where m.matched_sales_record_id in unnest(@sale_ids)
      and m.event_date_local between date '2026-01-01' and date '2026-12-31'
      and m.service_candidate
    order by current_sale_id, event_date_local, calendar_event_row
    """
    sales_sql = f"""
    with sales as (
      select sales_record_id, source_column_009 as customer_name,
          source_column_010 as phone_raw, source_column_011 as address_raw,
          source_column_003 as timestamp_raw, source_column_004 as closed_date_raw,
          source_column_014 as total_sessions_raw,
          source_column_026 as package_type_raw
      from `{PROJECT}.silver.sales`
      where sales_record_id is not null
    ), phone_pieces as (
      select s.*, piece, regexp_replace(piece, r'[^0-9]', '') as digits
      from sales s,
      unnest(regexp_extract_all(coalesce(phone_raw, ''),
          r'\\+?[0-9][0-9 \\t().\\-]*[0-9]')) piece
    ), keyed as (
      select *, case
          when regexp_contains(digits, r'^01[0-9]{{8,9}}$')
              then concat('+60', substr(digits, 2))
          when regexp_contains(digits, r'^601[0-9]{{8,9}}$')
              then concat('+', digits)
          when starts_with(trim(piece), '+')
              and regexp_contains(digits, r'^[1-9][0-9]{{7,14}}$')
              then concat('+', digits)
        end as phone_key
      from phone_pieces
    ), targets as (
      select distinct sales_record_id as target_id, phone_key
      from keyed where sales_record_id in unnest(@sale_ids) and phone_key is not null
    )
    select distinct t.target_id, k.sales_record_id as candidate_id,
        k.customer_name, k.timestamp_raw, k.closed_date_raw,
        k.total_sessions_raw, k.package_type_raw, k.address_raw
    from targets t join keyed k using (phone_key)
    order by target_id, timestamp_raw, candidate_id
    """
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        events = run_capped(client, events_sql, params)
        candidates = run_capped(client, sales_sql, params)
        for sale_id in ids:
            print(f"\n{sale_id}")
            case_events = [e for e in events if e.current_sale_id == sale_id]
            case_candidates = [c for c in candidates if c.target_id == sale_id]
            print(f"  2026 linked service candidates: {len(case_events)}")
            for event in case_events:
                print(f"  event {event.calendar_event_row} | {event.event_date_local} "
                      f"| {event.match_status} | {event.summary}")
            print(f"  SALES sharing a parsed phone: {len(set(c.candidate_id for c in case_candidates))}")
            for candidate in case_candidates:
                print(f"  sale {candidate.candidate_id} | {candidate.customer_name} "
                      f"| closed={candidate.closed_date_raw} "
                      f"| timestamp={candidate.timestamp_raw} "
                      f"| sessions={candidate.total_sessions_raw} "
                      f"| package={candidate.package_type_raw} "
                      f"| address={candidate.address_raw}")
        print("Read-only; no source, warehouse, weather, or geocoder writes.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
