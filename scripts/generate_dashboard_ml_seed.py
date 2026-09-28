"""Export frozen v5 holdout aggregates for the privacy-safe Looker view.

This deliberately reads only committed aggregate evaluation JSON, never model
predictors, package-level predictions, or customer records.
"""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config/warranty_new_holdout_v5.json"
DESTINATION = ROOT / "dbt/seeds/cp2_v5_holdout_metrics.csv"
ROLES = ("reference", "selected_ap")
METRICS = (
    ("roc_auc", lambda item: item["metrics"]["roc_auc"]),
    ("average_precision", lambda item: item["metrics"]["average_precision"]),
    ("brier_score", lambda item: item["metrics"]["brier_score"]),
    ("threshold_accuracy", lambda item: item["metrics"]["accuracy"]),
    ("always_no_callback_accuracy", lambda item: item["metrics"]["majority_class_accuracy"]),
    ("review20_recall", lambda item: item["priority_top20pct"]["recall"]),
    ("review20_precision", lambda item: item["priority_top20pct"]["precision"]),
    ("review20_positive_windows_found", lambda item: item["segments"]["all"]["budget_TP"]),
)


def rows_from_source(source: dict) -> list[dict]:
    if source["status"] != "retrospective_future_services_not_online_prediction":
        raise ValueError("Unexpected evaluation status")
    if source["rows"] != 100 or source["positive_rows"] != 5:
        raise ValueError("Frozen holdout population changed; review before release")
    rows = []
    for role in ROLES:
        item = source["results"][role]
        if item["metrics"]["rows"] != source["rows"] or item["metrics"]["positives"] != source["positive_rows"]:
            raise ValueError(f"Population mismatch for {role}")
        for name, getter in METRICS:
            rows.append({"model_role": role, "metric_name": name, "metric_value": getter(item)})
    return rows


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = rows_from_source(source)
    with DESTINATION.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("model_role", "metric_name", "metric_value"))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} aggregate metrics to {DESTINATION}")


if __name__ == "__main__":
    main()
