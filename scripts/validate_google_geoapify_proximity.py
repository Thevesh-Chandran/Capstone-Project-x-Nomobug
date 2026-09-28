"""Validate Google-hinted Geoapify points against a transient 1 km threshold.

Google coordinates are requested only for an in-memory Haversine comparison and
are never written. The versioned v11 cache stores only whether the Geoapify point
was within the user-approved 1 km threshold. No provider coordinates are
replaced, and no source-system or warehouse writes occur.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
import time

from dotenv import load_dotenv

from annotate_geoapify_postcode_proximity import haversine_km
from pilot_geoapify_calendar import ROOT, analysis_tier
from retry_geocodes_with_google_place_hints import (
    GooglePlacesRequestError,
    google_places,
    select_place_hint,
)


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v10.jsonl"
OUTPUT = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v11.jsonl"
THRESHOLD_KM = 1.0


def within_threshold(record: dict, place: dict, threshold_km: float = THRESHOLD_KM) -> bool:
    location = place.get("location") or {}
    google_lat = location.get("latitude")
    google_lon = location.get("longitude")
    if google_lat is None or google_lon is None:
        return False
    distance = haversine_km(
        float(record["latitude"]), float(record["longitude"]),
        float(google_lat), float(google_lon),
    )
    return distance <= threshold_km


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-addresses", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.max_addresses <= 200:
        raise SystemExit("Address cap must be between 1 and 200")
    if not SOURCE.is_file():
        raise SystemExit("Geoapify v10 cache is missing; no validation performed")

    records = [
        json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    eligible = [
        record for record in records
        if analysis_tier(record) == "google_hinted_area_candidate"
        and record.get("latitude") is not None and record.get("longitude") is not None
    ]
    selected = eligible[:args.max_addresses]
    print(f"Current records: {len(records)}; Google-hinted area candidates: {len(eligible)}")
    print(f"Selected for transient 1 km validation: {len(selected)}")
    if not args.execute:
        print(f"PLAN ONLY: would write {OUTPUT.relative_to(ROOT)}")
        return

    load_dotenv(ROOT / ".env")
    google_key = os.getenv("NOMOBUG_GOOGLE_MAPS_API_KEY", "").strip()
    if not google_key:
        raise SystemExit("Missing private Google Maps key; no validation performed")

    current = {record["address_hash"]: record for record in records}
    counts: Counter[str] = Counter()
    for index, record in enumerate(selected, start=1):
        try:
            places = google_places(
                record["input_address"], google_key, include_location=True
            )
            place = select_place_hint(record["input_address"], places)
            if place is None or not (place.get("location") or {}):
                counts["no_safe_google_location"] += 1
                continue
            updated = dict(record)
            updated["google_place_within_1km"] = within_threshold(record, place)
            updated["google_place_proximity_threshold_km"] = THRESHOLD_KM
            updated["google_place_proximity_checked_at_utc"] = (
                datetime.now(timezone.utc).isoformat()
            )
            current[record["address_hash"]] = updated
            counts["within_1km" if updated["google_place_within_1km"] else "over_1km"] += 1
        except GooglePlacesRequestError as exc:
            counts[f"google_{exc}"] += 1
        if index % 25 == 0:
            print(f"Processed {index} of {len(selected)}; within_1km={counts['within_1km']}")
        time.sleep(0.15)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for address_hash in sorted(current):
            handle.write(json.dumps(current[address_hash], ensure_ascii=False) + "\n")
    temporary.replace(OUTPUT)
    print(f"Within 1 km: {counts['within_1km']}; over 1 km: {counts['over_1km']}")
    print(f"No safe Google location: {counts['no_safe_google_location']}")
    print(f"Other outcomes: {sum(counts.values()) - counts['within_1km'] - counts['over_1km'] - counts['no_safe_google_location']}")
    print(f"WROTE {OUTPUT.relative_to(ROOT)} with {len(current)} records")
    print("Google coordinates and raw responses were not cached.")
    print("No source-system or warehouse writes.")


if __name__ == "__main__":
    main()
