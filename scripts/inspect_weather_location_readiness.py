"""Read-only, aggregate-only Calendar location coverage for weather planning."""

import argparse
from pathlib import Path

import yaml
from google.cloud import bigquery


ROOT = Path(__file__).resolve().parents[1]
LOCATION = "asia-southeast1"
MAX_BYTES = 100 * 1024 * 1024


def calendar_source_table() -> str:
    sources = yaml.safe_load((ROOT / "dbt/models/operational_sources.yml").read_text(encoding="utf-8"))
    source = next(item for item in sources["sources"] if item["name"] == "calendar_bronze")
    table = next(item for item in source["tables"] if item["name"] == "events")
    return f"`{source['database']}.{source['schema']}.{table['identifier']}`"


def calendar_address_expr(description_text: str) -> str:
    """Keep in sync with dbt/macros/calendar_address_line.sql."""
    return rf"""coalesce(nullif(trim(regexp_replace(
        regexp_extract(replace({description_text}, chr(160), ' '),
            r'(?im)(?:Alamat(?:[*_ ]*[:.]|[ \t]+)|^[ \t*_]*(?:Address(?:es)?|Addres|Full[ \t]+address)[*_ ]*[:.])\s*([^\r\n<]+)'),
        r'(?i)\s+(?:Package|Problem|Invoice(?:\s*id)?|Emel|Email|Phone(?:\s*No)?|Treatment|Nama)\s*:.*$',
        '')), ''),
        nullif(trim(regexp_extract(replace({description_text}, chr(160), ' '),
            r'(?im)^[ \t]*((?:No\.?[ \t]*[0-9]+|Lot[ \t]*[0-9]+|[0-9]+[A-Z]?(?:[-/][A-Z0-9]+)*)(?:[^\r\n<]*?\b(?:Jalan|Jln|Taman|Residensi|Persiaran|Lorong|Road|Street)\b)[^\r\n<]*)'
        )), ''))"""


def query_sql(calendar_table: str, all_dates: bool = False) -> str:
    # A postcode-shaped token is not a validated postcode, much less coordinates.
    date_filter = "" if all_dates else (
        "and e.event_date_local between date '2026-01-01' and date '2026-12-31'"
    )
    return f"""
with prepared as (
    select e.calendar_event_row, e.event_category, m.matched_sales_record_id as sale_id,
        nullif(trim(b.location), '') as calendar_location,
        regexp_replace(regexp_replace(coalesce(b.description, ''),
            r'(?i)</?(?:p|div|li|br)\\b[^>]*>', '\\n'), r'<[^>]+>', '') as description_text
    from `profound-keel-500007-s4.silver.calendar_events` e
    join `profound-keel-500007-s4.silver.calendar_event_matches` m using (calendar_event_row)
    join {calendar_table} b using (calendar_event_row)
    where e.service_candidate
        {date_filter}
), events as (
    select p.*, {calendar_address_expr('p.description_text')} as event_address
    from prepared p
), address_lines as (
    select e.*,
        split(e.description_text, '\\n') as description_lines,
        (select min(line_offset)
         from unnest(split(e.description_text, '\\n')) as line with offset as line_offset
         where regexp_contains(replace(line, chr(160), ' '),
             r'(?i)(?:Alamat(?:[*_ ]*[:.]|[ \\t]+)|^[ \\t*_]*(?:Address(?:es)?|Addres|Full[ \\t]+address)[*_ ]*[:.])'))
            as address_line_offset
    from events e
), locations as (
    select e.calendar_event_row, e.event_category, e.sale_id, e.event_address,
        e.calendar_location, e.description_text,
        e.description_lines[safe_offset(e.address_line_offset + 1)] as next_address_line,
        e.description_lines[safe_offset(e.address_line_offset + 2)] as second_next_address_line,
        regexp_extract(e.event_address, r'\\b[0-9]{{5}}\\b') as event_postcode_shape,
        regexp_extract(e.calendar_location, r'\\b[0-9]{{5}}\\b') as location_postcode_shape,
        regexp_extract(e.description_text, r'\\b[0-9]{{5}}\\b') as description_postcode_shape,
        regexp_extract(s.source_column_011, r'\\b[0-9]{{5}}\\b') as sale_postcode_shape
    from address_lines e
    left join `profound-keel-500007-s4.silver.sales` s
        on e.sale_id = s.sales_record_id
)
select event_category, count(*) as event_rows,
    count(distinct calendar_event_row) as distinct_event_rows,
    countif(sale_id is not null) as linked_sale_rows,
    countif(event_address is not null) as event_address_rows,
    countif(event_postcode_shape is not null) as event_postcode_shape_rows,
    countif(event_postcode_shape is null and calendar_location is not null)
        as no_address_postcode_with_location_text_rows,
    countif(event_postcode_shape is null and location_postcode_shape is not null)
        as no_address_postcode_with_location_postcode_shape_rows,
    countif(event_postcode_shape is null and description_postcode_shape is not null)
        as no_address_postcode_with_any_description_postcode_shape_rows,
    countif(event_postcode_shape is null
        and regexp_contains(coalesce(next_address_line, ''), r'\\b[0-9]{{5}}\\b')
        and not regexp_contains(coalesce(next_address_line, ''),
            r'(?i)^\\s*(?:Phone|No\\.?\\s*Tel|Emel|Email|Invoice|Package|Problem|Treatment)\\b'))
        as no_address_postcode_on_next_unlabelled_line_rows,
    countif(event_postcode_shape is null
        and regexp_contains(coalesce(second_next_address_line, ''), r'\\b[0-9]{{5}}\\b')
        and not regexp_contains(coalesce(second_next_address_line, ''),
            r'(?i)^\\s*(?:Phone|No\\.?\\s*Tel|Emel|Email|Invoice|Package|Problem|Treatment)\\b'))
        as no_address_postcode_on_second_next_unlabelled_line_rows,
    countif(event_postcode_shape is null and event_address is not null
        and regexp_contains(event_address, r'[0-9]')) as no_postcode_address_with_digits_rows,
    countif(sale_postcode_shape is not null) as linked_sale_postcode_shape_rows,
    countif(event_postcode_shape is not null and sale_postcode_shape is not null
        and event_postcode_shape = sale_postcode_shape) as postcode_shapes_agree_rows,
    countif(event_postcode_shape is not null and sale_postcode_shape is not null
        and event_postcode_shape != sale_postcode_shape) as postcode_shapes_disagree_rows,
    countif(event_postcode_shape is null and sale_postcode_shape is not null)
        as sale_only_postcode_shape_rows,
    countif(event_postcode_shape is null and sale_postcode_shape is null)
        as neither_postcode_shape_rows
from locations
group by event_category
order by event_category
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-dates", action="store_true",
                        help="Profile all service-like dates in the pinned Calendar snapshot")
    args = parser.parse_args()
    client = bigquery.Client(project="profound-keel-500007-s4", location=LOCATION)
    try:
        sql = query_sql(calendar_source_table(), all_dates=args.all_dates)
        dry = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        estimate = client.query(sql, job_config=dry, location=LOCATION).total_bytes_processed
        if estimate > MAX_BYTES:
            raise SystemExit(f"Query exceeds 100 MiB safety cap: {estimate:,} bytes")
        print(f"Estimated query bytes: {estimate:,}")
        job = client.query(sql, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION)
        rows = list(job.result())
        if any(row.event_rows != row.distinct_event_rows for row in rows):
            raise SystemExit("Location join expanded Calendar event grain")
        columns = list(rows[0].keys()) if rows else []
        print(" | ".join(columns))
        for row in rows:
            print(" | ".join(str(row[column]) for column in columns))
        print("Postcode-shaped strings are not validated locations or coordinates.")
        print("No address/contact values printed. No source, warehouse, or weather writes.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
