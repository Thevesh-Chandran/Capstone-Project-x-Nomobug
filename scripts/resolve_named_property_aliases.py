"""Resolve unit-level aliases using an existing exact Geoapify property result.

This is deliberately narrow: a canonical provider result must contain the same
distinctive property token as every promoted input.  Unit, block, and tower
identifiers are retained only in the original input; they do not change the
shared property's coordinates.
"""

from __future__ import annotations

import json
from pathlib import Path

from pilot_geoapify_calendar import ROOT


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v13.jsonl"
OUTPUT = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v14.jsonl"


def is_conezion_alias(text: str | None) -> bool:
    value = (text or "").casefold()
    return "conezion" in value or "conezión" in value


def resolve_conezion(rows: list[dict]) -> int:
    canonical = next(
        row for row in rows
        if is_conezion_alias(row.get("formatted"))
        and row.get("result_type") in {"building", "amenity"}
        and row.get("latitude") is not None
        and row.get("longitude") is not None
    )
    changed = 0
    for row in rows:
        if not is_conezion_alias(row.get("input_address")):
            continue
        row.update({
            "latitude": canonical["latitude"],
            "longitude": canonical["longitude"],
            "result_type": canonical["result_type"],
            "confidence": canonical.get("confidence"),
            "match_type": canonical.get("match_type"),
            "formatted": canonical["formatted"],
            "postcode": canonical.get("postcode"),
            "postcode_agrees": canonical.get("postcode_agrees"),
            "precision_tier": "peer_address_candidate",
            "peer_address_agreement": True,
            "peer_address_hash": canonical["address_hash"],
            "peer_address_match_score": 1.0,
            "coordinate_source": "trusted_geoapify_named_property_peer",
        })
        changed += 1
    return changed


def main() -> None:
    rows = [
        json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    changed = resolve_conezion(rows)
    OUTPUT.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    print(f"Resolved {changed} Conezion address variants from one exact Geoapify property result")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
