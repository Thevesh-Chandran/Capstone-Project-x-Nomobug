"""Convert preserved review decisions into a deterministic, PII-free dbt seed."""

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALID_LABELS = {"Confirmed warranty claim", "Not a warranty claim", "Unclear"}


def build_seed(source: Path, output: Path) -> int:
    with source.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    seen_rows, seen_ids = set(), set()
    for row in rows:
        event_row = int(row["calendar_event_row"])
        if event_row <= 0 or event_row in seen_rows or row["review_id"] in seen_ids:
            raise ValueError("Review identifiers must be positive and unique")
        if row["review_label"] not in VALID_LABELS or not row["event_id"]:
            raise ValueError("Review has an invalid label or missing event ID")
        seen_rows.add(event_row)
        seen_ids.add(row["review_id"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "calendar_event_row", "event_id", "review_id", "review_label", "reviewed_at",
        ])
        writer.writeheader()
        for row in sorted(rows, key=lambda item: int(item["calendar_event_row"])):
            writer.writerow({
                "calendar_event_row": int(row["calendar_event_row"]),
                "event_id": row["event_id"],
                "review_id": row["review_id"],
                "review_label": row["review_label"],
                "reviewed_at": "2026-09-27",
            })
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "planning/warranty_review_decisions.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "dbt/seeds/calendar_warranty_review_overrides.csv")
    args = parser.parse_args()
    print(f"Preserved {build_seed(args.source, args.output)} event review decisions in {args.output}")


if __name__ == "__main__":
    main()
