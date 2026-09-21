"""Tune and calibrate the prediction-safe residential 3x 30-day model.

All model/feature/threshold choices use pre-2026 walk-forward predictions.
The mature 2026 cohort is used only for reporting the frozen result.
"""

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from train_warranty_risk_baseline import (
    LOCATION,
    MAX_BYTES,
    PROJECT,
    RISK_CORE_NO_TEAM_BOOLEAN_FEATURES,
    RISK_CORE_NO_TEAM_CATEGORICAL_FEATURES,
    RISK_CORE_NO_TEAM_FEATURES,
    RISK_CORE_NO_TEAM_NUMERIC_FEATURES,
    logistic_pipeline,
    tree_pipeline,
)


SOURCE = f"{PROJECT}.analytics_ml.warranty_risk_3session_dataset"
TARGET = "warranty_signal_within_30d"
DEVELOPMENT_FOLDS = [
    ("2025_q2", date(2025, 4, 1), date(2025, 7, 1)),
    ("2025_q3", date(2025, 7, 1), date(2025, 10, 1)),
    ("2025_q4", date(2025, 10, 1), date(2026, 1, 1)),
]
REPORTING_START = date(2026, 1, 1)
REPORTING_END = date(2026, 8, 1)
MINIMUM_FOLDS_FOR_AUTOMATIC_FEATURE_REMOVAL = 4
SEGMENT_COLUMNS = [
    "pest_category", "premise_type", "package_category", "area_cell",
]

SQL = f"""
select sales_record_id, prediction_anchor_date, area_cell,
       warranty_signal_within_30d, complete_prior_14d_weather,
       {', '.join(RISK_CORE_NO_TEAM_FEATURES)}
from `{SOURCE}`
where warranty_signal_within_30d is not null
"""


def feature_types(features: list[str]) -> tuple[list[str], list[str], list[str]]:
    return (
        [f for f in RISK_CORE_NO_TEAM_NUMERIC_FEATURES if f in features],
        [f for f in RISK_CORE_NO_TEAM_BOOLEAN_FEATURES if f in features],
        [f for f in RISK_CORE_NO_TEAM_CATEGORICAL_FEATURES if f in features],
    )


def build_model(name: str, features: list[str]):
    numeric, boolean, categorical = feature_types(features)
    if name == "logistic_l2":
        return logistic_pipeline(numeric, boolean, categorical)
    if name == "hist_gradient_boosting":
        return tree_pipeline(
            HistGradientBoostingClassifier(
                learning_rate=0.04, max_iter=300, max_leaf_nodes=11,
                min_samples_leaf=20, l2_regularization=2.0,
                random_state=42),
            numeric, boolean, categorical)
    settings = {
        "rf_shallow": dict(max_depth=5, min_samples_leaf=15),
        "rf_balanced": dict(max_depth=8, min_samples_leaf=10),
        "rf_regularized": dict(max_depth=6, min_samples_leaf=20),
    }[name]
    return tree_pipeline(
        RandomForestClassifier(
            n_estimators=500, class_weight="balanced_subsample",
            random_state=42, n_jobs=-1, **settings),
        numeric, boolean, categorical)


def probability_metrics(y: pd.Series, probability: np.ndarray) -> dict[str, float]:
    return {
        "roc_auc": float(roc_auc_score(y, probability)),
        "average_precision": float(average_precision_score(y, probability)),
        "brier_score": float(brier_score_loss(y, probability)),
    }


def threshold_metrics(y: pd.Series, probability: np.ndarray,
                      threshold: float) -> dict[str, float]:
    alert = probability >= threshold
    return {
        "precision": float(precision_score(y, alert, zero_division=0)),
        "recall": float(recall_score(y, alert, zero_division=0)),
        "f1": float(f1_score(y, alert, zero_division=0)),
        "alert_rows": int(alert.sum()),
    }


def walk_forward(frame: pd.DataFrame, model_name: str,
                 features: list[str], include_importance: bool = False):
    metric_rows, prediction_frames, importance_rows = [], [], []
    for fold_name, test_start, test_end in DEVELOPMENT_FOLDS:
        train = frame[frame["prediction_anchor_date"] < test_start]
        test = frame[(frame["prediction_anchor_date"] >= test_start)
                     & (frame["prediction_anchor_date"] < test_end)]
        model = build_model(model_name, features).fit(
            train[features], train[TARGET].astype(bool))
        probability = model.predict_proba(test[features])[:, 1]
        y = test[TARGET].astype(bool)
        metric_rows.append({
            "model_name": model_name, "fold_name": fold_name,
            "training_rows": len(train), "test_rows": len(test),
            "positive_rows": int(y.sum()), **probability_metrics(y, probability),
        })
        predictions = test[["sales_record_id", "prediction_anchor_date"]].copy()
        predictions["fold_name"] = fold_name
        predictions["actual_signal"] = y.to_numpy()
        predictions["raw_probability"] = probability
        prediction_frames.append(predictions)
        if include_importance:
            result = permutation_importance(
                model, test[features], y, scoring="average_precision",
                n_repeats=3, random_state=42, n_jobs=-1)
            importance_rows.extend({
                "model_name": model_name, "fold_name": fold_name,
                "feature_name": feature,
                "importance_mean": float(result.importances_mean[index]),
                "importance_std": float(result.importances_std[index]),
            } for index, feature in enumerate(features))
    return (pd.DataFrame(metric_rows),
            pd.concat(prediction_frames, ignore_index=True),
            pd.DataFrame(importance_rows))


def calibrate(oof: pd.DataFrame, raw_probability: np.ndarray):
    clipped = np.clip(raw_probability, 1e-5, 1 - 1e-5)
    logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    y = oof["actual_signal"].astype(bool)
    calibrator = LogisticRegression(C=1.0, max_iter=1000).fit(logits, y)
    if calibrator.coef_[0, 0] <= 0:
        return None, raw_probability, "calibration_skipped_nonpositive_slope"
    return (calibrator, calibrator.predict_proba(logits)[:, 1],
            "platt_on_pooled_pre_2026_walk_forward_predictions")


def apply_calibrator(calibrator, raw_probability: np.ndarray) -> np.ndarray:
    if calibrator is None:
        return raw_probability
    clipped = np.clip(raw_probability, 1e-5, 1 - 1e-5)
    logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    return calibrator.predict_proba(logits)[:, 1]


def choose_thresholds(y: pd.Series, probability: np.ndarray) -> tuple[float, float]:
    candidates = np.linspace(0.05, 0.95, 181)
    monitor_candidates = []
    for value in candidates:
        metrics = threshold_metrics(y, probability, float(value))
        if metrics["recall"] >= 0.85 and metrics["alert_rows"] >= 20:
            monitor_candidates.append(float(value))
    if not monitor_candidates:
        raise ValueError("No monitor threshold achieves the required 0.85 recall")
    monitor = max(monitor_candidates)
    monitor_precision = threshold_metrics(y, probability, monitor)["precision"]
    high_candidates = []
    for value in candidates[candidates > monitor]:
        metrics = threshold_metrics(y, probability, float(value))
        if (metrics["recall"] >= 0.40 and metrics["alert_rows"] >= 20
                and metrics["precision"] >= monitor_precision + 0.05):
            high_candidates.append((metrics["precision"], metrics["recall"], float(value)))
    if not high_candidates:
        high = min(0.95, monitor + 0.10)
    else:
        high = max(high_candidates, key=lambda item: (item[0], item[1], item[2]))[2]
    return monitor, high


def main() -> None:
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    dry = client.query(SQL, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False))
    if dry.total_bytes_processed > MAX_BYTES:
        raise SystemExit("Tuning query exceeds 100 MiB cap")
    frame = pd.DataFrame(dict(row) for row in client.query(
        SQL, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES)
    ).result(timeout=630))
    frame["prediction_anchor_date"] = pd.to_datetime(
        frame["prediction_anchor_date"]).dt.date
    for column in RISK_CORE_NO_TEAM_BOOLEAN_FEATURES + [
            "complete_prior_14d_weather", TARGET]:
        frame[column] = frame[column].astype("boolean")
    frame = frame[frame["complete_prior_14d_weather"].fillna(False)].copy()
    run_utc = datetime.now(timezone.utc)

    candidate_frames = []
    for model_name in (
            "logistic_l2", "rf_shallow", "rf_balanced", "rf_regularized",
            "hist_gradient_boosting"):
        metrics, _, _ = walk_forward(
            frame, model_name, RISK_CORE_NO_TEAM_FEATURES)
        candidate_frames.append(metrics)
    candidate_metrics = pd.concat(candidate_frames, ignore_index=True)
    summary = candidate_metrics.groupby("model_name", as_index=False).agg(
        mean_roc_auc=("roc_auc", "mean"),
        mean_average_precision=("average_precision", "mean"),
        average_precision_std=("average_precision", "std"),
        mean_brier_score=("brier_score", "mean"),
    )
    selected_model = str(summary.sort_values(
        ["mean_average_precision", "mean_roc_auc"], ascending=False
    ).iloc[0]["model_name"])

    _, _, importance = walk_forward(
        frame, selected_model, RISK_CORE_NO_TEAM_FEATURES, include_importance=True)
    stability = importance.groupby("feature_name", as_index=False).agg(
        mean_importance=("importance_mean", "mean"),
        importance_std_across_folds=("importance_mean", "std"),
        positive_fold_count=("importance_mean", lambda values: int((values > 0).sum())),
        evaluated_fold_count=("importance_mean", "size"),
    )
    stable_features = stability[
        (stability["positive_fold_count"] >= 2)
        & (stability["mean_importance"] > 0)
    ]["feature_name"].tolist()
    if len(stable_features) < 15:
        stable_features = stability.sort_values(
            "mean_importance", ascending=False).head(15)["feature_name"].tolist()
    full_metrics = candidate_metrics[candidate_metrics["model_name"] == selected_model]
    reduced_metrics, reduced_oof, _ = walk_forward(
        frame, selected_model, stable_features)
    full_mean_ap = float(full_metrics["average_precision"].mean())
    reduced_mean_ap = float(reduced_metrics["average_precision"].mean())
    paired_ap = full_metrics[["fold_name", "average_precision"]].merge(
        reduced_metrics[["fold_name", "average_precision"]],
        on="fold_name", suffixes=("_full", "_stable"))
    stable_does_not_collapse_a_fold = bool((
        paired_ap["average_precision_stable"]
        >= paired_ap["average_precision_full"] - 0.01).all())
    if (len(DEVELOPMENT_FOLDS) >= MINIMUM_FOLDS_FOR_AUTOMATIC_FEATURE_REMOVAL
            and reduced_mean_ap >= full_mean_ap - 0.005
            and stable_does_not_collapse_a_fold):
        selected_features = stable_features
        selected_feature_set = "stable_prediction_safe_features_v2"
        selected_oof = reduced_oof
    else:
        selected_features = list(RISK_CORE_NO_TEAM_FEATURES)
        selected_feature_set = "prediction_safe_risk_core_without_team_v2"
        _, selected_oof, _ = walk_forward(
            frame, selected_model, selected_features)
    reduced_metrics["model_name"] = f"{selected_model}_stable_subset"
    stability["selected"] = stability["feature_name"].isin(selected_features)
    stability["run_utc"] = run_utc

    calibrator, oof_calibrated, calibration_method = calibrate(
        selected_oof, selected_oof["raw_probability"].to_numpy())
    selected_oof["calibrated_probability"] = oof_calibrated
    monitor_threshold, high_threshold = choose_thresholds(
        selected_oof["actual_signal"].astype(bool), oof_calibrated)

    training = frame[frame["prediction_anchor_date"] < REPORTING_START]
    reporting = frame[(frame["prediction_anchor_date"] >= REPORTING_START)
                      & (frame["prediction_anchor_date"] < REPORTING_END)].copy()
    final_model = build_model(selected_model, selected_features).fit(
        training[selected_features], training[TARGET].astype(bool))
    raw_probability = final_model.predict_proba(reporting[selected_features])[:, 1]
    probability = apply_calibrator(calibrator, raw_probability)
    y = reporting[TARGET].astype(bool)
    reporting["raw_probability"] = raw_probability
    reporting["calibrated_probability"] = probability
    reporting["risk_percentile"] = reporting[
        "calibrated_probability"].rank(method="max", pct=True)
    reporting["actual_signal"] = y.to_numpy()
    reporting["run_utc"] = run_utc

    evaluation_rows = []
    level_metrics = {}
    for level, percentile_cutoff in (
            ("MONITOR_OR_HIGHER", 0.50), ("HIGH_RISK", 0.80)):
        alert = reporting["risk_percentile"] > percentile_cutoff
        row = {
            "run_utc": run_utc, "alert_level": level,
            "threshold_type": "within_scoring_batch_risk_percentile",
            "threshold": percentile_cutoff,
            "reporting_rows": len(reporting), "positive_rows": int(y.sum()),
            **probability_metrics(y, probability),
            "precision": float(precision_score(y, alert, zero_division=0)),
            "recall": float(recall_score(y, alert, zero_division=0)),
            "f1": float(f1_score(y, alert, zero_division=0)),
            "alert_rows": int(alert.sum()),
        }
        level_metrics[level] = row
        evaluation_rows.append(row)
    high_risk_supported = bool(
        level_metrics["HIGH_RISK"]["precision"]
        >= level_metrics["MONITOR_OR_HIGHER"]["precision"] + 0.05)
    for row in evaluation_rows:
        row["tier_supported"] = (
            True if row["alert_level"] == "MONITOR_OR_HIGHER"
            else high_risk_supported)
    reporting["risk_level"] = np.where(
        reporting["risk_percentile"] > 0.50, "PRIORITY_REVIEW", "LOW")
    evaluation = pd.DataFrame(evaluation_rows)

    # Reporting-period comparison is diagnostic only and never changes the
    # already selected model or feature set.
    reporting_comparison_rows = []
    for comparison_name, comparison_features, comparison_oof in (
            ("full_prediction_safe", list(RISK_CORE_NO_TEAM_FEATURES), None),
            ("stable_subset", stable_features, reduced_oof)):
        if comparison_oof is None:
            _, comparison_oof, _ = walk_forward(
                frame, selected_model, comparison_features)
        comparison_calibrator, _, comparison_calibration_method = calibrate(
            comparison_oof, comparison_oof["raw_probability"].to_numpy())
        comparison_model = build_model(selected_model, comparison_features).fit(
            training[comparison_features], training[TARGET].astype(bool))
        comparison_raw = comparison_model.predict_proba(
            reporting[comparison_features])[:, 1]
        comparison_probability = apply_calibrator(
            comparison_calibrator, comparison_raw)
        reporting_comparison_rows.append({
            "run_utc": run_utc, "comparison_name": comparison_name,
            "feature_count": len(comparison_features),
            "calibration_method": comparison_calibration_method,
            **probability_metrics(y, comparison_probability),
        })
    reporting_comparison = pd.DataFrame(reporting_comparison_rows)
    selection = pd.DataFrame([{
        "run_utc": run_utc,
        "model_version": "warranty_risk_residential_3x_30d_v3",
        "selected_model": selected_model,
        "selected_feature_set": selected_feature_set,
        "selected_feature_count": len(selected_features),
        "full_feature_mean_pre_2026_ap": full_mean_ap,
        "stable_feature_mean_pre_2026_ap": reduced_mean_ap,
        "stable_subset_passed_every_fold_guard": stable_does_not_collapse_a_fold,
        "development_fold_count": len(DEVELOPMENT_FOLDS),
        "minimum_folds_for_automatic_feature_removal": (
            MINIMUM_FOLDS_FOR_AUTOMATIC_FEATURE_REMOVAL),
        "calibration_method": calibration_method,
        "monitor_probability_reference_threshold": monitor_threshold,
        "high_risk_probability_reference_threshold": high_threshold,
        "operational_risk_banding": (
            "priority_review_top_50pct_within_scoring_batch;_"
            "high_risk_disabled_until_supported"),
        "monitor_percentile_cutoff": 0.50,
        "high_risk_percentile_cutoff": 0.80,
        "high_risk_tier_supported": high_risk_supported,
        "unsupported_high_risk_reason": (
            None if high_risk_supported else
            "top_20pct_precision_not_0_05_above_monitor_or_higher_precision"),
        "selection_data_end_exclusive": REPORTING_START,
        "reporting_data_start": REPORTING_START,
        "status": "VALIDATED_EXPERIMENTAL_NOT_CAUSAL",
    }])
    selected_feature_table = pd.DataFrame({
        "run_utc": run_utc,
        "model_version": "warranty_risk_residential_3x_30d_v3",
        "feature_order": range(1, len(selected_features) + 1),
        "feature_name": selected_features,
    })
    for data in (candidate_metrics, summary, importance, reduced_metrics,
                 selected_oof, reporting):
        data["run_utc"] = run_utc
    outputs = {
        "warranty_risk_tuning_fold_metrics": candidate_metrics,
        "warranty_risk_tuning_summary": summary,
        "warranty_risk_stable_subset_fold_metrics": reduced_metrics,
        "warranty_risk_feature_stability": stability,
        "warranty_risk_selected_features_v3": selected_feature_table,
        "warranty_risk_oof_predictions_v3": selected_oof,
        "warranty_risk_reporting_predictions_v3": reporting[[
            "sales_record_id", "prediction_anchor_date", *SEGMENT_COLUMNS,
            "actual_signal", "raw_probability", "calibrated_probability",
            "risk_percentile", "risk_level", "run_utc"]],
        "warranty_risk_reporting_evaluation_v3": evaluation,
        "warranty_risk_reporting_feature_comparison_v3": reporting_comparison,
        "warranty_risk_model_selection_v3": selection,
    }
    for table, data in outputs.items():
        client.load_table_from_dataframe(
            data, f"{PROJECT}.analytics_ml.{table}",
            job_config=bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
        ).result(timeout=120)
        print(f"WROTE analytics_ml.{table}: {len(data)} rows")
    print(summary.sort_values("mean_average_precision", ascending=False)
          .round(4).to_string(index=False))
    print(selection.to_string(index=False))
    print(evaluation.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
