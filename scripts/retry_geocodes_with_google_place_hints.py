"""Use transient Google place hints to retry Geoapify review candidates.

Google Places Text Search is used only in memory to identify missing Malaysian
locality, state, and postcode hints. Google coordinates, place IDs, formatted
addresses, and raw responses are never cached. The enriched query is then sent
to Geoapify, and only an improved Geoapify candidate is written to a new,
versioned private cache. No source-system or warehouse writes occur.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv

from pilot_geoapify_calendar import (
    GeoapifyRequestError,
    POSTCODE,
    RESULT_TYPE_SCORE,
    ROOT,
    address_structure_conflicts,
    address_text_agreement,
    analysis_tier,
    geocode,
    normalized_address_tokens,
)


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v8.jsonl"
OUTPUT = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v9.jsonl"
PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
TIER_RANK = {
    "manual_review": 0,
    "postcode_area_candidate": 1,
    "area_analysis_candidate": 2,
    "text_agreement_candidate": 2,
    "proximity_candidate": 2,
    "peer_address_candidate": 2,
    "google_hinted_area_candidate": 1,
    "street_candidate": 3,
    "precise_candidate": 4,
}
HINT_COMPONENTS = {
    "locality", "postal_town", "sublocality", "sublocality_level_1",
    "administrative_area_level_2", "administrative_area_level_1", "postal_code",
}


class GooglePlacesRequestError(RuntimeError):
    """A Google Places request failed without exposing its address or key."""


def place_comparison_text(place: dict) -> str:
    display = (place.get("displayName") or {}).get("text") or ""
    formatted = place.get("formattedAddress") or ""
    return " ".join(part for part in (display, formatted) if part)


def select_place_hint(input_address: str, places: list[dict]) -> dict | None:
    """Return the strongest semantically compatible place, never just result #1."""
    input_words, input_ids = normalized_address_tokens(input_address)

    def named_place_agreement(place: dict) -> bool:
        display = (place.get("displayName") or {}).get("text") or ""
        display_words, _ = normalized_address_tokens(display)
        lexical_input = {
            word for word in input_words if not any(char.isdigit() for char in word)
        }
        lexical_display = {
            word for word in display_words if not any(char.isdigit() for char in word)
        }
        # Unit identifiers such as C1-46-11 must not prevent an otherwise exact
        # named-building match (for example Residence vs Residences).
        return bool(lexical_display) and lexical_display <= lexical_input

    def score(place: dict) -> tuple:
        text = place_comparison_text(place)
        provider_words, provider_ids = normalized_address_tokens(text)
        shared = input_words & provider_words
        coverage = len(shared) / len(input_words) if input_words else 0
        return (
            not address_structure_conflicts(input_address, text),
            address_text_agreement(input_address, text),
            len(shared),
            coverage,
            len(input_ids & provider_ids),
        )

    compatible = [
        place for place in places
        if (address_text_agreement(input_address, place_comparison_text(place))
            or named_place_agreement(place))
        and not address_structure_conflicts(input_address, place_comparison_text(place))
    ]
    return max(compatible, key=score) if compatible else None


def component_values(place: dict) -> dict[str, str]:
    """Extract only coarse locality fields used transiently as query hints."""
    values: dict[str, str] = {}
    for component in place.get("addressComponents") or []:
        value = component.get("longText") or component.get("shortText")
        if not value:
            continue
        for kind in component.get("types") or []:
            if kind in HINT_COMPONENTS and kind not in values:
                values[kind] = value
    return values


def enriched_query(input_address: str, place: dict) -> tuple[str, tuple[str, ...]]:
    """Append missing coarse Malaysian locality hints without replacing input text."""
    components = component_values(place)
    input_words, _ = normalized_address_tokens(input_address)
    input_postcode = POSTCODE.search(input_address)
    ordered = (
        "locality", "postal_town", "sublocality_level_1", "sublocality",
        "administrative_area_level_2", "administrative_area_level_1", "postal_code",
    )
    hints: list[str] = []
    used: list[str] = []
    for kind in ordered:
        value = components.get(kind)
        if not value:
            continue
        if kind == "postal_code" and input_postcode:
            # An explicit customer postcode controls; conflicting Google content
            # must not silently rewrite it.
            continue
        value_words, _ = normalized_address_tokens(value)
        if value_words and value_words <= input_words:
            continue
        if value.casefold() in input_address.casefold():
            continue
        hints.append(value)
        used.append(kind)
    query = ", ".join([input_address, *hints, "Malaysia"])
    return query, tuple(used)


def google_places(input_address: str, key: str, limit: int = 10,
                  include_location: bool = False) -> list[dict]:
    body = json.dumps({
        "textQuery": f"{input_address}, Malaysia",
        "regionCode": "MY",
        "languageCode": "en",
        "maxResultCount": limit,
    }).encode("utf-8")
    field_mask = (
        "places.displayName,places.formattedAddress,"
        "places.addressComponents,places.types"
    )
    if include_location:
        field_mask += ",places.location"
    request = urllib.request.Request(
        PLACES_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            # Intentionally excludes coordinates and place IDs.
            "X-Goog-FieldMask": field_mask,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise GooglePlacesRequestError(f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise GooglePlacesRequestError("network_or_response_error") from None
    places = payload.get("places", [])
    if not isinstance(places, list):
        raise GooglePlacesRequestError("unexpected_response")
    return places


def geoapify_matches_hint(place: dict, geoapify_result: dict) -> bool:
    """Confirm Geoapify returned the coarse locality/postcode Google suggested."""
    components = component_values(place)
    hint_postcode = components.get("postal_code")
    if hint_postcode and geoapify_result.get("postcode") == hint_postcode:
        return True
    hint_text = " ".join(
        components[kind] for kind in (
            "locality", "postal_town", "sublocality_level_1", "sublocality",
            "administrative_area_level_2", "administrative_area_level_1",
        ) if kind in components
    )
    hint_words, _ = normalized_address_tokens(hint_text)
    provider_words, _ = normalized_address_tokens(geoapify_result.get("formatted"))
    return len(hint_words & provider_words) >= 2


def proposed_record(old: dict, geoapify_result: dict,
                    hint_fields: tuple[str, ...], hint_agreement: bool) -> dict:
    original_postcode = POSTCODE.search(old.get("input_address", ""))
    provider_postcode = geoapify_result.get("postcode")
    postcode_agrees = (
        None if original_postcode is None
        else provider_postcode == original_postcode.group()
    )
    return {
        "provider": "geoapify",
        "geocoded_at_utc": datetime.now(timezone.utc).isoformat(),
        "address_hash": old["address_hash"],
        "input_address": old["input_address"],
        "calendar_event_rows": old["calendar_event_rows"],
        **geoapify_result,
        "postcode_agrees": postcode_agrees,
        "google_places_hint_used": True,
        "google_places_hint_fields": list(hint_fields),
        "google_places_hint_agreement": hint_agreement,
        "coordinate_source": "geoapify_after_transient_google_place_hint",
    }


def improvement_score(record: dict) -> tuple:
    return (
        TIER_RANK.get(analysis_tier(record), 0),
        address_text_agreement(record.get("input_address"), record.get("formatted")),
        RESULT_TYPE_SCORE.get(record.get("result_type"), -1),
        float(record.get("confidence") or 0),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-addresses", type=int, default=1)
    parser.add_argument("--address-hash")
    args = parser.parse_args()
    if not 1 <= args.max_addresses <= 200:
        raise SystemExit("Address cap must be between 1 and 200")
    if not SOURCE.is_file():
        raise SystemExit("Geoapify v8 cache is missing; no fallback performed")

    records = [
        json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    review = [record for record in records if analysis_tier(record) == "manual_review"]
    if args.address_hash:
        review = [record for record in review if record["address_hash"] == args.address_hash]
        if not review:
            raise SystemExit("Requested address hash is not in the current review set")
    selected = review[:args.max_addresses]
    print(f"Current records: {len(records)}; manual-review candidates: {len(review)}")
    print(f"Selected for transient Google hint + Geoapify retry: {len(selected)}")
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
                counts["no_safe_google_hint"] += 1
                continue
            query, hint_fields = enriched_query(old["input_address"], hint)
            if not hint_fields:
                counts["no_new_hint_fields"] += 1
                continue
            result = geocode(query, geoapify_key, 20)
            candidate = proposed_record(
                old, result, hint_fields, geoapify_matches_hint(hint, result)
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
        if index % 25 == 0:
            print(f"Processed {index} of {len(selected)}; improved={counts['improved']}")
        time.sleep(0.25)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for address_hash in sorted(current):
            handle.write(json.dumps(current[address_hash], ensure_ascii=False) + "\n")
    temporary.replace(OUTPUT)
    print(f"Improved Geoapify candidates: {counts['improved']}")
    print(f"No safe Google hint: {counts['no_safe_google_hint']}")
    print(f"Safe hint but Geoapify did not improve: {counts['not_improved']}")
    print(f"Other outcomes: {sum(counts.values()) - counts['improved'] - counts['no_safe_google_hint'] - counts['not_improved']}")
    print(f"WROTE {OUTPUT.relative_to(ROOT)} with {len(current)} records")
    print("Google coordinates, place IDs, formatted addresses, and raw responses were not cached.")
    print("No source-system or warehouse writes.")


if __name__ == "__main__":
    main()
