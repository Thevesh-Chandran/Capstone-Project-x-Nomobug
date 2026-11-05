"""Retry current postcode-conflicting Geoapify results with a larger result set.

The original v2 cache remains untouched. Only a result whose provider postcode
exactly matches the input postcode can replace the v2 selection in the compact,
current-only v3 cache. Raw addresses and coordinates are never printed.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import time

from dotenv import load_dotenv

from pilot_geoapify_calendar import (
    GeoapifyRequestError,
    OUTPUT,
    ROOT,
    fetch_candidates,
    geocode,
)


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v2.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.workers <= 3:
        raise SystemExit("Worker count must be between 1 and 3")
    if not SOURCE.is_file():
        raise SystemExit("Geoapify v2 cache is missing; no retry performed")
    candidates = fetch_candidates(date(2023, 1, 1), date(2026, 12, 31))
    source_records = {
        record["address_hash"]: record
        for record in map(json.loads, SOURCE.read_text(encoding="utf-8").splitlines())
    }
    missing = set(candidates) - set(source_records)
    if missing:
        raise SystemExit(f"Current candidate cache coverage incomplete: {len(missing)} missing")
    current = {address_hash: source_records[address_hash] for address_hash in candidates}
    conflicts = [
        (address_hash, candidates[address_hash])
        for address_hash, record in current.items()
        if record.get("postcode_agrees") is False
    ]
    print(f"Current candidates: {len(candidates)}; postcode conflicts to retry: {len(conflicts)}")
    print("Retry limit: 20 provider candidates; replacements require exact postcode agreement.")
    if not args.execute:
        print(f"PLAN ONLY: would write versioned cache {OUTPUT.relative_to(ROOT)}")
        return
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("NOMOBUG_GEOAPIFY_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Missing NOMOBUG_GEOAPIFY_API_KEY; no calls or writes made")
    improved = 0
    failures: Counter[str] = Counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for address_hash, candidate in conflicts:
            futures[pool.submit(geocode, candidate["address"], api_key, 20)] = (
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
            if result.get("postcode_agrees") is not True:
                continue
            current[address_hash] = {
                "provider": "geoapify",
                "geocoded_at_utc": datetime.now(timezone.utc).isoformat(),
                "address_hash": address_hash,
                "input_address": candidate["address"],
                "calendar_event_rows": candidate["event_rows"],
                **result,
            }
            improved += 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for address_hash in sorted(candidates):
            record = current[address_hash]
            record["calendar_event_rows"] = candidates[address_hash]["event_rows"]
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(OUTPUT)
    print(f"Postcode conflicts resolved by exact provider agreement: {improved}")
    print(f"Transient retry failures retained from v2: {sum(failures.values())}")
    print(f"WROTE {OUTPUT.relative_to(ROOT)} with {len(current)} unique current records")
    print("No source or warehouse writes; no private values printed.")


if __name__ == "__main__":
    main()
