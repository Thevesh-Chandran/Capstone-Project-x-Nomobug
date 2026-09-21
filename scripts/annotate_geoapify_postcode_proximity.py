"""Add local postcode-reference distances to the versioned Geoapify cache.

Trusted coordinates with an agreeing input/provider postcode define a median
reference point per postcode. Conflicting candidates are measured against that
local reference with the Haversine formula. No provider calls or warehouse
writes occur, and no addresses or coordinates are printed.
"""

from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
from statistics import median

from pilot_geoapify_calendar import OUTPUT, POSTCODE, ROOT


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v6.jsonl"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    value = (math.sin(delta_phi / 2) ** 2
             + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lon / 2) ** 2)
    return 6371.0088 * 2 * math.asin(math.sqrt(value))


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit("Geoapify v6 cache is missing; no proximity annotation performed")
    records = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    trusted: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for record in records:
        match = POSTCODE.search(record.get("input_address", ""))
        if (match and record.get("postcode_agrees") is True
                and record.get("latitude") is not None
                and record.get("longitude") is not None):
            trusted[match.group()].append(
                (float(record["latitude"]), float(record["longitude"]))
            )
    references = {
        postcode: (median(point[0] for point in points),
                   median(point[1] for point in points))
        for postcode, points in trusted.items()
    }
    annotated = 0
    within_five = 0
    beyond_ten = 0
    for record in records:
        record.pop("postcode_reference_distance_km", None)
        match = POSTCODE.search(record.get("input_address", ""))
        if (not match or record.get("postcode_agrees") is not False
                or match.group() not in references
                or record.get("latitude") is None or record.get("longitude") is None):
            continue
        reference_lat, reference_lon = references[match.group()]
        distance = haversine_km(
            float(record["latitude"]), float(record["longitude"]),
            reference_lat, reference_lon,
        )
        record["postcode_reference_distance_km"] = round(distance, 3)
        record["postcode_reference_point_count"] = len(trusted[match.group()])
        annotated += 1
        within_five += distance <= 5
        beyond_ten += distance > 10
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda row: row["address_hash"]):
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(OUTPUT)
    print(f"Trusted postcode reference groups: {len(references)}")
    print(f"Postcode-conflicting candidates with a local reference: {annotated}")
    print(f"Within 5 km: {within_five}; beyond 10 km: {beyond_ten}")
    print(f"WROTE {OUTPUT.relative_to(ROOT)} with {len(records)} records")
    print("No provider calls, source writes, or warehouse writes.")


if __name__ == "__main__":
    main()
