"""Retry every v12 review address using transient Google place identification.

Google place content is used only in memory to construct several Geoapify text
queries. Only an independently returned Geoapify result whose text agrees with
the original input is retained. Google coordinates, place IDs, formatted
addresses, and raw responses are never written.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv

from pilot_geoapify_calendar import (
    GeoapifyRequestError,
    ROOT,
    address_structure_conflicts,
    address_text_agreement,
    analysis_tier,
    geocode,
    without_leading_premise,
)
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


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v16.jsonl"
OUTPUT = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v17.jsonl"
REVIEW_TIERS = {"manual_review", "google_hinted_area_candidate"}


class GoogleAddressValidationError(RuntimeError):
    """Address Validation failed without exposing address content."""


def validate_google_address(address: str, key: str) -> tuple[str | None, dict]:
    """Return a transient standardized address and non-content verdict flags."""
    url = "https://addressvalidation.googleapis.com/v1:validateAddress?" + urllib.parse.urlencode(
        {"key": key}
    )
    body = json.dumps({
        "address": {
            "regionCode": "MY",
            "languageCode": "en",
            "addressLines": [address],
        }
    }).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "nomobug-capstone-address-validation/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise GoogleAddressValidationError(f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise GoogleAddressValidationError("network_or_response_error") from None
    result = payload.get("result") or {}
    formatted = ((result.get("address") or {}).get("formattedAddress") or "").strip()
    verdict = result.get("verdict") or {}
    flags = {
        key: verdict.get(key)
        for key in (
            "addressComplete", "hasUnconfirmedComponents", "hasInferredComponents",
            "hasReplacedComponents", "possibleNextAction",
        )
        if verdict.get(key) is not None
    }
    return formatted or None, flags


def normalize_google_query_spacing(address: str) -> str:
    """Repair common collapsed Malaysian address boundaries conservatively."""
    text = " ".join(address.split())
    # Separate a five-digit Malaysian postcode from adjacent words.
    text = re.sub(r"(?<=[A-Za-z])(?=\d{5}\b)", " ", text)
    text = re.sub(r"(?<=\d{5})(?=[A-Za-z])", " ", text)
    # Separate well-known address/locality cues when form exports concatenate
    # them with the preceding token (for example ``24aKampung``).
    cues = (
        "kampung|taman|jalan|lorong|persiaran|petaling|selangor|kuala|"
        "putrajaya|shah|ampang|kajang|puchong|cyberjaya|subang|klang"
    )
    text = re.sub(
        rf"(?<=[0-9A-Za-z])(?=(?:{cues})\b)", " ", text,
        flags=re.IGNORECASE,
    )
    return " ".join(text.split())


def google_identification_queries(input_address: str, place: dict) -> list[tuple[str, str]]:
    """Return distinct in-memory Geoapify text-query strategies."""
    display = ((place.get("displayName") or {}).get("text") or "").strip()
    formatted = (place.get("formattedAddress") or "").strip()
    components = component_values(place)
    coarse = [
        components[kind]
        for kind in (
            "sublocality_level_1", "sublocality", "locality", "postal_town",
            "administrative_area_level_2", "administrative_area_level_1", "postal_code",
        )
        if components.get(kind)
    ]
    city_only = [
        components[kind]
        for kind in ("locality", "postal_town", "administrative_area_level_1")
        if components.get(kind)
    ][:2]
    variants = [
        # A short canonical property-name query often resolves Malaysian
        # buildings better than an over-specified address. Extra administrative
        # fields can make Geoapify fall back to a postcode or unrelated POI.
        ("google_display_name_only", display),
        ("google_name_city_only", ", ".join([display, *city_only])),
        ("full_google_place_text", place_comparison_text(place)),
        ("google_formatted_address", formatted),
        ("google_name_with_area", ", ".join([display, *coarse])),
        (
            "input_without_unit_with_area",
            ", ".join([without_leading_premise(input_address), *coarse]),
        ),
    ]
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for strategy, query in variants:
        query = " ".join(query.split()).strip(" ,")
        if not query:
            continue
        if "malaysia" not in query.casefold():
            query = f"{query}, Malaysia"
        key = query.casefold()
        if key not in seen:
            seen.add(key)
            unique.append((strategy, query))
    return unique


def acceptable_candidate(original: dict, candidate: dict) -> bool:
    """Require Geoapify itself to return meaningful original-address text."""
    comparison_address = normalize_google_query_spacing(
        original.get("input_address") or ""
    )
    if candidate.get("latitude") is None or candidate.get("longitude") is None:
        return False
    if address_structure_conflicts(
        comparison_address, candidate.get("formatted")
    ):
        return False
    if not address_text_agreement(
        comparison_address, candidate.get("formatted")
    ):
        return False
    classified = {**candidate, "input_address": comparison_address}
    return analysis_tier(classified) not in REVIEW_TIERS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-addresses", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.max_addresses <= 200:
        raise SystemExit("Address cap must be between 1 and 200")
    if not 1 <= args.workers <= 8:
        raise SystemExit("Worker count must be between 1 and 8")
    if not SOURCE.is_file():
        raise SystemExit("Geoapify v12 cache is missing; no retry performed")

    records = [
        json.loads(line)
        for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    review = [record for record in records if analysis_tier(record) in REVIEW_TIERS]
    selected = review[: args.max_addresses]
    print(f"Current records: {len(records)}; exact-location review candidates: {len(review)}")
    print(f"Selected for Google identification + Geoapify text retry: {len(selected)}")
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
    strategy_counts: Counter[str] = Counter()

    def process_one(old: dict) -> tuple[str, str | None, dict | None]:
        try:
            normalized = normalize_google_query_spacing(old["input_address"])
            validated_address, validation_flags = validate_google_address(
                normalized, google_key
            )
            identification_query = validated_address or normalized
            places = google_places(identification_query, google_key)
            place = select_place_hint(identification_query, places)
            if place is None and identification_query != old["input_address"]:
                places = google_places(old["input_address"], google_key)
                place = select_place_hint(old["input_address"], places)
            hint_fields = tuple(sorted(component_values(place))) if place else ()
            candidates: list[tuple[str, dict]] = []
            queries: list[tuple[str, str]] = []
            if validated_address:
                queries.append(("google_validated_address", validated_address))
            if place:
                queries.extend(google_identification_queries(old["input_address"], place))
            seen_queries: set[str] = set()
            for strategy, query in queries:
                query_key = query.casefold()
                if query_key in seen_queries:
                    continue
                seen_queries.add(query_key)
                result = geocode(query, geoapify_key, 20)
                if place:
                    candidate = proposed_record(
                        old, result, hint_fields, geoapify_matches_hint(place, result)
                    )
                else:
                    candidate = {**old, **result}
                candidate["google_places_identification_used"] = True
                candidate["google_address_validation_used"] = True
                candidate["google_address_validation_flags"] = validation_flags
                candidate["google_query_spacing_normalized"] = (
                    normalized != old["input_address"]
                )
                candidate["geoapify_retry_strategy"] = strategy
                candidate["coordinate_source"] = (
                    "geoapify_after_transient_google_place_identification"
                )
                if acceptable_candidate(old, candidate):
                    candidates.append((strategy, candidate))
                time.sleep(0.05)
            if candidates:
                strategy, best = max(candidates, key=lambda item: improvement_score(item[1]))
                if improvement_score(best) > improvement_score(old):
                    return "improved", strategy, best
                return "not_improved", None, None
            return "no_geoapify_text_match", None, None
        except GoogleAddressValidationError as exc:
            return f"google_validation_{exc}", None, None
        except GooglePlacesRequestError as exc:
            return f"google_{exc}", None, None
        except GeoapifyRequestError as exc:
            return f"geoapify_{exc}", None, None

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_one, old): old for old in selected}
        for index, future in enumerate(as_completed(futures), start=1):
            old = futures[future]
            outcome, strategy, candidate = future.result()
            counts[outcome] += 1
            if candidate is not None:
                current[old["address_hash"]] = candidate
            if strategy is not None:
                strategy_counts[strategy] += 1
            if index % 10 == 0 or index == len(selected):
                print(
                    f"Processed {index} of {len(selected)}; "
                    f"improved={counts['improved']}",
                    flush=True,
                )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for address_hash in sorted(current):
            handle.write(json.dumps(current[address_hash], ensure_ascii=False) + "\n")
    temporary.replace(OUTPUT)
    print(f"Improved Geoapify candidates: {counts['improved']}")
    print(f"No safe Google match: {counts['no_safe_google_match']}")
    print(f"No agreeing Geoapify result: {counts['no_geoapify_text_match']}")
    print(f"Safe result but not improved: {counts['not_improved']}")
    print(f"Improvement strategies: {dict(strategy_counts)}")
    print(f"Other outcomes: {sum(counts.values()) - counts['improved'] - counts['no_safe_google_match'] - counts['no_geoapify_text_match'] - counts['not_improved']}")
    print(f"WROTE {OUTPUT.relative_to(ROOT)} with {len(current)} records")
    print("Google coordinates, place IDs, formatted addresses, and raw responses were not saved.")
    print("No source-system or warehouse writes.")


if __name__ == "__main__":
    main()
