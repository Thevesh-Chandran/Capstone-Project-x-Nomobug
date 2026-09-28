"""Freeze one callback cohort and compare identical contracts with/without flood.

Select all candidates using pre-2026 folds only. The previously inspected 2026
period is diagnostic. Also hold the baseline winner's family and non-flood
features fixed to isolate the effect of adding observed flood measurements.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

try:
    from scripts import benchmark_warranty_models as benchmark
except ModuleNotFoundError:
    import benchmark_warranty_models as benchmark


SOURCE = f"{benchmark.PROJECT}.analytics_ml.warranty_callback_flood_dataset"
FEATURE_SETS = ["compact_history", "base", "base_weather_environment"]
MODELS = ["extra_trees_depth6", "rf_depth3", "rf_depth6",
          "catboost_depth4_plain", "lr_c1.0_plain", "dummy_prior"]
OBSERVATION_ONLY_NUMERIC = ["gfm_prior_30d_observed_days",
                            "gfm_days_since_valid_observation",
                            "gfm_prior_30d_max_valid_fraction_1km"]


def configure_contracts(flood: bool, reported_flood: bool = False) -> None:
    """Reset explicit experiment contracts so sequential modes cannot leak features."""
    benchmark.CATEGORICAL[:] = [
        "pest_category", "package_category", "calendar_pest_text_category",
        "calendar_service_method_category"]
    benchmark.FEATURE_SETS.clear()
    benchmark.FEATURE_SETS.update({
        "compact_history": list(benchmark.COMPACT_NUMERIC),
        "base": list(benchmark.BASE_NUMERIC),
        "base_weather_environment": (list(benchmark.BASE_NUMERIC)
                                      + list(benchmark.WEATHER_NUMERIC)
                                      + list(benchmark.ENVIRONMENT_NUMERIC)
                                      + list(benchmark.DERIVED_NUMERIC)),
    })
    benchmark.configure_premise_context(True)
    benchmark.configure_pest_context(True)
    benchmark.configure_flood_context(flood)
    benchmark.configure_reported_flood_context(reported_flood)


def configure_observation_only_contracts() -> None:
    configure_contracts(True)
    for feature_set, numeric in list(benchmark.FEATURE_SETS.items()):
        benchmark.FEATURE_SETS[feature_set] = [
            column for column in numeric if column not in benchmark.FLOOD_NUMERIC
        ] + OBSERVATION_ONLY_NUMERIC


def split_receipt(frame: pd.DataFrame) -> list[dict]:
    receipts = []
    windows = benchmark.DEVELOPMENT_FOLDS + [
        ("diagnostic_2026", benchmark.REPORTING_START, None)]
    for name, start, end in windows:
        train, test, audit = benchmark.purged_split(frame, start, end)
        receipt = {"fold": name, "training_rows": len(train), "test_rows": len(test),
                   "training_positive_rows": int(train[benchmark.TARGET].sum()),
                   "test_positive_rows": int(test[benchmark.TARGET].sum()), **audit}
        for label, partition in (("train", train), ("test", test)):
            canonical = partition[benchmark.KEYS + ["validation_group"]].to_json(
                orient="records", date_format="iso")
            receipt[f"{label}_keys_sha256"] = hashlib.sha256(
                canonical.encode("utf-8")).hexdigest()
        receipts.append(receipt)
    return receipts


def evaluate_locked_candidate(frame: pd.DataFrame, feature_set: str, model_name: str,
                              output: Path) -> dict:
    """Fit a development-selected contract without any diagnostic selection."""
    numeric = benchmark.FEATURE_SETS[feature_set]
    features = numeric + benchmark.CATEGORICAL
    oof_parts = []
    fold_metrics = []
    for name, start, end in benchmark.DEVELOPMENT_FOLDS:
        train, test, audit = benchmark.purged_split(frame, start, end)
        if (len(train) < 30 or len(test) < 15 or train[benchmark.TARGET].nunique() < 2
                or min(test[benchmark.TARGET].sum(), (~test[benchmark.TARGET]).sum()) < 3):
            continue
        fitted = benchmark.make_model(model_name, numeric).fit(
            train[features], train[benchmark.TARGET])
        part = test[benchmark.KEYS + ["validation_group"]].copy()
        part["raw_probability"] = fitted.predict_proba(test[features])[:, 1]
        part["fold"] = name
        oof_parts.append(part)
        fold_metrics.append({"fold": name, "training_rows": len(train), **audit,
                             **benchmark.score(test[benchmark.TARGET],
                                               part["raw_probability"])})
    if len(oof_parts) < 2:
        raise ValueError("Locked flood ablation requires two development folds")
    oof = pd.concat(oof_parts, ignore_index=True)
    calibrator, metadata = benchmark.fit_calibrator(
        oof[benchmark.TARGET], oof["raw_probability"])
    oof["probability"] = benchmark.apply_calibrator(calibrator, oof["raw_probability"])
    threshold = benchmark.select_threshold(oof[benchmark.TARGET], oof["probability"])
    train, diagnostic, audit = benchmark.purged_split(frame, benchmark.REPORTING_START)
    fitted = benchmark.make_model(model_name, numeric).fit(
        train[features], train[benchmark.TARGET])
    predictions = diagnostic[benchmark.KEYS + ["validation_group"]].copy()
    predictions["raw_probability"] = fitted.predict_proba(diagnostic[features])[:, 1]
    predictions["probability"] = benchmark.apply_calibrator(
        calibrator, predictions["raw_probability"])
    predictions["threshold"] = threshold
    output.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output / "diagnostic_predictions.csv", index=False)
    oof.to_csv(output / "development_predictions.csv", index=False)
    pd.DataFrame(fold_metrics).to_csv(output / "fold_metrics.csv", index=False)
    joblib.dump({"pipeline": fitted, "features": features, "calibrator": calibrator,
                 "threshold": threshold, "population": str(frame["population"].iloc[0]),
                 "feature_preparation_options": benchmark.feature_preparation_options(),
                 "business_target": benchmark.business_target_metadata(
                     list(frame["population"].unique())),
                 "feature_preparation": "benchmark_warranty_models.prepare_frame",
                 "training_outcome_end_exclusive": benchmark.REPORTING_START,
                 "purpose": "frozen_diagnostic_model_not_deployment"},
                output / "selected_model.joblib")
    return {"selected_model": model_name, "selected_feature_set": feature_set,
            "selected_features": features,
            "feature_preparation_options": benchmark.feature_preparation_options(),
            "development_fold_metrics": fold_metrics,
            "development_selection": {
                "mean_average_precision": float(np.mean([
                    fold["average_precision"] for fold in fold_metrics])),
                "sd_average_precision": float(np.std([
                    fold["average_precision"] for fold in fold_metrics], ddof=1)),
                "mean_roc_auc": float(np.mean([fold["roc_auc"] for fold in fold_metrics])),
                "development_folds": len(fold_metrics),
            },
            "calibration": metadata, "development_threshold": threshold,
            "diagnostic_split_audit": audit,
            "diagnostic_2026": benchmark.score(
                predictions[benchmark.TARGET], predictions["probability"], threshold),
            "diagnostic_priority_top20pct": benchmark.priority_review_metrics(
                predictions[benchmark.TARGET], predictions["probability"])}


def paired_bootstrap(baseline: pd.DataFrame, flood: pd.DataFrame,
                     repeats: int = 500) -> dict:
    """Use identical connected-component samples for flood minus baseline deltas."""
    keys = ["population", "sales_record_id", "anchor_date"]
    joined = baseline.merge(flood, on=keys, suffixes=("_baseline", "_flood"),
                            how="outer", validate="one_to_one", indicator=True)
    if not joined["_merge"].eq("both").all():
        raise ValueError("Paired diagnostic predictions have different anchors")
    for column in (benchmark.TARGET, "validation_group", "outcome_end_date"):
        if not joined[f"{column}_baseline"].equals(joined[f"{column}_flood"]):
            raise ValueError(f"Paired diagnostic predictions disagree on {column}")
    groups = [group for _, group in joined.groupby("validation_group_baseline", sort=False)]
    rng = np.random.default_rng(42)
    samples = []
    for _ in range(repeats):
        sample = pd.concat([groups[index] for index in
                            rng.integers(0, len(groups), len(groups))])
        if sample[f"{benchmark.TARGET}_baseline"].nunique() < 2:
            continue
        scores = {}
        for mode in ("baseline", "flood"):
            scores[mode] = benchmark.score(
                sample[f"{benchmark.TARGET}_{mode}"], sample[f"probability_{mode}"],
                float(sample[f"threshold_{mode}"].iloc[0]))
        samples.append({metric: scores["flood"][metric] - scores["baseline"][metric]
                        for metric in ("roc_auc", "average_precision", "brier_score",
                                       "accuracy", "precision", "recall", "f1")})
    return {"direction": "flood_minus_baseline", "valid_repeats": len(samples),
            "groups": len(groups), "confidence_95pct": {
                metric: np.quantile([sample[metric] for sample in samples],
                                    [0.025, 0.975]).tolist() if samples else None
                for metric in ("roc_auc", "average_precision", "brier_score",
                               "accuracy", "precision", "recall", "f1")}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--input-json", type=Path)
    parser.add_argument("--reported-flood-context", action="store_true",
                        help="Add separate locked regional GDACS report comparison")
    parser.add_argument("--output-dir", type=Path,
                        default=benchmark.ROOT / "outputs/cp2-v2/flood_model_comparison")
    parser.add_argument("--bootstrap-repeats", type=int, default=500)
    args = parser.parse_args()
    if not 1 <= args.bootstrap_repeats <= 500:
        raise SystemExit("Bootstrap repeats must be between 1 and 500")
    configure_contracts(True, args.reported_flood_context)
    raw = (benchmark.load_dataset_input(args.input_json) if args.input_json
           else benchmark.read_frame(args.source))
    if raw.empty or raw["population"].nunique() != 1:
        raise SystemExit("Flood comparison requires one nonempty callback population")
    digest = benchmark.persist_dataset_input(raw, args.output_dir)
    raw = benchmark.load_dataset_input(args.output_dir / "dataset_input.json")
    results, receipts = {}, {}
    population = str(raw["population"].iloc[0])
    for mode, enabled in (("baseline", False), ("flood", True)):
        configure_contracts(enabled)
        frame = benchmark.prepare_frame(raw)
        receipts[mode] = split_receipt(frame)
        results[mode] = benchmark.benchmark_population(
            frame, args.output_dir / mode, args.bootstrap_repeats, MODELS)
        if "diagnostic_2026" not in results[mode]:
            raise SystemExit(f"Insufficient support for {mode} flood comparison")
        (args.output_dir / mode / "benchmark_results.json").write_text(json.dumps({
            "source": args.source, "dataset_input_sha256": digest,
            "dataset_input_file": "../dataset_input.json",
            "feature_preparation_options": benchmark.feature_preparation_options(),
            "reporting_caveat": "2026 already inspected; diagnostic only",
            "populations": [results[mode]],
        }, indent=2, allow_nan=False), encoding="utf-8")
    if receipts["baseline"] != receipts["flood"]:
        raise ValueError("Baseline/flood cohorts or purged splits differ")
    baseline = results["baseline"]
    configure_contracts(True)
    frame = benchmark.prepare_frame(raw)
    locked = evaluate_locked_candidate(
        frame, baseline["selected_feature_set"], baseline["selected_model"],
        args.output_dir / "locked_flood")
    baseline_predictions = pd.read_csv(
        args.output_dir / "baseline" / f"{population}_diagnostic_predictions.csv")
    flood_predictions = pd.read_csv(args.output_dir / "locked_flood/diagnostic_predictions.csv")
    paired = paired_bootstrap(baseline_predictions, flood_predictions, args.bootstrap_repeats)
    # A satellite observation is a changing geography/coverage proxy. Hold that
    # context separately from detected-flood measurements before attributing gains.
    configure_observation_only_contracts()
    observation_control = evaluate_locked_candidate(
        frame, baseline["selected_feature_set"], baseline["selected_model"],
        args.output_dir / "locked_observation_control")
    observation_predictions = pd.read_csv(
        args.output_dir / "locked_observation_control/diagnostic_predictions.csv")
    observed_vs_baseline = paired_bootstrap(
        baseline_predictions, observation_predictions, args.bootstrap_repeats)
    observed_vs_baseline["direction"] = "observation_control_minus_baseline"
    flood_vs_observed = paired_bootstrap(
        observation_predictions, flood_predictions, args.bootstrap_repeats)
    flood_vs_observed["direction"] = "full_flood_context_minus_observation_control"
    reported_result, reported_bootstrap = None, None
    if args.reported_flood_context:
        configure_contracts(False, True)
        regional_frame = benchmark.prepare_frame(raw)
        if split_receipt(regional_frame) != receipts["baseline"]:
            raise ValueError("Reported regional context changed baseline purged splits")
        reported_result = evaluate_locked_candidate(
            regional_frame, baseline["selected_feature_set"], baseline["selected_model"],
            args.output_dir / "locked_reported_flood")
        reported_predictions = pd.read_csv(
            args.output_dir / "locked_reported_flood/diagnostic_predictions.csv")
        reported_bootstrap = paired_bootstrap(
            baseline_predictions, reported_predictions, args.bootstrap_repeats)
        reported_bootstrap["direction"] = "reported_regional_flood_minus_baseline"
    locked_development_comparison = {
        "baseline": baseline["selection"],
        "baseline_plus_gfm8": locked["development_selection"],
        "baseline_plus_observation_control3": observation_control["development_selection"],
    }
    if reported_result is not None:
        locked_development_comparison["baseline_plus_reported_regional_flood4"] = (
            reported_result["development_selection"])
    development_winner = max(locked_development_comparison, key=lambda name: (
        locked_development_comparison[name]["mean_average_precision"],
        locked_development_comparison[name]["mean_roc_auc"]))
    for result in results.values():
        result["dataset_input_sha256"] = digest
    report = {
        "run_utc": datetime.now(timezone.utc).isoformat(), "source": args.source,
        "dataset_input_sha256": digest, "dataset_input_file": "dataset_input.json",
        "candidate_evaluations": sum(result["candidate_count"] for result in results.values()),
        "additional_locked_contract_evaluations": 2 + int(args.reported_flood_context),
        "models": MODELS, "non_flood_feature_sets": FEATURE_SETS,
        "flood_feature_contract": benchmark.FLOOD_NUMERIC,
        "feature_preparation_options": {"premise_context": True,
                                        "normalize_pest_context": True},
        "same_cohort_same_purged_splits": True, "split_receipts": receipts["baseline"],
        "selection_period_end_exclusive": benchmark.REPORTING_START,
        "reporting_caveat": "2026 already inspected; exploratory diagnostic comparison",
        "flood_interpretation": "prior_available_observed_nearby_flood_context_not_property_confirmation",
        "baseline": baseline, "flood": results["flood"],
        "locked_baseline_winner_plus_flood": locked,
        "locked_pair_bootstrap": paired,
        "observation_only_numeric_contract": OBSERVATION_ONLY_NUMERIC,
        "locked_baseline_winner_plus_observation_control": observation_control,
        "observation_control_minus_baseline_bootstrap": observed_vs_baseline,
        "full_flood_minus_observation_control_bootstrap": flood_vs_observed,
        "reported_regional_flood_numeric_contract": (
            benchmark.REPORTED_FLOOD_NUMERIC if args.reported_flood_context else None),
        "reported_regional_flood_interpretation": (
            "reported_regional_geometry_with_latest_update_plus_24h_availability_proxy_"
            "not_confirmed_household_flooding" if args.reported_flood_context else None),
        "locked_baseline_winner_plus_reported_regional_flood": reported_result,
        "reported_regional_flood_minus_baseline_bootstrap": reported_bootstrap,
        "locked_development_comparison": locked_development_comparison,
        "locked_variant_selected_on_development": development_winner,
    }
    (args.output_dir / "flood_comparison_results.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
