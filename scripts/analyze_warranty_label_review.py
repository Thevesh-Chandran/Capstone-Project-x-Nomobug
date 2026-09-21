"""Analyze the completed CP2 warranty-label review workbook."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd


VALID_LABELS = {"Confirmed warranty claim", "Not a warranty claim", "Unclear"}


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Return a Wilson score interval for a binomial proportion."""
    if total <= 0:
        return (0.0, 0.0)
    proportion = successes / total
    denominator = 1 + z**2 / total
    centre = (proportion + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z**2 / (4 * total**2)
    ) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def summarize(frame: pd.DataFrame) -> dict:
    """Validate reviewer inputs and return review-quality metrics."""
    stratum_column = "Review stratum" if "Review stratum" in frame.columns else "Stratum"
    required = {"Review ID", stratum_column, "Review label"}
    missing_columns = sorted(required - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Review sheet is missing columns: {', '.join(missing_columns)}")

    labels = frame["Review label"].fillna("").astype(str).str.strip()
    invalid = sorted(set(labels) - VALID_LABELS - {""})
    if invalid:
        raise ValueError(f"Invalid review labels: {', '.join(invalid)}")

    incomplete = frame.loc[labels == "", "Review ID"].astype(str).tolist()
    result: dict = {
        "total_rows": int(len(frame)),
        "reviewed_rows": int((labels != "").sum()),
        "remaining_rows": len(incomplete),
        "remaining_review_ids": incomplete,
        "complete": not incomplete,
    }
    if incomplete:
        return result

    reviewed = frame.copy()
    reviewed["Review label"] = labels
    reviewed["is_confirmed"] = reviewed["Review label"].eq("Confirmed warranty claim")
    reviewed["is_unclear"] = reviewed["Review label"].eq("Unclear")
    reviewed["system_positive"] = reviewed[stratum_column].astype(str).str.startswith("POSITIVE_")
    reviewed["hard_negative"] = reviewed[stratum_column].astype(str).str.startswith("NEGATIVE_")

    positive = reviewed[reviewed["system_positive"]]
    negative = reviewed[reviewed["hard_negative"]]
    positive_successes = int(positive["is_confirmed"].sum())
    negative_errors = int(negative["is_confirmed"].sum())

    result.update(
        {
            "system_positive_precision": positive_successes / len(positive) if len(positive) else None,
            "system_positive_precision_wilson_95": wilson_interval(positive_successes, len(positive)),
            "hard_negative_positive_rate": negative_errors / len(negative) if len(negative) else None,
            "hard_negative_positive_rate_wilson_95": wilson_interval(negative_errors, len(negative)),
            "unclear_rows": int(reviewed["is_unclear"].sum()),
            "by_stratum": {},
            "error_reasons": {},
            "interpretation_note": (
                "This is a stratified diagnostic sample. Its unweighted overall confirmed rate "
                "must not be reported as population accuracy."
            ),
        }
    )

    for stratum, group in reviewed.groupby(stratum_column, sort=True):
        confirmed = int(group["is_confirmed"].sum())
        result["by_stratum"][str(stratum)] = {
            "rows": int(len(group)),
            "confirmed_claims": confirmed,
            "confirmed_rate": confirmed / len(group),
            "confirmed_rate_wilson_95": wilson_interval(confirmed, len(group)),
            "unclear": int(group["is_unclear"].sum()),
        }

    if "Error reason" in reviewed.columns:
        reasons = reviewed["Error reason"].fillna("").astype(str).str.strip()
        result["error_reasons"] = {
            str(reason): int(count)
            for reason, count in reasons[reasons != ""].value_counts().items()
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, help="Completed CP2 review workbook")
    parser.add_argument("--output", type=Path, help="JSON output path")
    args = parser.parse_args()

    frame = pd.read_excel(args.workbook, sheet_name="Review", engine="openpyxl")
    result = summarize(frame)
    output = args.output or args.workbook.with_name(f"{args.workbook.stem}_analysis.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Wrote {output}")
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
