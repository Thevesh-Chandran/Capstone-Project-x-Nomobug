"""Reproducible aggregate evidence for follow-up decisions; never fit a model.

Historical holdout summaries remain fixed. New history-rule comparisons use
already-inspected DEVELOPMENT predictions only and are labelled exploratory.
Private keys/features are used for alignment but never emitted to the seeds.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["population", "sales_record_id", "anchor_date"]
TARGET = "warranty_signal_within_30d"
HISTORY = "prior_property_warranty_claims"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def select_exact(frame: pd.DataFrame, score: str, fraction: float = .2) -> pd.Series:
    """Exact budget; missing history last, outcome-independent SHA256 tie break."""
    if not 0 < fraction <= 1 or frame.empty:
        raise ValueError("Nonempty population and fraction in (0,1] required")
    if frame[KEYS].isna().any().any() or frame.duplicated(KEYS).any():
        raise ValueError("Missing or duplicate service keys")
    values = pd.to_numeric(frame[score], errors="raise")
    if np.isinf(values).any() or (values.dropna() < 0).any():
        raise ValueError("Invalid score")
    tie = frame[KEYS].astype(str).apply(
        lambda row: hashlib.sha256(json.dumps(row.tolist(), separators=(",", ":")).encode()).hexdigest(), axis=1)
    order = pd.DataFrame({"score": values, "tie": tie}, index=frame.index).sort_values(
        ["score", "tie"], ascending=[False, True], na_position="last", kind="stable")
    selected = pd.Series(False, index=frame.index)
    selected.loc[order.index[:math.ceil(len(frame) * fraction)]] = True
    return selected


def counts(labels: pd.Series, selected: pd.Series) -> dict:
    if labels.isna().any() or not labels.isin([0, 1, True, False]).all():
        raise ValueError("Complete binary outcomes required")
    if not labels.index.equals(selected.index):
        raise ValueError("Selection/outcome indexes differ")
    y = labels.astype(bool)
    n, positives, reviews = len(y), int(y.sum()), int(selected.sum())
    found = int((y & selected).sum())
    return dict(services=n, positive_windows=positives, reviews=reviews,
                callbacks_found=found, reviews_without_callback=reviews-found,
                callbacks_missed=positives-found,
                callback_capture=found/positives if positives else None,
                review_precision=found/reviews if reviews else None)


def holdout_rows(source: dict) -> list[dict]:
    if source["status"] != "retrospective_future_services_not_online_prediction" or (
        source["rows"], source["positive_rows"]) != (100, 5):
        raise ValueError("Frozen historical population changed")
    rows = []
    for order, role, label in [(1, "selected_ap", "Current model"), (2, "reference", "Earlier model")]:
        item = source["results"][role]
        s = item["segments"]["all"]
        if (s["rows"], s["positive_rows"], s["budget_alerts"]) != (100, 5, 20):
            raise ValueError("Review population or budget differs")
        if s["budget_TP"] + s["budget_FN"] != 5 or s["budget_TP"] + s["budget_FP"] != 20:
            raise ValueError("Review counts do not reconcile")
        rows.append(dict(rule_order=order, review_rule=label, evidence_type="Observed historical ranking",
            services=100, positive_windows=5, reviews=20, callbacks_found=s["budget_TP"],
            reviews_without_callback=s["budget_FP"], callbacks_missed=s["budget_FN"],
            callback_capture=s["budget_TP"]/5, review_precision=s["budget_TP"]/20,
            cohort_start=source["start"], cohort_end=source["end"],
            limitation="Only five positive service windows; batch ranking, not a tested daily queue"))
    rows.append(dict(rows[0], rule_order=3, review_rule="Random selection (expected)",
        evidence_type="Mathematical expectation, not observed staff performance", callbacks_found=1,
        reviews_without_callback=19, callbacks_missed=4, callback_capture=.2, review_precision=.05))
    return rows


def feature_rows(source: dict) -> list[dict]:
    labels = {"et10_history_only": "Service history; no weather or mapped environment",
              "et10_no_environment": "Service history and weather",
              "v5_control": "Service history, weather and mapped environment",
              "et10_landcover": "Current inputs plus land cover"}
    rows = []
    for order, (name, label) in enumerate(labels.items(), 1):
        matches = [x for x in source["candidates"] if x["name"] == name]
        if len(matches) != 1 or len(matches[0]["folds"]) != 3:
            raise ValueError("Missing comparison or unexpected development folds")
        x = matches[0]
        rows.append(dict(feature_order=order, input_set=label,
            mean_average_precision=x["mean_ap"], mean_callback_capture=x["mean_review_recall"],
            validation_folds=3, review_fraction=.2,
            evidence_type="Exploratory 2025 chronological development; not fresh test accuracy",
            limitation="Mean of three fold metrics; additional inputs did not consistently improve both measures"))
    return rows


def development_rows(predictions: pd.DataFrame, features: pd.DataFrame) -> list[dict]:
    for frame in (predictions, features):
        if frame[KEYS].isna().any().any() or frame.duplicated(KEYS).any():
            raise ValueError("Missing or duplicate development keys")
    joined = predictions.merge(features[KEYS + [HISTORY, TARGET]], on=KEYS, how="left",
        suffixes=("", "_source"), validate="one_to_one", indicator=True)
    if not joined._merge.eq("both").all() or not joined[TARGET].eq(joined[TARGET + "_source"]).all():
        raise ValueError("Development predictors/outcomes do not align")
    if not joined.fold.isin(["2025_q2", "2025_q3", "2025_q4"]).all() or (
        pd.to_datetime(joined.anchor_date) >= pd.Timestamp("2026-01-01")).any():
        raise ValueError("Only declared 2025 development folds are permitted")
    if not joined.raw_probability.between(0, 1).all():
        raise ValueError("Invalid model scores")
    result = []
    for fold, frame in joined.groupby("fold", sort=True):
        for rule, score in [("Current model", "raw_probability"), ("Previous property callbacks", HISTORY)]:
            result.append(dict(fold=fold, review_rule=rule,
                **counts(frame[TARGET], select_exact(frame, score)),
                history_missing_services=int(frame[HISTORY].isna().sum()),
                evidence_type="Exploratory already-inspected development; exact 20% budget with deterministic ties"))
        expected = result[-1].copy()
        expected.update(review_rule="Random selection (expected)",
            callbacks_found=expected["reviews"]*expected["positive_windows"]/expected["services"])
        expected.update(reviews_without_callback=expected["reviews"]-expected["callbacks_found"],
            callbacks_missed=expected["positive_windows"]-expected["callbacks_found"],
            callback_capture=expected["reviews"]/expected["services"] if expected["positive_windows"] else None,
            review_precision=expected["positive_windows"]/expected["services"])
        result.append(expected)
    return result


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    prediction_path = ROOT / "outputs/cp2-v2/model_corrected_v5/selected_ap/development_predictions.csv"
    input_path = ROOT / "outputs/cp2-v2/source_refresh_20260927/corrected_training/dataset_input.json"
    source = json.loads(input_path.read_text())
    features = pd.DataFrame(source["records"], columns=source["columns"])
    predictions = pd.read_csv(prediction_path, dtype={"sales_record_id": str})
    features["sales_record_id"] = features.sales_record_id.astype(str)
    for frame in (predictions, features):
        frame["anchor_date"] = pd.to_datetime(frame.anchor_date).dt.strftime("%Y-%m-%d")
    tables = {
        "cp2_review_capacity": holdout_rows(read("config/warranty_new_holdout_v5.json")),
        "cp2_environment_comparison": feature_rows(read("config/cp2_broad_challenger_results_v1.json")),
        "cp2_followup_baselines": development_rows(predictions, features),
    }
    for name, rows in tables.items():
        write_csv(ROOT / "dbt/seeds" / f"{name}.csv", rows)
    output = ROOT / "outputs/project_value_review/20261011"
    output.mkdir(parents=True, exist_ok=True)
    sources = [prediction_path, input_path, ROOT / "config/warranty_new_holdout_v5.json",
               ROOT / "config/cp2_broad_challenger_results_v1.json"]
    receipt = {"source_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in sources},
               "seed_rows": {name: len(rows) for name, rows in tables.items()},
               "model_fitted": False, "new_holdout_evaluated": False,
               "frozen_bundle_sha256": sha(ROOT / "outputs/cp2-v2/prospective_callback_v2/bundle.json")}
    (output / "build_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt["seed_rows"]))


if __name__ == "__main__":
    main()
