"""Resolve strong address-format duplicates from already trusted Calendar rows.

Manual-review addresses are compared locally with usable addresses in the same
cache. A coordinate is reused only for a high token-overlap match, compatible
postcode and structure identifiers, and no close-scoring geographically
conflicting peer. No external request or warehouse write occurs.
"""

from __future__ import annotations

import json

from pilot_geoapify_calendar import (
    OUTPUT,
    POSTCODE,
    ROOT,
    address_structure_conflicts,
    analysis_tier,
    normalized_address_tokens,
)
from annotate_geoapify_postcode_proximity import haversine_km


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v7.jsonl"


def postcode(value: str | None) -> str | None:
    match = POSTCODE.search(value or "")
    return match.group() if match else None


def peer_score(target: dict, peer: dict) -> float | None:
    target_postcode = postcode(target.get("input_address"))
    peer_postcode = postcode(peer.get("input_address"))
    if target_postcode and peer_postcode and target_postcode != peer_postcode:
        return None
    if address_structure_conflicts(target.get("input_address"), peer.get("input_address")):
        return None
    target_words, target_ids = normalized_address_tokens(target.get("input_address"))
    peer_words, peer_ids = normalized_address_tokens(peer.get("input_address"))
    union = target_words | peer_words
    if not union:
        return None
    shared = target_words & peer_words
    similarity = len(shared) / len(union)
    if target_postcode and peer_postcode and len(shared) >= 2:
        similarity += 0.2
    elif len(shared) < 3 or not (target_ids & peer_ids):
        return None
    return similarity


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit("Geoapify v7 cache is missing; no peer matching performed")
    records = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    trusted = [record for record in records
               if analysis_tier(record) != "manual_review"
               and record.get("latitude") is not None
               and record.get("longitude") is not None]
    resolved = 0
    ambiguous = 0
    for target in records:
        if analysis_tier(target) != "manual_review":
            continue
        ranked = sorted(
            ((score, peer) for peer in trusted
             if (score := peer_score(target, peer)) is not None and score >= 0.7),
            key=lambda item: item[0], reverse=True,
        )
        if not ranked:
            continue
        best_score, best = ranked[0]
        if len(ranked) > 1 and best_score - ranked[1][0] < 0.05:
            second = ranked[1][1]
            distance = haversine_km(
                float(best["latitude"]), float(best["longitude"]),
                float(second["latitude"]), float(second["longitude"]),
            )
            if distance > 3:
                ambiguous += 1
                continue
        target.update({
            "latitude": best["latitude"],
            "longitude": best["longitude"],
            "formatted": best.get("formatted"),
            "postcode": best.get("postcode"),
            "postcode_agrees": (
                True if postcode(target.get("input_address"))
                and postcode(target.get("input_address")) == best.get("postcode")
                else None
            ),
            "result_type": best.get("result_type"),
            "confidence": best.get("confidence"),
            "match_type": best.get("match_type"),
            "peer_address_agreement": True,
            "peer_address_match_score": round(best_score, 3),
            "peer_address_hash": best["address_hash"],
            "coordinate_source": "trusted_calendar_address_peer",
        })
        resolved += 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda row: row["address_hash"]):
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(OUTPUT)
    print(f"Manual-review candidates resolved from trusted address peers: {resolved}")
    print(f"Close-scoring but geographically conflicting peers left for review: {ambiguous}")
    print(f"WROTE {OUTPUT.relative_to(ROOT)} with {len(records)} records")
    print("No provider calls, source writes, or warehouse writes.")


if __name__ == "__main__":
    main()
