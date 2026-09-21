"""Evaluate static environmental context as a grouped model challenger.

This script is read-only. It compares the selected v3 logistic model feature
contract with the same model plus elevation, relief, mapped-water and
mapped-forest context. Model
selection evidence comes from pre-2026 walk-forward folds. The 2026 comparison
is diagnostic because that period has already been inspected during development.
"""

from datetime import datetime, timezone

import pandas as pd
from google.cloud import bigquery
from train_warranty_risk_baseline import (
    ENVIRONMENTAL_BOOLEAN_FEATURES,
    ENVIRONMENTAL_NUMERIC_FEATURES,
    LOCATION,
    MAX_BYTES,
    PROJECT,
    RISK_CORE_NO_TEAM_BOOLEAN_FEATURES,
    RISK_CORE_NO_TEAM_CATEGORICAL_FEATURES,
    RISK_CORE_NO_TEAM_FEATURES,
    RISK_CORE_NO_TEAM_NUMERIC_FEATURES,
    logistic_pipeline,
)
from tune_warranty_risk_model import (
    DEVELOPMENT_FOLDS,
    REPORTING_END,
    REPORTING_START,
    TARGET,
    probability_metrics,
)


SOURCE = f"{PROJECT}.analytics_ml.warranty_risk_3session_dataset"
BASE_FEATURES = list(RISK_CORE_NO_TEAM_FEATURES)
ENVIRONMENTAL_FEATURES = (
    list(ENVIRONMENTAL_NUMERIC_FEATURES) + list(ENVIRONMENTAL_BOOLEAN_FEATURES)
)
CHALLENGER_FEATURES = BASE_FEATURES + ENVIRONMENTAL_FEATURES

SQL = f"""
select prediction_anchor_date, {TARGET}, complete_prior_14d_weather,
       {', '.join(CHALLENGER_FEATURES)}
from `{SOURCE}`
where {TARGET} is not null
"""


def build_model(include_environment: bool):
    numeric = list(RISK_CORE_NO_TEAM_NUMERIC_FEATURES)
    boolean = list(RISK_CORE_NO_TEAM_BOOLEAN_FEATURES)
    if include_environment:
        numeric += ENVIRONMENTAL_NUMERIC_FEATURES
        boolean += ENVIRONMENTAL_BOOLEAN_FEATURES
    return logistic_pipeline(
        numeric, boolean, list(RISK_CORE_NO_TEAM_CATEGORICAL_FEATURES))


def evaluate_fold(frame: pd.DataFrame, test_start, test_end,
                  include_environment: bool) -> dict:
    features = CHALLENGER_FEATURES if include_environment else BASE_FEATURES
    train = frame[frame["prediction_anchor_date"] < test_start]
    test = frame[(frame["prediction_anchor_date"] >= test_start)
                 & (frame["prediction_anchor_date"] < test_end)]
    model = build_model(include_environment).fit(
        train[features], train[TARGET].astype(bool))
    probability = model.predict_proba(test[features])[:, 1]
    return {
        "training_rows": len(train),
        "test_rows": len(test),
        "positive_rows": int(test[TARGET].sum()),
        **probability_metrics(test[TARGET].astype(bool), probability),
    }


def main() -> None:
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    dry = client.query(SQL, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False))
    if dry.total_bytes_processed > MAX_BYTES:
        raise SystemExit("Environmental comparison exceeds 100 MiB input cap")
    frame = pd.DataFrame(dict(row) for row in client.query(
        SQL,
        job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES),
    ).result(timeout=630))
    frame["prediction_anchor_date"] = pd.to_datetime(
        frame["prediction_anchor_date"]).dt.date
    for column in (RISK_CORE_NO_TEAM_BOOLEAN_FEATURES
                   + ENVIRONMENTAL_BOOLEAN_FEATURES
                   + ["complete_prior_14d_weather", TARGET]):
        frame[column] = frame[column].astype("boolean")
    frame = frame[frame["complete_prior_14d_weather"].fillna(False)].copy()

    coverage = {
        "eligible_rows": len(frame),
        "elevation_rows": int(frame["elevation_m"].notna().sum()),
        "relief_rows": int(frame["local_relief_500m_m"].notna().sum()),
        "water_distance_rows": int(frame["nearest_mapped_water_m"].notna().sum()),
        "forest_distance_rows": int(frame["nearest_mapped_forest_m"].notna().sum()),
    }
    print("Coverage:", coverage)

    rows = []
    for model_name, include_environment in (
            ("v3_base", False), ("v3_plus_static_environment", True)):
        for fold_name, test_start, test_end in DEVELOPMENT_FOLDS:
            rows.append({
                "model": model_name,
                "fold": fold_name,
                **evaluate_fold(frame, test_start, test_end, include_environment),
            })
    metrics = pd.DataFrame(rows)
    print("\nPre-2026 walk-forward folds:")
    print(metrics.round(4).to_string(index=False))
    print("\nPre-2026 means:")
    print(metrics.groupby("model")[[
        "roc_auc", "average_precision", "brier_score"
    ]].mean().round(4).to_string())

    training = frame[frame["prediction_anchor_date"] < REPORTING_START]
    reporting = frame[(frame["prediction_anchor_date"] >= REPORTING_START)
                      & (frame["prediction_anchor_date"] < REPORTING_END)]
    diagnostic_rows = []
    for model_name, include_environment in (
            ("v3_base", False), ("v3_plus_static_environment", True)):
        features = CHALLENGER_FEATURES if include_environment else BASE_FEATURES
        model = build_model(include_environment).fit(
            training[features], training[TARGET].astype(bool))
        probability = model.predict_proba(reporting[features])[:, 1]
        diagnostic_rows.append({
            "model": model_name,
            "reporting_rows": len(reporting),
            "positive_rows": int(reporting[TARGET].sum()),
            **probability_metrics(reporting[TARGET].astype(bool), probability),
        })
    print("\n2026 diagnostic only (not a pristine holdout):")
    print(pd.DataFrame(diagnostic_rows).round(4).to_string(index=False))
    print("\nRun UTC:", datetime.now(timezone.utc).isoformat())


if __name__ == "__main__":
    main()
