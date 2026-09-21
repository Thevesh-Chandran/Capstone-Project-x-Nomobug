"""Read-only Calendar address-block coverage; never sends addresses externally.

Uses the pinned Calendar Bronze snapshot. Raw descriptions are processed only
in memory. Default output is aggregate-only; private review flags print details.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections import defaultdict
import html
import re
import unicodedata

from google.cloud import bigquery

from inspect_weather_location_readiness import (
    LOCATION, MAX_BYTES, calendar_address_expr, calendar_source_table,
)


POSTCODE = re.compile(r"(?<![A-Za-z0-9_])\d{5}(?![A-Za-z0-9_])")
HTML_BREAK = re.compile(r"(?i)</?(?:p|div|li|br)\b[^>]*>")
HTML_TAG = re.compile(r"<[^>]+>")
STOP_FIELD = re.compile(
    r"(?i)^\s*(?:phone|no\.?\s*(?:tel|telefon)|mobile|h/p|emel|e-?mail|"
    r"invoice|inv\b|package|problem|treatment|client(?:s)?\s+update|"
    r"tech(?:s)?\s+update|need\s+to|use\s+trbs|contact)\b"
)
INLINE_FIELD = re.compile(
    r"(?i)\s+(?:package|problem|invoice(?:\s*id)?|emel|e-?mail|"
    r"phone(?:\s*no)?|treatment)\s*:.*$"
)
PHONE_ONLY = re.compile(r"^\s*(?:\+?60|0)[\d\s()\-]{7,}\s*$")
ADDRESS_CUE = re.compile(
    r"(?i)\b(?:jalan|jln|taman|residensi|persiaran|lorong|road|street|"
    r"bandar|kampung|kg\.?|apartment|condo|kuala\s+lumpur|selangor|"
    r"shah\s+alam|putrajaya|sentul|cheras)\b"
)


def clean_lines(description: str | None) -> list[str]:
    text = html.unescape(description or "").replace("\xa0", " ")
    text = HTML_BREAK.sub("\n", text)
    text = HTML_TAG.sub("", text)
    return [line.strip() for line in text.splitlines()]


def address_block(description: str | None, extracted_line: str | None) -> tuple[str | None, str]:
    """Return a cautious contiguous block and why it could not be extended."""
    if not extracted_line:
        return None, "no_extracted_line"
    lines = clean_lines(description)
    first = " ".join(html.unescape(extracted_line).split())
    if not first:
        return None, "no_extracted_line"
    start = next(
        (i for i, line in enumerate(lines) if first.casefold() in " ".join(line.split()).casefold()),
        None,
    )
    if start is None:
        return first, "start_not_found"
    block = [first]
    for line in lines[start + 1 : start + 5]:
        if not line:
            return "\n".join(block), "blank_line"
        if STOP_FIELD.match(line) or "@" in line or PHONE_ONLY.fullmatch(line):
            return "\n".join(block), "contact_or_field"
        if len(line) > 160:
            return "\n".join(block), "long_note"
        if POSTCODE.search(line) or ADDRESS_CUE.search(line) or block[-1].rstrip().endswith(","):
            block.append(INLINE_FIELD.sub("", line).strip())
            continue
        return "\n".join(block), "not_address_like"
    return "\n".join(block), "line_limit"


def normalized_candidate_key(block: str) -> str:
    """Conservative exact-string key, not a confirmed unique property ID."""
    normalized = unicodedata.normalize("NFKC", block).casefold()
    return "".join(char for char in normalized if char.isalnum())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-continuations", action="store_true",
                        help="Print candidate continuation lines for private terminal review")
    parser.add_argument("--review-multi-string-sales", action="store_true",
                        help="Print private address-string variants for linked SALES IDs")
    args = parser.parse_args()
    table = calendar_source_table()
    sql = f"""
    with events as (
        select e.calendar_event_row, e.event_date_local, e.event_category,
            b.summary, b.description, m.match_status, m.matched_sales_record_id,
            regexp_replace(regexp_replace(coalesce(b.description, ''),
                r'(?i)</?(?:p|div|li|br)\\b[^>]*>', '\\n'),
                r'<[^>]+>', '') as description_text
        from `profound-keel-500007-s4.silver.calendar_events` e
        join {table} b using (calendar_event_row)
        join `profound-keel-500007-s4.silver.calendar_event_matches` m
            using (calendar_event_row)
        where e.service_candidate
            and e.event_date_local between date '2026-01-01' and date '2026-12-31'
    )
    select calendar_event_row, event_date_local, event_category, summary,
        description, match_status, matched_sales_record_id,
        {calendar_address_expr('description_text')} as extracted_line
    from events
    order by calendar_event_row
    """
    client = bigquery.Client(project="profound-keel-500007-s4", location=LOCATION)
    try:
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False), location=LOCATION)
        if dry.total_bytes_processed > MAX_BYTES:
            raise SystemExit("Address-block query exceeds 100 MiB safety cap")
        rows = client.query(sql, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION).result()
        counts: Counter[str] = Counter()
        ids: set[int] = set()
        candidate_counts: Counter[str] = Counter()
        keys_by_sale: dict[str, set[str]] = defaultdict(set)
        sales_by_key: dict[str, set[str]] = defaultdict(set)
        events_by_sale_key: dict[tuple[str, str], list[tuple[str, str, str, str]]] = defaultdict(list)
        for row in rows:
            if row.calendar_event_row in ids:
                raise SystemExit("Address-block query expanded Calendar event grain")
            ids.add(row.calendar_event_row)
            block, reason = address_block(row.description, row.extracted_line)
            counts["events"] += 1
            counts[f"stop_{reason}"] += 1
            if not block:
                counts["no_block"] += 1
                continue
            counts["has_block"] += 1
            key = normalized_candidate_key(block)
            if key:
                candidate_counts[key] += 1
                if row.matched_sales_record_id:
                    keys_by_sale[row.matched_sales_record_id].add(key)
                    sales_by_key[key].add(row.matched_sales_record_id)
                    events_by_sale_key[(row.matched_sales_record_id, key)].append((
                        str(row.event_date_local), row.match_status,
                        row.summary or "", block.replace("\n", " | ")))
            if "\n" in block:
                counts["multiline_block"] += 1
            first_line = block.split("\n", 1)[0]
            if POSTCODE.search(first_line):
                counts["postcode_shape_first_line"] += 1
            elif POSTCODE.search(block):
                counts["postcode_shape_continuation_only"] += 1
                if args.review_continuations:
                    print(f"review event {row.calendar_event_row}: {block.splitlines()[-1]}")
            else:
                counts["no_postcode_shape_in_block"] += 1
        if counts["events"] != len(ids):
            raise SystemExit("Calendar event count/ID mismatch")
        counts["normalized_candidate_strings"] = len(candidate_counts)
        counts["candidate_strings_seen_once"] = sum(
            n == 1 for n in candidate_counts.values())
        counts["events_on_repeated_candidate_strings"] = sum(
            n for n in candidate_counts.values() if n > 1)
        counts["linked_sale_ids"] = len(keys_by_sale)
        counts["linked_sale_ids_with_multiple_strings"] = sum(
            len(keys) > 1 for keys in keys_by_sale.values())
        counts["candidate_strings_with_multiple_sale_ids"] = sum(
            len(sale_ids) > 1 for sale_ids in sales_by_key.values())
        for key in (
            "events", "has_block", "no_block", "multiline_block",
            "postcode_shape_first_line", "postcode_shape_continuation_only",
            "no_postcode_shape_in_block", "stop_start_not_found",
            "normalized_candidate_strings", "candidate_strings_seen_once",
            "events_on_repeated_candidate_strings", "linked_sale_ids",
            "linked_sale_ids_with_multiple_strings",
            "candidate_strings_with_multiple_sale_ids",
        ):
            print(f"{key}: {counts[key]}")
        print("Postcode-shaped tokens are candidates, not validated postcodes or coordinates.")
        print("Normalized strings are not verified distinct properties or customers.")
        if args.review_multi_string_sales:
            review_ids = sorted(sale_id for sale_id, keys in keys_by_sale.items() if len(keys) > 1)
            sales_sql = """
            select sales_record_id, source_column_009 as customer_name,
                source_column_004 as closed_date_raw,
                source_column_003 as timestamp_raw,
                source_column_014 as total_sessions_raw
            from `profound-keel-500007-s4.silver.sales`
            where sales_record_id in unnest(@sale_ids)
            order by sales_record_id
            """
            params = [bigquery.ArrayQueryParameter("sale_ids", "STRING", review_ids)]
            review_config = bigquery.QueryJobConfig(query_parameters=params)
            sales_dry_config = bigquery.QueryJobConfig(
                query_parameters=params, dry_run=True, use_query_cache=False)
            sales_dry = client.query(sales_sql, job_config=sales_dry_config,
                                     location=LOCATION)
            if sales_dry.total_bytes_processed > MAX_BYTES:
                raise SystemExit("SALES review query exceeds 100 MiB safety cap")
            review_config.maximum_bytes_billed = MAX_BYTES
            sales_details: dict[str, list] = defaultdict(list)
            for sale in client.query(sales_sql, job_config=review_config,
                                     location=LOCATION).result():
                sales_details[sale.sales_record_id].append(sale)
            for sale_id, keys in sorted(keys_by_sale.items()):
                if len(keys) > 1:
                    print(f"review {sale_id} ({len(keys)} keys):")
                    for sale in sales_details[sale_id]:
                        print(f"  SALE: {sale.customer_name} | closed={sale.closed_date_raw} "
                              f"| timestamp={sale.timestamp_raw} "
                              f"| sessions={sale.total_sessions_raw}")
                    for key in sorted(keys):
                        events = sorted(events_by_sale_key[(sale_id, key)])
                        methods = dict(sorted(Counter(event[1] for event in events).items()))
                        print(f"  {len(events)} events, {events[0][0]}..{events[-1][0]}, "
                              f"match={methods}")
                        print(f"    first: {events[0][2]}")
                        if len(events) > 1:
                            print(f"    last: {events[-1][2]}")
                        print(f"    address: {events[0][3]}")
        if not (args.review_continuations or args.review_multi_string_sales):
            print("No addresses printed or saved.")
        print("No source, weather, or geocoder writes.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
