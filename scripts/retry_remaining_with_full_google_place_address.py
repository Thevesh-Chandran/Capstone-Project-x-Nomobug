"""Retry v9 review rows by sending Google's transient full place address to Geoapify.

The Google place name and formatted address exist only in memory for the
Geoapify request. They, Google coordinates, place IDs, and raw responses are
never written. Only an improved Geoapify response is saved to versioned v10.
No source-system or warehouse writes occur.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import time

from dotenv import load_dotenv

from pilot_geoapify_calendar import GeoapifyRequestError, ROOT, analysis_tier, geocode
from retry_geocodes_with_google_place_hints import (
    GooglePlacesRequestError,
    component_values,
    geoapify_matches_hint,
    google_places,
    improvement_score,
    place_comparison_text,
    proposed_record,
    select_place_hint,
)


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v9.jsonl"
OUTPUT = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v10.jsonl"


def full_place_query(place: dict) -> str:
    """Build a transient Geoapify query from Google's selected place result."""
    query = place_comparison_text(place).strip()
    if query and "malaysia" not in query.casefold():
        query = f"{query}, Malaysia"
    return query


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-addresses", type=int, default=1)
    parser.add_argument("--address-hash")
    args = parser.parse_args()
    if not 1 <= args.max_addresses <= 100:
        raise SystemExit("Address cap must be between 1 and 100")
    if not SOURCE.is_file():
        raise SystemExit("Geoapify v9 cache is missing; no retry performed")

    records = [
        json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    review = [record for record in records if analysis_tier(record) == "manual_review"]
    if args.address_hash:
        review = [record for record in review if record["address_hash"] == args.address_hash]
        if not review:
            raise SystemExit("Requested address hash is not in the v9 review set")
    selected = review[:args.max_addresses]
    print(f"Current records: {len(records)}; v9 manual-review candidates: {len(review)}")
    print(f"Selected for full-place Google-to-Geoapify retry: {len(selected)}")
    if not args.execute:
        print(f"PLAN ONLY: would write {OUTPUT.relative_to(ROOT)}")
        return

    load_dotenv(ROOT / ".env")
    google_key = os.getenv("NOMOBUG_GOOGLE_MAPS_API_KEY", "").strip()
    geoapify_key = os.getenv("NOMOBUG_GEOAPIFY_API_KEY", "").strip()
    if not google_key or not geoapify_key:
        raise SystemExit("Both private Google Maps and Geoapify keys are required")

    current = {record["address_hash"]: record for record in records}
    counts: Counter[str] = Counter()
    for index, old in enumerate(selected, start=1):
        try:
            places = google_places(old["input_address"], google_key)
            hint = select_place_hint(old["input_address"], places)
            if hint is None:
                counts["no_safe_google_match"] += 1
                continue
            query = full_place_query(hint)
            if not query:
                counts["empty_full_place_query"] += 1
                continue
            result = geocode(query, geoapify_key, 20)
            fields = tuple(sorted(component_values(hint)))
            candidate = proposed_record(
                old, result, fields, geoapify_matches_hint(hint, result)
            )
            candidate["google_places_full_address_query_used"] = True
            candidate["coordinate_source"] = (
                "geoapify_after_transient_google_full_place_address"
            )
            if improvement_score(candidate) > improvement_score(old):
                current[old["address_hash"]] = candidate
                counts["improved"] += 1
            else:
                counts["not_improved"] += 1
        except GooglePlacesRequestError as exc:
            counts[f"google_{exc}"] += 1
        except GeoapifyRequestError as exc:
            counts[f"geoapify_{exc}"] += 1
        if index % 20 == 0:
            print(f"Processed {index} of {len(selected)}; improved={counts['improved']}")
        time.sleep(0.25)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for address_hash in sorted(current):
            handle.write(json.dumps(current[address_hash], ensure_ascii=False) + "\n")
    temporary.replace(OUTPUT)
    print(f"Improved Geoapify candidates: {counts['improved']}")
    print(f"No safe Google match: {counts['no_safe_google_match']}")
    print(f"Safe match but Geoapify did not improve: {counts['not_improved']}")
    print(f"Other outcomes: {sum(counts.values()) - counts['improved'] - counts['no_safe_google_match'] - counts['not_improved']}")
    print(f"WROTE {OUTPUT.relative_to(ROOT)} with {len(current)} records")
    print("Google place content and raw responses were not cached.")
    print("No source-system or warehouse writes.")


if __name__ == "__main__":
    main()
