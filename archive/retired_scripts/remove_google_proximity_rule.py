"""Create v12 without the retired Google/Geoapify distance acceptance rule."""

from __future__ import annotations

import json

from pilot_geoapify_calendar import ROOT


SOURCE = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v11.jsonl"
OUTPUT = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v12.jsonl"
RETIRED_FIELDS = {
    "google_place_within_1km",
    "google_place_proximity_threshold_km",
    "google_place_proximity_checked_at_utc",
}


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit("Geoapify v11 cache is missing; no v12 cache created")
    records = [
        json.loads(line)
        for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    removed = 0
    for record in records:
        for field in RETIRED_FIELDS:
            if field in record:
                removed += 1
                record.pop(field, None)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda row: row["address_hash"]):
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(OUTPUT)
    print(f"WROTE {OUTPUT.relative_to(ROOT)} with {len(records)} records")
    print(f"Removed retired proximity-rule fields: {removed}")
    print("No API, source-system, or warehouse writes.")


if __name__ == "__main__":
    main()
