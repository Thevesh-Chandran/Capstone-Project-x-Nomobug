"""Export private Calendar review page; no postcode on extracted address line.

This is not a list of unidentifiable addresses. It reads the pinned Bronze
Calendar snapshot and writes only a local, git-ignored HTML report.
"""

import base64
import argparse
from datetime import datetime
import html
from pathlib import Path
from urllib.parse import urlencode

from google.cloud import bigquery

from inspect_weather_location_readiness import (
    MAX_BYTES, ROOT, LOCATION, calendar_address_expr, calendar_source_table,
)


OUTPUT_DIR = ROOT / "data/exports/calendar_review"


def query_sql(calendar_table: str, all_dates: bool = False,
              missing_address_only: bool = False) -> str:
    date_filter = "" if all_dates else (
        "and e.event_date_local between date '2026-01-01' and date '2026-12-31'"
    )
    address_filter = ("event_address_line is null" if missing_address_only else
                      "not regexp_contains(coalesce(event_address_line, ''), r'\\b[0-9]{5}\\b')")
    return f"""
with source_events as (
    select e.calendar_event_row, e.calendar_name, e.event_date_local,
        e.event_category, b.event_id, b.calendar_id, b.summary, b.description,
        b.location,
        m.matched_sales_record_id as sales_record_id,
        regexp_replace(regexp_replace(coalesce(b.description, ''),
            r'(?i)</?(?:p|div|li|br)\\b[^>]*>', '\\n'), r'<[^>]+>', '') as description_text
    from `profound-keel-500007-s4.silver.calendar_events` e
    join `profound-keel-500007-s4.silver.calendar_event_matches` m
        using (calendar_event_row)
    join {calendar_table} b using (calendar_event_row)
    where e.service_candidate
        {date_filter}
), extracted as (
    select *, {calendar_address_expr('description_text')} as event_address_line
    from source_events
)
select calendar_event_row, calendar_name, event_date_local, event_category,
    event_id, calendar_id, summary, description, location, sales_record_id,
    event_address_line,
    regexp_contains(description_text, r'\\b[0-9]{{5}}\\b')
        as postcode_shape_elsewhere_in_description
from extracted
where {address_filter}
order by event_address_line is not null, event_date_local, calendar_name,
    calendar_event_row
"""


def line(value: object) -> str:
    if value is None:
        return "(not recorded)"
    return " ".join(str(value).split()) or "(blank)"


def escape(value: object) -> str:
    return html.escape(str(value or ""))


def calendar_link(event_id: str, calendar_id: str) -> str:
    encoded = base64.urlsafe_b64encode(
        f"{event_id} {calendar_id}".encode("utf-8")
    ).decode("ascii").rstrip("=")
    return "https://calendar.google.com/calendar/event?" + urlencode({"eid": encoded})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-dates", action="store_true")
    parser.add_argument("--missing-address-only", action="store_true")
    args = parser.parse_args()
    client = bigquery.Client(project="profound-keel-500007-s4", location=LOCATION)
    try:
        sql = query_sql(calendar_source_table(), all_dates=args.all_dates,
                        missing_address_only=args.missing_address_only)
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False), location=LOCATION)
        if dry.total_bytes_processed > MAX_BYTES:
            raise SystemExit("Review query exceeds 100 MiB safety cap")
        rows = list(client.query(sql, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION).result())
    finally:
        client.close()

    event_ids = [row.calendar_event_row for row in rows]
    if len(event_ids) != len(set(event_ids)):
        raise SystemExit("Review query expanded Calendar event grain")
    missing_address = sum(row.event_address_line is None for row in rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / (
        ("events_without_extracted_address_" if args.missing_address_only else
         "events_without_address_line_postcode_")
        + datetime.now().strftime("%Y%m%d_%H%M%S") + ".html"
    )
    with path.open("x", encoding="utf-8") as report:
        report.write('''<!doctype html><html lang="en"><meta charset="utf-8">
<title>Nomobug Calendar address review</title>
<style>body{font:16px system-ui;max-width:1000px;margin:32px auto;padding:0 20px;background:#f5f7fa;color:#172330}article{background:white;padding:20px;margin:16px 0;border:1px solid #d9e1e8;border-radius:10px}h2{font-size:19px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px system-ui}summary,a{cursor:pointer;color:#0759a5}</style>
<h1>Calendar address review</h1>
<p>Private review of the stored snapshot. An address without a postcode may still be identifiable. A five-digit token elsewhere in the description may belong to another field, so it is only a review hint. These events are scheduled/recorded, not proof of completed service. Calendar content may have changed since extraction.</p>
<p>Use the event number when reporting a correction. If an event link fails, find it using the date, calendar and title.</p>
''')
        report.write(f"<p>Events: {len(rows)} · No extractable address line: "
                     f"{missing_address} · Address line without token: "
                     f"{len(rows) - missing_address}</p>\n")
        for index, row in enumerate(rows, 1):
            link = (f'<p><a href="{escape(calendar_link(row.event_id, row.calendar_id))}" '
                    'target="_blank" rel="noopener noreferrer">Open in Google Calendar</a></p>') \
                if row.event_id and row.calendar_id else ""
            report.write(f'''<article><h2>{index}. {escape(row.summary) or '(No title)'}</h2>
<p>{escape(row.event_date_local)} · {escape(row.calendar_name)} · {escape(row.event_category)}</p>
<p><strong>Extracted address line:</strong> {escape(row.event_address_line) or '(Not found)'}</p>
<p>Five-digit token elsewhere in description: {'Yes — review context' if row.postcode_shape_elsewhere_in_description else 'No'}</p>
<p>Snapshot event row: {row.calendar_event_row} · Matched Sales ID: {escape(line(row.sales_record_id))}</p>
{link}
<details><summary>Show recorded description and location</summary>
<h3>Description</h3><pre>{escape(row.description) or '(Empty)'}</pre>
<h3>Location</h3><pre>{escape(row.location) or '(Empty)'}</pre></details></article>\n''')
        report.write("</html>\n")
    print(f"Private review list: {path}")
    print(f"Events: {len(rows)} | no address line: {missing_address} "
          f"| address line without five-digit token: {len(rows) - missing_address}")
    print("No Google Sheet, Calendar, BigQuery, Neon, or weather data changed.")


if __name__ == "__main__":
    main()
