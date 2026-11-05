"""Reassess every current geocoding review candidate with richer Geoapify results.

The prior cache remains untouched. Current manual-review records are queried with
up to 20 results, ranked by normalized address agreement before postcode,
provider result type, and provider confidence. A second-pass query removes only
the leading house/unit identifier, which often distracts free-form geocoders.
Only an improved analysis tier
replaces the old result in the versioned v5 cache. No raw values are printed.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import json
import os
import time

from dotenv import load_dotenv

from pilot_geoapify_calendar import (
    GeoapifyRequestError,
    OUTPUT,
    ROOT,
    analysis_tier,
    fetch_candidates,
    geocode,
    without_leading_premise,
)


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v5.jsonl"
TIER_RANK = {
    "manual_review": 0,
    "postcode_area_candidate": 1,
    "area_analysis_candidate": 2,
    "text_agreement_candidate": 2,
    "street_candidate": 3,
    "precise_candidate": 4,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--max-requests", type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.workers <= 3:
        raise SystemExit("Worker count must be between 1 and 3")
    if not 1 <= args.max_requests <= 600:
        raise SystemExit("Request cap must be between 1 and 600")
    if not SOURCE.is_file():
        raise SystemExit("Geoapify v3 cache is missing; no reassessment performed")

    candidates = fetch_candidates(date(2023, 1, 1), date(2026, 12, 31))
    source_records = {
        record["address_hash"]: record
        for record in map(json.loads, SOURCE.read_text(encoding="utf-8").splitlines())
        if record["address_hash"] in candidates
    }
    missing = set(candidates) - set(source_records)
    if missing:
        raise SystemExit(f"Current cache coverage incomplete: {len(missing)} missing")
    current = dict(source_records)
    review = [
        (address_hash, candidates[address_hash])
        for address_hash, record in current.items()
        if analysis_tier(record) in {"manual_review", "text_agreement_candidate"}
    ]
    selected = review[:args.max_requests]
    print(f"Current candidates: {len(candidates)}; text-based or review candidates to rerank: {len(review)}")
    print(f"Would reassess: {len(selected)} with up to 20 provider candidates each")
    if not args.execute:
        print(f"PLAN ONLY: would write {OUTPUT.relative_to(ROOT)}")
        return

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("NOMOBUG_GEOAPIFY_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Missing NOMOBUG_GEOAPIFY_API_KEY; no calls or writes made")

    improved = 0
    failures: Counter[str] = Counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for address_hash, candidate in selected:
            query = without_leading_premise(candidate["address"])
            futures[pool.submit(geocode, query, api_key, 20)] = (
                address_hash, candidate
            )
            time.sleep(0.26)
        for future in as_completed(futures):
            address_hash, candidate = futures[future]
            try:
                result = future.result()
            except GeoapifyRequestError as exc:
                failures[str(exc)] += 1
                continue
            proposed = {
                "provider": "geoapify",
                "geocoded_at_utc": datetime.now(timezone.utc).isoformat(),
                "address_hash": address_hash,
                "input_address": candidate["address"],
                "calendar_event_rows": candidate["event_rows"],
                **result,
            }
            if TIER_RANK[analysis_tier(proposed)] > TIER_RANK[analysis_tier(current[address_hash])]:
                current[address_hash] = proposed
                improved += 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for address_hash in sorted(candidates):
            record = current[address_hash]
            record["calendar_event_rows"] = candidates[address_hash]["event_rows"]
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(OUTPUT)
    print(f"Review candidates improved by richer result ranking: {improved}")
    print(f"Transient failures retaining the prior result: {sum(failures.values())}")
    print(f"WROTE {OUTPUT.relative_to(ROOT)} with {len(current)} unique current records")
    print("No source or warehouse writes; no private values printed.")


if __name__ == "__main__":
    main()
