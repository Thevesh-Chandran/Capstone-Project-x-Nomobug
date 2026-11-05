"""One-time, recoverable migration of the private geocode cache to sanitized keys."""

from __future__ import annotations

import hashlib
import json
import shutil

from inspect_calendar_address_blocks import normalized_candidate_key
from pilot_geoapify_calendar import (
    OUTPUT, fetch_candidates, precision_tier, sanitized_address_candidate,
)


BACKUP = OUTPUT.with_name("geoapify_pilot_v2_pre_sanitize_20260915.jsonl")
TEMP = OUTPUT.with_suffix(".jsonl.tmp")


def record_score(record: dict) -> tuple[int, float]:
    tier = precision_tier(
        record.get("result_type"), record.get("postcode_agrees"), record.get("confidence")
    )
    rank = {"manual_review": 0, "postcode_area_candidate": 1,
            "street_candidate": 2, "precise_candidate": 3}[tier]
    return rank, float(record.get("confidence") or 0)


def main() -> None:
    if not OUTPUT.exists():
        raise SystemExit("Active cache missing; migration not run")
    if BACKUP.exists() or TEMP.exists():
        raise SystemExit("Backup/temp target already exists; inspect before retrying")
    candidates = fetch_candidates()
    current: dict[str, dict] = {}
    original_lines = OUTPUT.read_text(encoding="utf-8").splitlines()
    for line in original_lines:
        if not line.strip():
            continue
        record = json.loads(line)
        cleaned = sanitized_address_candidate(record.get("input_address"))
        if not cleaned:
            continue
        address_hash = hashlib.sha256(normalized_candidate_key(cleaned).encode()).hexdigest()
        if address_hash not in candidates:
            continue
        migrated = {**record, "address_hash": address_hash, "input_address": cleaned,
                    "calendar_event_rows": candidates[address_hash]["event_rows"]}
        prior = current.get(address_hash)
        if prior is None or record_score(migrated) > record_score(prior):
            current[address_hash] = migrated

    if not current:
        raise SystemExit("Migration produced no current cache rows; original left unchanged")
    for address_hash, record in current.items():
        if address_hash != hashlib.sha256(
                normalized_candidate_key(record["input_address"]).encode()).hexdigest():
            raise SystemExit("Sanitized hash validation failed; original left unchanged")
        if sanitized_address_candidate(record["input_address"]) != record["input_address"]:
            raise SystemExit("Sanitized input validation failed; original left unchanged")

    shutil.copy2(OUTPUT, BACKUP)
    with TEMP.open("w", encoding="utf-8") as handle:
        for address_hash in sorted(current):
            handle.write(json.dumps(current[address_hash], ensure_ascii=False) + "\n")
    TEMP.replace(OUTPUT)
    print(f"Original cache rows backed up: {len([x for x in original_lines if x.strip()])}")
    print(f"Active sanitized cache rows: {len(current)}")
    print("No address or contact values printed. Backup is private and git-ignored.")


if __name__ == "__main__":
    main()
