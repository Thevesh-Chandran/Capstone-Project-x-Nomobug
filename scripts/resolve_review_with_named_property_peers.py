"""Resolve review addresses from exact named-property Geoapify peers.

Google Places is used transiently to identify the property name and locality.
The persisted coordinate and formatted address always come from an existing
Geoapify building/amenity result for that same distinctive property.
"""

from __future__ import annotations

import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

from pilot_geoapify_calendar import (
    ROOT,
    address_structure_conflicts,
    address_text_agreement,
    analysis_tier,
    normalized_address_tokens,
)
from retry_geocodes_with_google_place_hints import (
    GooglePlacesRequestError,
    geoapify_matches_hint,
    google_places,
    select_place_hint,
)


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v14.jsonl"
OUTPUT = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v15.jsonl"
REVIEW_TIERS = {"manual_review", "google_hinted_area_candidate"}


def distance_km(left: dict, right: dict) -> float:
    lat1, lon1 = math.radians(left["latitude"]), math.radians(left["longitude"])
    lat2, lon2 = math.radians(right["latitude"]), math.radians(right["longitude"])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def distinctive_name_agreement(name: str, formatted: str) -> tuple[bool, int]:
    name_words, _ = normalized_address_tokens(name)
    formatted_words, _ = normalized_address_tokens(formatted)
    shared = name_words & formatted_words
    generic_property_words = {
        "apartment", "apartments", "residence", "residences", "residensi",
        "condo", "condominium", "tower", "block", "blok", "suite", "suites",
    }
    input_property_types = name_words & generic_property_words
    formatted_property_types = formatted_words & generic_property_words
    if input_property_types and not formatted_property_types:
        return False, len(shared)
    distinctive_input = name_words - generic_property_words
    distinctive_shared = shared - generic_property_words
    # Two shared distinctive words are strong evidence. A single long token is
    # accepted only when it is the whole distinctive property name (Conezion,
    # Gardenview, etc.), not merely a shared area word from a longer name.
    agreed = len(distinctive_shared) >= 2 or (
        len(distinctive_input) == 1
        and distinctive_shared == distinctive_input
        and len(next(iter(distinctive_shared), "")) >= 7
    )
    return agreed and address_text_agreement(name, formatted), len(shared)


def choose_peer(original: dict, place: dict, peers: list[dict]) -> dict | None:
    name = ((place.get("displayName") or {}).get("text") or "").strip()
    if not name or not address_text_agreement(original.get("input_address"), name):
        return None
    candidates: list[tuple[tuple[int, int, float], dict]] = []
    for peer in peers:
        formatted = peer.get("formatted") or ""
        agrees, shared_count = distinctive_name_agreement(name, formatted)
        if not agrees or address_structure_conflicts(name, formatted):
            continue
        # Google is only an identification aid. The original customer address
        # must independently share the property's distinctive wording with the
        # persisted Geoapify peer; generic words such as apartment/residence
        # cannot establish identity.
        original_agrees, original_shared = distinctive_name_agreement(
            original.get("input_address") or "", formatted
        )
        if not original_agrees:
            continue
        if not geoapify_matches_hint(place, peer):
            continue
        score = (
            shared_count + original_shared,
            int(peer.get("result_type") == "building"),
            float(peer.get("confidence") or 0),
        )
        candidates.append((score, peer))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best = candidates[0]
    # If equally strong candidates point to materially different properties,
    # retain the record for review instead of guessing.
    for score, candidate in candidates[1:]:
        if score == best_score and distance_km(best, candidate) > 0.5:
            return None
    return best


def apply_peer(original: dict, peer: dict) -> dict:
    updated = dict(original)
    updated.update({
        "latitude": peer["latitude"],
        "longitude": peer["longitude"],
        "result_type": peer["result_type"],
        "confidence": peer.get("confidence"),
        "match_type": peer.get("match_type"),
        "formatted": peer["formatted"],
        "postcode": peer.get("postcode"),
        "postcode_agrees": peer.get("postcode_agrees"),
        "precision_tier": "peer_address_candidate",
        "peer_address_agreement": True,
        "peer_address_hash": peer["address_hash"],
        "coordinate_source": "trusted_geoapify_named_property_peer",
        "google_places_identification_used": True,
    })
    return updated


def main() -> None:
    rows = [
        json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    review = [row for row in rows if analysis_tier(row) in REVIEW_TIERS]
    peers = [
        row for row in rows
        if row.get("latitude") is not None
        and row.get("longitude") is not None
        and row.get("result_type") in {"building", "amenity"}
        and row.get("formatted")
    ]
    load_dotenv(ROOT / ".env")
    key = os.getenv("NOMOBUG_GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        raise SystemExit("Missing private Google Maps key")

    replacements: dict[str, dict] = {}
    outcomes = {"resolved": 0, "no_safe_google_match": 0, "no_unique_geoapify_peer": 0}

    def process(row: dict) -> tuple[str, dict | None]:
        try:
            place = select_place_hint(row["input_address"], google_places(row["input_address"], key))
        except GooglePlacesRequestError:
            return "no_safe_google_match", None
        if place is None:
            return "no_safe_google_match", None
        peer = choose_peer(row, place, peers)
        if peer is None:
            return "no_unique_geoapify_peer", None
        return "resolved", apply_peer(row, peer)

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_rows = {executor.submit(process, row): row for row in review}
        for index, future in enumerate(as_completed(future_rows), start=1):
            source_row = future_rows[future]
            outcome, updated = future.result()
            outcomes[outcome] += 1
            if updated is not None:
                replacements[source_row["address_hash"]] = updated
            if index % 10 == 0 or index == len(review):
                print(f"Processed {index}/{len(review)}; resolved={outcomes['resolved']}")

    final = [replacements.get(row["address_hash"], row) for row in rows]
    OUTPUT.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in final) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(outcomes, sort_keys=True))
    print("No Google coordinates, place IDs, formatted addresses, or raw responses saved")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
