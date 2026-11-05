"""Apply user-verified coordinates to the local geocoding cache.

The override file is local and git-ignored. Entries are matched by the exact
sanitized input address so a coordinate cannot silently affect a similar unit.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from pilot_geoapify_calendar import OUTPUT


ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ROOT / "data" / "processed" / "geocoding" / "manual_geocode_overrides.json"


def valid_malaysia_coordinate(latitude: float, longitude: float) -> bool:
    # Deliberately broad bounds covering Peninsular and East Malaysia.
    return 0.5 <= latitude <= 7.5 and 99.0 <= longitude <= 120.0


def main() -> None:
    records = [json.loads(line) for line in OUTPUT.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    by_address = {record["input_address"]: record for record in records}
    unknown = sorted(set(overrides) - set(by_address))
    if unknown:
        raise SystemExit(f"Override addresses absent from cache: {unknown}")

    applied = 0
    for address, values in overrides.items():
        latitude = float(values["latitude"])
        longitude = float(values["longitude"])
        if not valid_malaysia_coordinate(latitude, longitude):
            raise SystemExit(f"Coordinate outside Malaysia bounds for: {address}")
        record = by_address[address]
        verification_level = values.get("verification_level", "manual_property")
        coordinate_source = (
            "external_area_reference"
            if verification_level == "area_reference"
            else "manual_user_verified"
        )
        precision = (
            "area_reference_verified"
            if verification_level == "area_reference"
            else "manual_verified"
        )
        record.update({
            "latitude": latitude,
            "longitude": longitude,
            "coordinate_source": coordinate_source,
            "manual_verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "manual_override_protected": True,
            "precision_tier": precision,
            "result_type": (
                "street_area_reference"
                if verification_level == "area_reference"
                else "manual_coordinate"
            ),
            "confidence": None if verification_level == "area_reference" else 1.0,
            "match_type": coordinate_source,
        })
        if values.get("reference_url"):
            record["coordinate_reference_url"] = values["reference_url"]
        applied += 1

    ordered = sorted(records, key=lambda record: record["address_hash"])
    OUTPUT.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n"
                              for record in ordered), encoding="utf-8")
    print(f"Applied {applied} exact-address manual overrides to {OUTPUT}")


if __name__ == "__main__":
    main()
