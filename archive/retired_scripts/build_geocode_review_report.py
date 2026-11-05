"""Build a private local HTML review of Geoapify candidate quality.

The report contains sanitized address candidates and provider-formatted matches,
so it must remain in the git-ignored data/exports/calendar_review directory.
It performs no API or warehouse writes.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
import html
import json
from pathlib import Path
import re
from urllib.parse import quote

from google.cloud import bigquery

from pilot_geoapify_calendar import (
    OUTPUT, POSTCODE, analysis_tier, fetch_candidates, precision_tier,
)
from inspect_weather_location_readiness import LOCATION, MAX_BYTES, calendar_source_table


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "exports" / "calendar_review" / "geocode_quality_review_latest.html"
MISSING_REPORT = (ROOT / "data" / "exports" / "calendar_review" /
                  "geocode_missing_candidate_review_latest.html")


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def main() -> None:
    candidates = fetch_candidates(date(2023, 1, 1), date(2026, 12, 31))
    records = [json.loads(line) for line in OUTPUT.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    by_hash = {record["address_hash"]: record for record in records}
    rows = []
    counts: Counter[str] = Counter()
    represented_events: set[int] = set()
    for address_hash, candidate in candidates.items():
        record = by_hash.get(address_hash)
        event_rows = candidate["event_rows"]
        represented_events.update(event_rows)
        if record is None:
            tier = "provider_unresolved"
            reason = "No cached provider response"
        else:
            property_tier = precision_tier(
                record.get("result_type"), record.get("postcode_agrees"),
                record.get("confidence"),
            )
            tier = analysis_tier(record)
            reasons = []
            has_coordinates = (record.get("latitude") is not None
                               and record.get("longitude") is not None)
            if record.get("result_count", 0) == 0:
                reasons.append("No provider result or coordinates")
            if record.get("postcode_agrees") is False:
                reasons.append("Coordinate returned, but provider postcode disagrees")
            postcode_distance = record.get("postcode_reference_distance_km")
            if (tier == "manual_review" and postcode_distance is not None
                    and postcode_distance > 10):
                reasons.append(
                    f"Provider point is {postcode_distance:.1f} km from the trusted "
                    "centre of matching addresses in the input postcode"
                )
            if tier == "postcode_area_candidate":
                reasons.append(
                    "Ready for weather/heatmap with a wide uncertainty radius; not an exact property point"
                )
            if tier == "area_analysis_candidate":
                reasons.append(
                    "Ready for weather/heatmap at building/street area level; not verified for routing"
                )
            if tier == "text_agreement_candidate":
                reasons.append(
                    "Meaningful normalized address components agree; postcode absence/conflict is retained as uncertainty"
                )
            if tier == "proximity_candidate":
                reasons.append(
                    "Provider point is within 5 km of the trusted median for the input postcode; retained only as a coarse area candidate"
                )
            if tier == "peer_address_candidate":
                reasons.append(
                    "Matched to a strongly similar address already geocoded elsewhere in the Calendar dataset"
                )
            if tier == "google_hinted_area_candidate":
                reasons.append(
                    "Google supplied a transient locality hint that Geoapify independently resolved; suitable for weather-area analysis only"
                )
            if tier == "manual_verified":
                reasons.append(
                    "Coordinates supplied and verified manually; protected from automatic geocoding replacement"
                )
            if tier == "area_reference_verified":
                reasons.append(
                    "Street-area coordinate corroborated by external address references; suitable for weather-area analysis, not exact routing"
                )
            if (tier == "manual_review" and has_coordinates
                    and record.get("postcode_agrees") is not False):
                reasons.append(
                    "Coordinate returned, but precision/confidence is below the automatic rule"
                )
            reason = "; ".join(reasons) or "Passed automatic coordinate rule"
        counts[tier] += 1
        needs_review = tier in {
            "manual_review", "provider_unresolved", "google_hinted_area_candidate"
        }
        if needs_review:
            status = "REVIEW"
        elif tier in {"postcode_area_candidate", "area_analysis_candidate",
                      "text_agreement_candidate", "proximity_candidate",
                      "peer_address_candidate", "area_reference_verified"}:
            status = "AREA READY"
        elif tier == "manual_verified":
            status = "MANUAL PASS"
        else:
            status = "PASS"
        rows.append({
            "needs_review": needs_review,
            "status": status,
            "tier": tier,
            "property_tier": "provider_unresolved" if record is None else property_tier,
            "reason": reason,
            "event_count": len(event_rows),
            "input_address": candidate["address"],
            "provider_address": None if record is None else record.get("formatted"),
            "result_type": None if record is None else record.get("result_type"),
            "confidence": None if record is None else record.get("confidence"),
            "postcode_distance_km": (
                None if record is None else record.get("postcode_reference_distance_km")
            ),
            "postcode_agrees": None if record is None else record.get("postcode_agrees"),
            "coordinates_returned": bool(record and record.get("latitude") is not None
                                         and record.get("longitude") is not None),
        })
    rows.sort(key=lambda row: (not row["needs_review"], row["tier"], row["input_address"].lower()))
    review_count = sum(row["needs_review"] for row in rows)
    review_rows = [row for row in rows if row["needs_review"]]
    coordinate_count = sum(row["coordinates_returned"] for row in rows)
    without_postcode = [row for row in rows if not POSTCODE.search(row["input_address"])]
    without_postcode_coordinates = sum(row["coordinates_returned"] for row in without_postcode)
    body_rows = "\n".join(
        "<tr class='{}'><td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
        "<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
        "<td>{}</td><td>{}</td></tr>".format(
            "review" if row["needs_review"] else "accepted",
            esc(row["status"]), esc(row["tier"]), esc(row["property_tier"]),
            esc(row["reason"]), row["event_count"],
            esc(row["input_address"]), esc(row["provider_address"]),
            "Yes" if row["coordinates_returned"] else "No",
            esc(row["result_type"]), esc(row["confidence"]),
            ("" if row["postcode_distance_km"] is None
             else f'{row["postcode_distance_km"]:.1f} km'),
            (f'<a href="https://www.google.com/maps/search/?api=1&amp;query='
             f'{quote(row["input_address"])}" target="_blank" rel="noopener">Search map</a>'),
        ) for row in review_rows
    )
    summary = ", ".join(f"{esc(key)}={value}" for key, value in sorted(counts.items()))
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Geoapify quality review</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #18212b; }}
.summary {{ background: #eef5ff; border: 1px solid #bfd5f5; padding: 14px; margin-bottom: 18px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border: 1px solid #ccd4dd; padding: 7px; text-align: left; vertical-align: top; }}
th {{ position: sticky; top: 0; background: #243447; color: white; }}
tr.review {{ background: #fff0f0; }} tr.accepted {{ background: #f4fff6; }}
input {{ width: 420px; padding: 8px; margin: 8px 0 14px; }}
</style></head><body>
<h1>Geoapify geocoding quality review</h1>
<div class="summary"><b>Generated:</b> {esc(datetime.now().isoformat(timespec='seconds'))}<br>
<b>Candidate addresses:</b> {len(rows)} &nbsp; <b>Calendar event rows represented:</b> {len(represented_events)}<br>
<b>Showing only addresses that need review:</b> {review_count}<br>
The normalized address-agreement rule is applied to every candidate address; the examples used to test it are not special-case exceptions.<br>
<b>All-candidate precision tiers:</b> {summary}<br>
<b>Coordinates returned:</b> {coordinate_count} of {len(rows)} addresses.<br>
<b>Without an input postcode:</b> {without_postcode_coordinates} of {len(without_postcode)}
still received coordinates.<br>
Coordinates are provider candidates, not verified service properties. No warehouse write was performed.</div>
<label><b>Search:</b></label><br><input id="q" placeholder="address, tier, reason..." oninput="filterRows()">
<table id="results"><thead><tr><th>Status</th><th>Analysis tier</th><th>Property tier</th>
<th>Reason</th><th>Events</th>
<th>Sanitized input</th><th>Geoapify match</th><th>Coordinates returned?</th>
<th>Result type</th><th>Confidence</th><th>Postcode-area distance</th><th>Map check</th></tr></thead>
<tbody>{body_rows}</tbody></table>
<script>function filterRows(){{const q=document.getElementById('q').value.toLowerCase();
document.querySelectorAll('#results tbody tr').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(q)?'':'none');}}</script>
</body></html>"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(document, encoding="utf-8")
    source = calendar_source_table()
    sql = f"""
    select e.calendar_event_row, e.event_date_local, e.calendar_name,
           b.summary, b.location, b.description
    from `profound-keel-500007-s4.silver.calendar_events` e
    join {source} b using (calendar_event_row)
    where e.service_candidate
    order by e.event_date_local, e.calendar_event_row
    """
    client = bigquery.Client(project="profound-keel-500007-s4", location=LOCATION)
    try:
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False), location=LOCATION)
        if dry.total_bytes_processed > MAX_BYTES:
            raise SystemExit("Missing-candidate review query exceeds 100 MiB cap")
        all_events = client.query(sql, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION).result()
        missing = [dict(row) for row in all_events
                   if int(row.calendar_event_row) not in represented_events]
    finally:
        client.close()
    postcode = re.compile(r"\b\d{5}\b")
    location_rows = sum(bool((row.get("location") or "").strip()) for row in missing)
    description_rows = sum(bool((row.get("description") or "").strip()) for row in missing)
    postcode_rows = sum(bool(postcode.search(
        f"{row.get('location') or ''} {row.get('description') or ''}")) for row in missing)
    missing_body = "\n".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td><pre>{}</pre></td>"
        "<td><pre>{}</pre></td></tr>".format(
            esc(row["calendar_event_row"]), esc(row["event_date_local"]),
            esc(row["calendar_name"]), esc(row["summary"]),
            esc(row["location"]), esc(row["description"]),
        ) for row in missing
    )
    missing_document = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Events without geocode candidate</title><style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #18212b; }}
.summary {{ background:#fff4d6; border:1px solid #e2bd58; padding:14px; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; }}
th,td {{ border:1px solid #ccd4dd; padding:7px; text-align:left; vertical-align:top; }}
th {{ position:sticky; top:0; background:#243447; color:white; }}
pre {{ white-space:pre-wrap; max-width:620px; margin:0; font:inherit; }}
input {{ width:420px; padding:8px; margin:12px 0; }}</style></head><body>
<h1>Service events without a safe geocode candidate</h1><div class="summary">
<b>Missing candidate events:</b> {len(missing)}<br>
Location field populated: {location_rows}; description populated: {description_rows};
 five-digit token present: {postcode_rows}.<br>
These rows were not sent to Geoapify. Review whether an address exists in an
unrecognised format or is genuinely absent.</div>
<input id="q" placeholder="search title, date, description..." oninput="filterRows()">
<table id="results"><thead><tr><th>Row</th><th>Date</th><th>Calendar</th><th>Title</th>
<th>Location</th><th>Description</th></tr></thead><tbody>{missing_body}</tbody></table>
<script>function filterRows(){{const q=document.getElementById('q').value.toLowerCase();
document.querySelectorAll('#results tbody tr').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(q)?'':'none');}}</script>
</body></html>"""
    MISSING_REPORT.write_text(missing_document, encoding="utf-8")
    print(f"WROTE {REPORT}")
    print(f"Candidates: {len(rows)}; review: {review_count}; represented events: {len(represented_events)}")
    print(f"WROTE {MISSING_REPORT}")
    print(f"Missing candidates: {len(missing)}; location={location_rows}; description={description_rows}; postcode-token={postcode_rows}")
    print("No API or warehouse writes.")


if __name__ == "__main__":
    main()
