"""Build a private review page for Geoapify points validated within 1 km.

Google Places coordinates are requested only for an in-memory distance
calculation.  The output stores the derived distance, the existing sanitized
input address, and the stored Geoapify match; it never stores Google
coordinates, place IDs, formatted addresses, or raw responses.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import html
import json
import os
from pathlib import Path
import time
from urllib.parse import quote

from dotenv import load_dotenv

from annotate_geoapify_postcode_proximity import haversine_km
from pilot_geoapify_calendar import ROOT
from retry_geocodes_with_google_place_hints import (
    GooglePlacesRequestError,
    google_places,
    select_place_hint,
)


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v11.jsonl"
REPORT = (
    ROOT
    / "data"
    / "exports"
    / "calendar_review"
    / "google_geoapify_within_1km_review_latest.html"
)


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def distance_band(distance_m: float) -> str:
    if distance_m <= 250:
        return "0–250 m"
    if distance_m <= 500:
        return "251–500 m"
    return "501–1,000 m"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not SOURCE.is_file():
        raise SystemExit("Geoapify v11 cache is missing; no report generated")

    records = [
        json.loads(line)
        for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = [
        record
        for record in records
        if record.get("google_place_within_1km") is True
        and record.get("latitude") is not None
        and record.get("longitude") is not None
    ]
    print(f"Selected within-1-km candidates: {len(selected)}")
    if not args.execute:
        print(f"PLAN ONLY: would write {REPORT.relative_to(ROOT)}")
        return

    load_dotenv(ROOT / ".env")
    google_key = os.getenv("NOMOBUG_GOOGLE_MAPS_API_KEY", "").strip()
    if not google_key:
        raise SystemExit("Missing private Google Maps key; no report generated")

    rows: list[dict] = []
    outcomes: Counter[str] = Counter()
    for index, record in enumerate(selected, start=1):
        try:
            places = google_places(
                record["input_address"], google_key, include_location=True
            )
            place = select_place_hint(record["input_address"], places)
            location = None if place is None else place.get("location") or {}
            if not location or location.get("latitude") is None or location.get("longitude") is None:
                outcomes["no_safe_google_location"] += 1
                continue
            distance_km = haversine_km(
                float(record["latitude"]),
                float(record["longitude"]),
                float(location["latitude"]),
                float(location["longitude"]),
            )
            distance_m = distance_km * 1000
            if distance_m > 1000:
                # Provider search results can change. Keep changed results out of
                # the within-1-km report rather than presenting stale acceptance.
                outcomes["now_over_1km"] += 1
                continue
            band = distance_band(distance_m)
            outcomes[band] += 1
            rows.append(
                {
                    "input_address": record["input_address"],
                    "geoapify_address": record.get("formatted") or "",
                    "distance_m": distance_m,
                    "band": band,
                    "event_count": len(record.get("calendar_event_rows") or []),
                    "result_type": record.get("result_type") or "",
                    "confidence": record.get("confidence"),
                }
            )
        except GooglePlacesRequestError as exc:
            outcomes[f"google_{exc}"] += 1
        if index % 20 == 0:
            print(f"Processed {index} of {len(selected)}")
        time.sleep(0.15)

    rows.sort(key=lambda row: (-row["distance_m"], row["input_address"].lower()))
    body_rows = "\n".join(
        "<tr><td>{}</td><td>{:.0f} m</td><td>{}</td><td>{}</td><td>{}</td>"
        "<td>{}</td><td>{}</td><td><a href=\"https://www.google.com/maps/search/?api=1&amp;query={}\" "
        "target=\"_blank\" rel=\"noopener\">Input map</a> · "
        "<a href=\"https://www.google.com/maps/search/?api=1&amp;query={}\" "
        "target=\"_blank\" rel=\"noopener\">Geoapify map</a></td></tr>".format(
            esc(row["band"]),
            row["distance_m"],
            row["event_count"],
            esc(row["input_address"]),
            esc(row["geoapify_address"]),
            esc(row["result_type"]),
            "" if row["confidence"] is None else f'{row["confidence"]:.3f}',
            quote(row["input_address"]),
            quote(row["geoapify_address"]),
        )
        for row in rows
    )
    summary = " &nbsp; ".join(
        f"<b>{esc(band)}:</b> {outcomes[band]}"
        for band in ("0–250 m", "251–500 m", "501–1,000 m")
    )
    represented_events = sum(row["event_count"] for row in rows)
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Google–Geoapify distance review</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #18212b; }}
.summary {{ background:#eef5ff; border:1px solid #bfd5f5; padding:14px; margin-bottom:18px; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; }}
th,td {{ border:1px solid #ccd4dd; padding:7px; text-align:left; vertical-align:top; }}
th {{ position:sticky; top:0; background:#243447; color:white; }}
tr:nth-child(even) {{ background:#f6f8fa; }}
input {{ width:420px; padding:8px; margin:8px 0 14px; }}
</style></head><body>
<h1>Locations accepted by the 1 km rule</h1>
<div class="summary"><b>Generated:</b> {esc(datetime.now().isoformat(timespec='seconds'))}<br>
<b>Locations displayed:</b> {len(rows)} &nbsp; <b>Service events represented:</b> {represented_events}<br>
{summary}<br>
Distance is between the stored Geoapify point and the Google Places point selected during this run.
Google coordinates, place IDs, formatted addresses, and raw responses were not saved.<br>
These are approximate locations for area-level analysis, not verified customer-building coordinates.
</div>
<label><b>Search:</b></label><br><input id="q" placeholder="address, distance band..." oninput="filterRows()">
<table id="results"><thead><tr><th>Distance band</th><th>Distance</th><th>Events</th>
<th>Sanitized input address</th><th>Geoapify match</th><th>Geoapify type</th>
<th>Confidence</th><th>Map checks</th></tr></thead><tbody>{body_rows}</tbody></table>
<script>function filterRows(){{const q=document.getElementById('q').value.toLowerCase();
document.querySelectorAll('#results tbody tr').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(q)?'':'none');}}</script>
</body></html>"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(document, encoding="utf-8")
    print(f"WROTE {REPORT}")
    print(f"Rows: {len(rows)}; represented events: {represented_events}")
    print(
        "Distance bands: "
        + ", ".join(
            f"{band}={outcomes[band]}"
            for band in ("0–250 m", "251–500 m", "501–1,000 m")
        )
    )
    print(
        f"Changed/unavailable results omitted: "
        f"{sum(outcomes.values()) - len(rows)}"
    )
    print("Google coordinates and raw responses were not saved.")
    print("No source-system or warehouse writes.")


if __name__ == "__main__":
    main()
