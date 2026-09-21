"""Walk-forward validation, error analysis, and model freeze evidence.

The selected outcome is a recorded Calendar warranty signal within 60 days
after a unique 3-of-3 event. It is not proof of biological recurrence or fault.
"""

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
from google.cloud import bigquery
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
    best_f1_threshold,
)
from tune_warranty_risk_model import build_model


SOURCE = f"{PROJECT}.analytics_ml.warranty_risk_3session_dataset"
TARGET = "warranty_signal_within_60d"
SEGMENT_COLUMNS = [
    "pest_category", "premise_type", "package_category", "area_cell",
    "property_history_band", "rain_band",
]
FOLDS = [
    ("2025_q2", date(2025, 4, 1), date(2025, 7, 1)),
    ("2025_q3", date(2025, 7, 1), date(2025, 10, 1)),
    ("2025_q4", date(2025, 10, 1), date(2026, 1, 1)),
    ("2026_mature", date(2026, 1, 1), date(2026, 8, 1)),
]

SQL = f"""
select sales_record_id, prediction_anchor_date, area_cell,
       warranty_signal_within_60d, complete_prior_14d_weather,
       {', '.join(RISK_CORE_NO_TEAM_FEATURES)}
from `{SOURCE}`
where warranty_signal_within_60d is not null
"""


def fit_model() -> object:
    return build_model("rf_regularized", list(RISK_CORE_NO_TEAM_FEATURES))


def add_segments(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    services = result["prior_property_service_events"].fillna(0)
    result["property_history_band"] = pd.cut(
        services, bins=[-1, 0, 1, 3, np.inf],
        labels=["NO_PRIOR", "ONE_PRIOR", "TWO_TO_THREE", "FOUR_PLUS"])
    rain = result["prior_7d_precipitation_mm"].fillna(0)
    result["rain_band"] = pd.cut(
        rain, bins=[-np.inf, 0, 20, 50, np.inf],
        labels=["DRY", "SOME_RAIN", "WET", "VERY_WET"],
        include_lowest=True)
    return result


def evaluate(y: pd.Series, probability: np.ndarray,
             threshold: float) -> dict[str, float]:
    alert = probability >= threshold
    return {
        "roc_auc": float(roc_auc_score(y, probability)),
        "average_precision": float(average_precision_score(y, probability)),
        "brier_score": float(brier_score_loss(y, probability)),
        "precision": float(precision_score(y, alert, zero_division=0)),
        "recall": float(recall_score(y, alert, zero_division=0)),
        "f1": float(f1_score(y, alert, zero_division=0)),
    }


def tuned_threshold(train: pd.DataFrame) -> tuple[float, float]:
    ordered = train.sort_values(["prediction_anchor_date", "sales_record_id"])
    cut = int(len(ordered) * 0.80)
    development, tuning = ordered.iloc[:cut], ordered.iloc[cut:]
    if development[TARGET].nunique() != 2 or tuning[TARGET].nunique() != 2:
        raise ValueError("Threshold split must contain both outcome classes")
    model = fit_model().fit(
        development[RISK_CORE_NO_TEAM_FEATURES], development[TARGET].astype(bool))
    probability = model.predict_proba(tuning[RISK_CORE_NO_TEAM_FEATURES])[:, 1]
    return best_f1_threshold(tuning[TARGET].astype(bool), probability)


def main() -> None:
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    dry = client.query(SQL, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False))
    if dry.total_bytes_processed > MAX_BYTES:
        raise SystemExit("Validation query exceeds 100 MiB cap")
    rows = [dict(row) for row in client.query(
        SQL, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES)
    ).result(timeout=630)]
    frame = add_segments(pd.DataFrame(rows))
    frame["prediction_anchor_date"] = pd.to_datetime(
        frame["prediction_anchor_date"]).dt.date
    for column in RISK_CORE_NO_TEAM_BOOLEAN_FEATURES + [
            "complete_prior_14d_weather", TARGET]:
        frame[column] = frame[column].astype("boolean")
    frame = frame[frame["complete_prior_14d_weather"].fillna(False)].copy()

    run_utc = datetime.now(timezone.utc)
    fold_rows = []
    final_predictions = None
    final_threshold = None
    for fold_name, test_start, test_end in FOLDS:
        train = frame[frame["prediction_anchor_date"] < test_start].copy()
        test = frame[(frame["prediction_anchor_date"] >= test_start)
                     & (frame["prediction_anchor_date"] < test_end)].copy()
        if min(len(train), len(test)) == 0 or train[TARGET].nunique() != 2 \
                or test[TARGET].nunique() != 2:
            raise SystemExit(f"Invalid walk-forward fold: {fold_name}")
        threshold, tuning_f1 = tuned_threshold(train)
        model = fit_model().fit(
            train[RISK_CORE_NO_TEAM_FEATURES], train[TARGET].astype(bool))
        probability = model.predict_proba(test[RISK_CORE_NO_TEAM_FEATURES])[:, 1]
        y = test[TARGET].astype(bool)
        metrics = evaluate(y, probability, threshold)
        fold_rows.append({
            "run_utc": run_utc, "fold_name": fold_name,
            "train_end_exclusive": test_start, "test_end_exclusive": test_end,
            "training_rows": len(train), "test_rows": len(test),
            "test_positive_rows": int(y.sum()),
            "test_prevalence": float(y.mean()), "threshold": threshold,
            "threshold_tuning_f1": tuning_f1, **metrics,
        })
        if fold_name == "2026_mature":
            final_threshold = threshold
            final_predictions = test[[
                "sales_record_id", "prediction_anchor_date", *SEGMENT_COLUMNS
            ]].copy()
            final_predictions["actual_signal"] = y.to_numpy()
            final_predictions["predicted_probability"] = probability
            final_predictions["alert"] = probability >= threshold

    assert final_predictions is not None and final_threshold is not None
    actual = final_predictions["actual_signal"].astype(bool)
    alert = final_predictions["alert"].astype(bool)
    final_predictions["error_type"] = np.select(
        [alert & actual, alert & ~actual, ~alert & actual],
        ["TRUE_POSITIVE", "FALSE_POSITIVE", "FALSE_NEGATIVE"],
        default="TRUE_NEGATIVE")
    final_predictions["run_utc"] = run_utc
    final_predictions["selected_horizon_days"] = 60
    final_predictions["frozen_threshold"] = final_threshold

    segment_rows = []
    for dimension in SEGMENT_COLUMNS:
        for value, group in final_predictions.groupby(dimension, dropna=False):
            y = group["actual_signal"].astype(bool)
            probability = group["predicted_probability"].to_numpy()
            group_alert = group["alert"].astype(bool)
            row = {
                "run_utc": run_utc, "segment_dimension": dimension,
                "segment_value": "MISSING" if pd.isna(value) else str(value),
                "row_count": len(group), "positive_rows": int(y.sum()),
                "prevalence": float(y.mean()),
                "false_positive_rows": int((group["error_type"] == "FALSE_POSITIVE").sum()),
                "false_negative_rows": int((group["error_type"] == "FALSE_NEGATIVE").sum()),
                "precision": float(precision_score(y, group_alert, zero_division=0)),
                "recall": float(recall_score(y, group_alert, zero_division=0)),
                "minimum_reliable_segment_rows": 20,
            }
            if len(group) >= 20 and y.nunique() == 2:
                row["roc_auc"] = float(roc_auc_score(y, probability))
                row["average_precision"] = float(
                    average_precision_score(y, probability))
                row["metric_status"] = "EVALUATED"
            else:
                row["roc_auc"] = None
                row["average_precision"] = None
                row["metric_status"] = "INSUFFICIENT_ROWS_OR_CLASSES"
            segment_rows.append(row)

    horizon_query = f"""
    select horizon_days,
           max(if(metric_name = 'roc_auc', metric_value, null)) as roc_auc,
           max(if(metric_name = 'average_precision', metric_value, null))
               as average_precision
    from `{PROJECT}.analytics_ml.warranty_risk_horizon_metrics`
    where starts_with(model_name, 'calibrated')
    group by horizon_days
    order by horizon_days
    """
    horizon_rows = [dict(row) for row in client.query(horizon_query).result()]
    reliable = [row for row in horizon_rows if row["roc_auc"] >= 0.55]
    best_ap = max(row["average_precision"] for row in reliable)
    selected = min(
        (row for row in reliable
         if row["average_precision"] >= best_ap - 0.01),
        key=lambda row: row["horizon_days"])
    selection_summary = pd.DataFrame([{
        "run_utc": run_utc,
        "selected_horizon_days": int(selected["horizon_days"]),
        "selected_feature_set": "risk_core_without_team_v1",
        "frozen_threshold": final_threshold,
        "selection_rule": (
            "shortest_horizon_with_roc_auc_at_least_0_55_and_average_precision_"
            "within_0_01_of_best_reliable_horizon"),
        "label_definition": (
            "recorded_calendar_warranty_signal_within_60d_after_3_of_3"),
        "release_status": "VALIDATED_EXPERIMENTAL_NOT_CAUSAL",
    }])
    if int(selected["horizon_days"]) != 60:
        raise SystemExit("Horizon selection no longer resolves to 60 days")

    outputs = {
        "warranty_risk_walk_forward_metrics": pd.DataFrame(fold_rows),
        "warranty_risk_error_analysis_60d": final_predictions,
        "warranty_risk_segment_metrics_60d": pd.DataFrame(segment_rows),
        "warranty_risk_model_selection_summary": selection_summary,
    }
    for table, data in outputs.items():
        client.load_table_from_dataframe(
            data, f"{PROJECT}.analytics_ml.{table}",
            job_config=bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
        ).result(timeout=120)
        print(f"WROTE analytics_ml.{table}: {len(data)} rows")
    print(pd.DataFrame(fold_rows)[[
        "fold_name", "training_rows", "test_rows", "roc_auc",
        "average_precision", "precision", "recall", "threshold"
    ]].round(4).to_string(index=False))
    print(selection_summary.to_string(index=False))


if __name__ == "__main__":
    main()
