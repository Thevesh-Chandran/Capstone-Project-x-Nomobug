"""Aggregate-only quality report for the private Calendar geocode cache."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date

from pilot_geoapify_calendar import OUTPUT, POSTCODE, analysis_tier, fetch_candidates


USABLE_TIERS = {
    "precise_candidate", "street_candidate", "postcode_area_candidate",
    "area_analysis_candidate", "text_agreement_candidate", "proximity_candidate",
    "peer_address_candidate", "google_hinted_area_candidate",
}


def current_tier(record: dict) -> str:
    return analysis_tier(record)


def main() -> None:
    candidates = fetch_candidates(date(2023, 1, 1), date(2026, 12, 31))
    records = []
    if OUTPUT.exists():
        records = [json.loads(line) for line in OUTPUT.read_text(encoding="utf-8").splitlines()
                   if line.strip()]

    by_hash = {record["address_hash"]: record for record in records}
    duplicate_cache_rows = len(records) - len(by_hash)
    tier_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    postcode_counts: Counter[str] = Counter()
    accepted_event_rows: set[int] = set()
    review_event_rows: set[int] = set()

    current_hashes = set(candidates)
    current_records = {
        address_hash: record for address_hash, record in by_hash.items()
        if address_hash in current_hashes
    }
    for address_hash, record in current_records.items():
        tier = current_tier(record)
        tier_counts[tier] += 1
        type_counts[str(record.get("result_type") or "no_result")] += 1
        has_input_postcode = bool(POSTCODE.search(record.get("input_address", "")))
        if not has_input_postcode:
            postcode_counts["input_without_postcode"] += 1
        elif record.get("postcode_agrees") is True:
            postcode_counts["postcode_agrees"] += 1
        elif record.get("postcode_agrees") is False:
            postcode_counts["postcode_disagrees"] += 1
        else:
            postcode_counts["provider_postcode_unavailable"] += 1
        candidate = candidates[address_hash]
        target = accepted_event_rows if tier in USABLE_TIERS else review_event_rows
        target.update(candidate.get("event_rows") or [])

    all_candidate_rows = {
        int(row)
        for item in candidates.values()
        for row in item.get("event_rows", [])
    }
    cached_candidate_hashes = set(candidates) & set(by_hash)
    unresolved_hashes = set(candidates) - set(by_hash)
    obsolete_cache_hashes = set(by_hash) - set(candidates)

    print("Geoapify Calendar aggregate quality summary")
    print(f"Candidate addresses: {len(candidates)}")
    print(f"Cached unique addresses: {len(cached_candidate_hashes)}")
    print(f"Unresolved provider requests: {len(unresolved_hashes)}")
    print(f"Obsolete cached strings excluded from quality counts: {len(obsolete_cache_hashes)}")
    print(f"Duplicate cache rows: {duplicate_cache_rows}")
    print("Current precision tiers: " + ", ".join(
        f"{key}={tier_counts[key]}" for key in sorted(tier_counts)
    ))
    print("Provider result types: " + ", ".join(
        f"{key}={type_counts[key]}" for key in sorted(type_counts)
    ))
    print("Postcode checks: " + ", ".join(
        f"{key}={postcode_counts[key]}" for key in sorted(postcode_counts)
    ))
    print(f"Candidate event rows represented: {len(all_candidate_rows)}")
    print(f"Event rows with usable coordinate candidates: {len(accepted_event_rows)}")
    print(f"Event rows needing geocode review: {len(review_event_rows)}")
    print("No address, customer, phone, email, or coordinate values printed.")


if __name__ == "__main__":
    main()
