"""Compare leakage-safe horizons and baselines for 3-session warranty risk.

The selected v2 outcome is a recorded Calendar warranty signal within 60 days
after a unique 3/3 event. It is not proof of treatment completion or biological
pest recurrence. Final v2 selection is performed by tune_warranty_risk_model.py.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.compose import ColumnTransformer
from sklearn.calibration import CalibratedClassifierCV
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.frozen import FrozenEstimator


PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
MAX_BYTES = 100 * 1024 * 1024
SOURCE = f"{PROJECT}.analytics_ml.warranty_risk_3session_dataset"

OPERATIONAL_NUMERIC_FEATURES = [
    "sale_total_rm",
    "days_sale_to_completion",
    "days_first_to_completion",
    "days_session_1_to_2",
    "days_session_2_to_3",
    "anchor_month",
    "anchor_day_of_week",
    "anchor_hour_local",
    "prior_package_service_events",
    "prior_package_warranty_signals",
    "prior_property_service_events",
    "prior_property_warranty_signals",
    "prior_property_distinct_packages",
    "days_since_prior_property_event",
    "days_since_prior_property_warranty_signal",
    "session_interval_difference_days",
    "distinct_teams_first_three_sessions",
    "booking_lead_hours",
    "last_pre_service_edit_lead_hours",
    "prior_team_service_events",
    "prior_team_warranty_signals",
    "prior_team_warranty_rate",
    "prior_team_warranty_rate_smoothed",
    "prior_area_service_events",
    "prior_area_warranty_signals",
    "prior_area_warranty_rate",
    "prior_area_warranty_rate_smoothed",
    "team_events_on_anchor_day",
    "team_events_prior_7d",
    "team_events_before_anchor_same_day",
    "team_scheduled_minutes_prior_7d",
    "prior_property_service_events_90d",
    "prior_property_warranty_signals_90d",
    "prior_property_service_events_per_90_active_days",
    "recent_90d_share_of_prior_property_services",
    "workload_team_change_interaction",
    "prior_pest_premise_service_events",
    "prior_pest_premise_warranty_signals",
    "prior_pest_premise_warranty_rate",
    "prior_pest_premise_warranty_rate_smoothed",
    "prior_pest_premise_service_events_90d",
    "prior_pest_premise_warranty_signals_90d",
    "prior_pest_premise_warranty_rate_90d",
    "prior_pest_premise_warranty_rate_90d_smoothed",
    "scheduled_duration_minutes",
    "days_first_contact_to_close",
    "prior_payment_count",
    "prior_payment_amount_rm",
    "prior_payment_to_sale_ratio",
    "days_since_last_payment",
]
OPERATIONAL_BOOLEAN_FEATURES = [
    "sale_total_missing",
    "recorded_returning_client",
    "anchor_is_weekend",
    "edited_within_24h_before_service",
    "recurring_calendar_event",
    "team_changed_session_1_to_2",
    "team_changed_session_2_to_3",
]
OPERATIONAL_CATEGORICAL_FEATURES = [
    "acquisition_category",
    "pest_category",
    "package_category",
    "contract_category",
    "premise_type",
    "trbs_status",
    "billing_arrangement",
    "pest_premise_category",
    "pest_team_category",
    "sales_pic",
    "appointment_daypart",
    "assigned_team_calendar",
    "calendar_pest_text_category",
    "calendar_service_method_category",
    "property_history_pest_category",
]
WEATHER_FEATURES = [
    "event_day_temperature_mean_c",
    "event_day_precipitation_mm",
    "event_day_relative_humidity_mean_pct",
    "event_day_soil_moisture_0_to_7cm_mean",
    "prior_3d_precipitation_mm",
    "prior_7d_precipitation_mm",
    "prior_14d_precipitation_mm",
    "prior_7d_relative_humidity_mean_pct",
    "prior_7d_soil_moisture_0_to_7cm_mean",
]
EVENT_DAY_WEATHER_FEATURES = [
    "event_day_temperature_mean_c", "event_day_precipitation_mm",
    "event_day_relative_humidity_mean_pct",
    "event_day_soil_moisture_0_to_7cm_mean",
]
PREDICTION_SAFE_WEATHER_FEATURES = [
    feature for feature in WEATHER_FEATURES
    if feature not in EVENT_DAY_WEATHER_FEATURES
]
WEATHER_INTERACTION_NUMERIC_FEATURES = [
    "rain_humidity_7d_interaction", "rain_soil_moisture_interaction",
]
WEATHER_INTERACTION_CATEGORICAL_FEATURES = [
    "pest_rain_band_category", "method_humidity_band_category",
]
ENVIRONMENTAL_NUMERIC_FEATURES = [
    "elevation_m", "local_relief_500m_m", "nearest_mapped_water_m",
    "mapped_water_features_2km", "nearest_mapped_forest_m",
    "mapped_forest_features_2km",
]
ENVIRONMENTAL_BOOLEAN_FEATURES = [
    "mapped_water_within_2km", "mapped_forest_within_2km",
    "environmental_places_result_capped", "environmental_context_available",
]
OPERATIONAL_FEATURES = (
    OPERATIONAL_NUMERIC_FEATURES
    + OPERATIONAL_BOOLEAN_FEATURES
    + OPERATIONAL_CATEGORICAL_FEATURES
)
NON_TEAM_OPERATIONAL_CATEGORICAL_FEATURES = [
    feature for feature in OPERATIONAL_CATEGORICAL_FEATURES
    if feature != "assigned_team_calendar"
]
NON_TEAM_OPERATIONAL_FEATURES = (
    OPERATIONAL_NUMERIC_FEATURES
    + OPERATIONAL_BOOLEAN_FEATURES
    + NON_TEAM_OPERATIONAL_CATEGORICAL_FEATURES
)
ALL_FEATURES = (OPERATIONAL_FEATURES + WEATHER_FEATURES
                + WEATHER_INTERACTION_NUMERIC_FEATURES
                + WEATHER_INTERACTION_CATEGORICAL_FEATURES
                + ENVIRONMENTAL_NUMERIC_FEATURES + ENVIRONMENTAL_BOOLEAN_FEATURES)
PAYMENT_FEATURES = [
    "prior_payment_count", "prior_payment_amount_rm",
    "prior_payment_to_sale_ratio", "days_since_last_payment",
]
SALES_CONTEXT_NUMERIC_FEATURES = ["days_first_contact_to_close"]
SALES_CONTEXT_CATEGORICAL_FEATURES = ["sales_pic"]
TEAM_AREA_CONTEXT_NUMERIC_FEATURES = [
    "prior_team_service_events", "prior_team_warranty_signals",
    "prior_team_warranty_rate", "prior_area_service_events",
    "prior_area_warranty_signals", "prior_area_warranty_rate",
    "team_events_on_anchor_day", "scheduled_duration_minutes",
]
TEAM_AREA_CONTEXT_CATEGORICAL_FEATURES = ["pest_team_category"]
FINAL_CONTEXT_NUMERIC_FEATURES = [
    "prior_property_distinct_packages", "days_since_prior_property_event",
    "days_since_prior_property_warranty_signal",
    "session_interval_difference_days", "distinct_teams_first_three_sessions",
    "booking_lead_hours", "last_pre_service_edit_lead_hours",
]
FINAL_CONTEXT_BOOLEAN_FEATURES = [
    "anchor_is_weekend", "edited_within_24h_before_service",
    "recurring_calendar_event", "team_changed_session_1_to_2",
    "team_changed_session_2_to_3",
]
FINAL_CONTEXT_CATEGORICAL_FEATURES = ["appointment_daypart"]
LAST_INTERNAL_NUMERIC_FEATURES = [
    "team_events_prior_7d", "team_events_before_anchor_same_day",
    "team_scheduled_minutes_prior_7d", "prior_property_service_events_90d",
    "prior_property_warranty_signals_90d",
    "prior_property_service_events_per_90_active_days",
    "recent_90d_share_of_prior_property_services",
    "workload_team_change_interaction",
    "prior_pest_premise_service_events",
    "prior_pest_premise_warranty_signals",
    "prior_pest_premise_warranty_rate",
    "prior_pest_premise_service_events_90d",
    "prior_pest_premise_warranty_signals_90d",
    "prior_pest_premise_warranty_rate_90d",
]
LAST_INTERNAL_CATEGORICAL_FEATURES = [
    "calendar_pest_text_category", "calendar_service_method_category",
    "property_history_pest_category",
]
NEW_INTERNAL_NUMERIC_FEATURES = (
    PAYMENT_FEATURES + SALES_CONTEXT_NUMERIC_FEATURES
    + TEAM_AREA_CONTEXT_NUMERIC_FEATURES + FINAL_CONTEXT_NUMERIC_FEATURES
    + LAST_INTERNAL_NUMERIC_FEATURES
)
NEW_INTERNAL_CATEGORICAL_FEATURES = (
    SALES_CONTEXT_CATEGORICAL_FEATURES + TEAM_AREA_CONTEXT_CATEGORICAL_FEATURES
    + FINAL_CONTEXT_CATEGORICAL_FEATURES + LAST_INTERNAL_CATEGORICAL_FEATURES
)
PRIOR_EXPANDED_NUMERIC_FEATURES = [
    feature for feature in OPERATIONAL_NUMERIC_FEATURES
    if feature not in NEW_INTERNAL_NUMERIC_FEATURES
]
PRIOR_EXPANDED_CATEGORICAL_FEATURES = [
    feature for feature in OPERATIONAL_CATEGORICAL_FEATURES
    if feature not in NEW_INTERNAL_CATEGORICAL_FEATURES
]
PRIOR_EXPANDED_BOOLEAN_FEATURES = [
    feature for feature in OPERATIONAL_BOOLEAN_FEATURES
    if feature not in FINAL_CONTEXT_BOOLEAN_FEATURES
]
PRIOR_EXPANDED_FEATURES = (
    PRIOR_EXPANDED_NUMERIC_FEATURES + PRIOR_EXPANDED_BOOLEAN_FEATURES
    + PRIOR_EXPANDED_CATEGORICAL_FEATURES + WEATHER_FEATURES
)
WEAK_BUSINESS_NUMERIC_FEATURES = [
    "sale_total_rm", "days_first_contact_to_close", "prior_payment_count",
    "prior_payment_amount_rm", "prior_payment_to_sale_ratio", "days_since_last_payment",
]
WEAK_BUSINESS_CATEGORICAL_FEATURES = [
    "acquisition_category", "billing_arrangement", "sales_pic",
]
SMOOTHED_RATE_FEATURES = [
    "prior_team_warranty_rate_smoothed", "prior_area_warranty_rate_smoothed",
    "prior_pest_premise_warranty_rate_smoothed",
    "prior_pest_premise_warranty_rate_90d_smoothed",
]
UNSMOOTHED_RATE_FEATURES = [
    "prior_team_warranty_rate", "prior_area_warranty_rate",
    "prior_pest_premise_warranty_rate",
    "prior_pest_premise_warranty_rate_90d",
]
RISK_CORE_NUMERIC_FEATURES = [
    feature for feature in OPERATIONAL_NUMERIC_FEATURES
    if feature not in WEAK_BUSINESS_NUMERIC_FEATURES + UNSMOOTHED_RATE_FEATURES
] + PREDICTION_SAFE_WEATHER_FEATURES + WEATHER_INTERACTION_NUMERIC_FEATURES
RISK_CORE_BOOLEAN_FEATURES = list(OPERATIONAL_BOOLEAN_FEATURES)
RISK_CORE_CATEGORICAL_FEATURES = [
    feature for feature in OPERATIONAL_CATEGORICAL_FEATURES
    if feature not in WEAK_BUSINESS_CATEGORICAL_FEATURES
] + WEATHER_INTERACTION_CATEGORICAL_FEATURES
RISK_CORE_FEATURES = (
    RISK_CORE_NUMERIC_FEATURES + RISK_CORE_BOOLEAN_FEATURES
    + RISK_CORE_CATEGORICAL_FEATURES
)
RISK_CORE_WITH_ENV_FEATURES = (
    RISK_CORE_FEATURES + ENVIRONMENTAL_NUMERIC_FEATURES
    + ENVIRONMENTAL_BOOLEAN_FEATURES
)
RISK_CORE_NO_TEAM_NUMERIC_FEATURES = [
    feature for feature in RISK_CORE_NUMERIC_FEATURES
    if not feature.startswith("prior_team_")
    and not feature.startswith("team_")
    and feature != "workload_team_change_interaction"
]
RISK_CORE_NO_TEAM_BOOLEAN_FEATURES = [
    feature for feature in RISK_CORE_BOOLEAN_FEATURES
    if not feature.startswith("team_changed_")
]
RISK_CORE_NO_TEAM_CATEGORICAL_FEATURES = [
    feature for feature in RISK_CORE_CATEGORICAL_FEATURES
    if feature not in ("assigned_team_calendar", "pest_team_category")
]
RISK_CORE_NO_TEAM_FEATURES = (
    RISK_CORE_NO_TEAM_NUMERIC_FEATURES + RISK_CORE_NO_TEAM_BOOLEAN_FEATURES
    + RISK_CORE_NO_TEAM_CATEGORICAL_FEATURES
)
WEATHER_AUDIT_COLUMNS = [
    "event_day_weather_available", "local_weather_available", "complete_prior_14d_weather"
]

SQL = f"""
select sales_record_id, prediction_anchor_date, evaluation_split,
       warranty_signal_within_14d, warranty_signal_within_30d,
       warranty_signal_within_60d, warranty_signal_within_90d, target_definition,
       prediction_time_definition, label_evidence,
       {', '.join(ALL_FEATURES + WEATHER_AUDIT_COLUMNS)}
from `{SOURCE}`
"""


def metric_rows(name: str, y: pd.Series, probability: np.ndarray,
                threshold: float = 0.5) -> list[dict]:
    prediction = probability >= threshold
    values = {
        "roc_auc": roc_auc_score(y, probability),
        "average_precision": average_precision_score(y, probability),
        "log_loss": log_loss(y, probability, labels=[False, True]),
        "brier_score": brier_score_loss(y, probability),
        "accuracy_at_0_5": accuracy_score(y, prediction),
        "balanced_accuracy_at_0_5": balanced_accuracy_score(y, prediction),
        "precision_at_0_5": precision_score(y, prediction, zero_division=0),
        "recall_at_0_5": recall_score(y, prediction, zero_division=0),
        "f1_at_0_5": f1_score(y, prediction, zero_division=0),
    }
    return [
        {"model_name": name, "metric_name": metric, "metric_value": float(value)}
        for metric, value in values.items()
    ]


def best_f1_threshold(y: pd.Series, probability: np.ndarray) -> tuple[float, float]:
    """Select an alert threshold on a pre-holdout tuning slice only."""
    candidates = np.linspace(0.05, 0.95, 181)
    scores = np.array([
        f1_score(y, probability >= threshold, zero_division=0)
        for threshold in candidates
    ])
    best = int(np.argmax(scores))
    return float(candidates[best]), float(scores[best])


def logistic_pipeline(numeric_features: list[str], boolean_features: list[str],
                      categorical_features: list[str]) -> Pipeline:
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scaler", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(
            handle_unknown="infrequent_if_exist", min_frequency=10)),
    ])
    transformers = [("numeric", numeric, numeric_features + boolean_features)]
    if categorical_features:
        transformers.append(("categorical", categorical, categorical_features))
    return Pipeline([
        ("preprocess", ColumnTransformer(transformers)),
        ("classifier", LogisticRegression(max_iter=2000)),
    ])


def tree_pipeline(classifier, numeric_features: list[str],
                  boolean_features: list[str],
                  categorical_features: list[str]) -> Pipeline:
    """Dense, imputed feature matrix for small nonlinear benchmarks."""
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(
            handle_unknown="infrequent_if_exist", min_frequency=10,
            sparse_output=False)),
    ])
    return Pipeline([
        ("preprocess", ColumnTransformer([
            ("numeric", numeric, numeric_features + boolean_features),
            ("categorical", categorical, categorical_features),
        ])),
        ("classifier", classifier),
    ])


def random_forest_pipeline(numeric_features: list[str],
                           categorical_features: list[str],
                           boolean_features: list[str] | None = None) -> Pipeline:
    return tree_pipeline(
        RandomForestClassifier(
            n_estimators=500, max_depth=8, min_samples_leaf=10,
            class_weight="balanced_subsample", random_state=42, n_jobs=-1),
        numeric_features,
        OPERATIONAL_BOOLEAN_FEATURES if boolean_features is None else boolean_features,
        categorical_features)


def main() -> None:
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    dry = client.query(SQL, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False))
    print(f"Estimated input bytes: {dry.total_bytes_processed:,}")
    if dry.total_bytes_processed > MAX_BYTES:
        raise SystemExit("Training input query exceeds 100 MiB cap")
    records = [dict(row) for row in client.query(
        SQL,
        job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES, job_timeout_ms=600000),
        job_retry=None,
    ).result(timeout=630)]
    frame = pd.DataFrame(records)
    if frame.empty:
        raise SystemExit("No mature experiment rows")

    target_columns = [
        "warranty_signal_within_14d", "warranty_signal_within_30d",
        "warranty_signal_within_60d", "warranty_signal_within_90d",
    ]
    for column in (OPERATIONAL_BOOLEAN_FEATURES + ENVIRONMENTAL_BOOLEAN_FEATURES
                   + WEATHER_AUDIT_COLUMNS + target_columns):
        frame[column] = frame[column].astype("boolean")
    # Fair comparison: every candidate model is evaluated on the same rows
    # with a complete prior-14-day weather window.
    cohort = frame[frame["complete_prior_14d_weather"].fillna(False)].copy()
    train = cohort[cohort["evaluation_split"] == "train_2024_2025"].copy()
    holdout = cohort[cohort["evaluation_split"] == "holdout_2026"].copy()
    if train.empty or holdout.empty or train["warranty_signal_within_30d"].nunique() != 2 \
            or holdout["warranty_signal_within_30d"].nunique() != 2:
        raise SystemExit("Both time cohorts must contain positive and negative outcomes")
    if len(train) < 100 or int(train["warranty_signal_within_30d"].sum()) < 20:
        raise SystemExit(
            "Weather-complete training cohort is too small to publish "
            f"({len(train)} rows / {int(train['warranty_signal_within_30d'].sum())} positives)"
        )

    y_train = train["warranty_signal_within_30d"].astype(bool)
    y_holdout = holdout["warranty_signal_within_30d"].astype(bool)
    baseline = DummyClassifier(strategy="prior").fit(train[["anchor_month"]], y_train)
    models = {
        "operational_without_team_logistic": (
            logistic_pipeline(OPERATIONAL_NUMERIC_FEATURES, OPERATIONAL_BOOLEAN_FEATURES,
                              NON_TEAM_OPERATIONAL_CATEGORICAL_FEATURES),
            NON_TEAM_OPERATIONAL_FEATURES,
        ),
        "operational_logistic_regression": (
            logistic_pipeline(OPERATIONAL_NUMERIC_FEATURES, OPERATIONAL_BOOLEAN_FEATURES,
                              OPERATIONAL_CATEGORICAL_FEATURES),
            OPERATIONAL_FEATURES,
        ),
        "weather_logistic_regression": (
            logistic_pipeline(WEATHER_FEATURES + ["anchor_month"], [], []),
            WEATHER_FEATURES + ["anchor_month"],
        ),
        "combined_logistic_regression": (
            logistic_pipeline(OPERATIONAL_NUMERIC_FEATURES + WEATHER_FEATURES,
                              OPERATIONAL_BOOLEAN_FEATURES,
                              OPERATIONAL_CATEGORICAL_FEATURES),
            OPERATIONAL_FEATURES + WEATHER_FEATURES,
        ),
        "combined_random_forest": (
            random_forest_pipeline(
                OPERATIONAL_NUMERIC_FEATURES + WEATHER_FEATURES,
                OPERATIONAL_CATEGORICAL_FEATURES),
            OPERATIONAL_FEATURES + WEATHER_FEATURES,
        ),
        "environment_increment_random_forest": (
            random_forest_pipeline(
                OPERATIONAL_NUMERIC_FEATURES + WEATHER_FEATURES
                + ENVIRONMENTAL_NUMERIC_FEATURES,
                OPERATIONAL_CATEGORICAL_FEATURES,
                OPERATIONAL_BOOLEAN_FEATURES + ENVIRONMENTAL_BOOLEAN_FEATURES),
            OPERATIONAL_FEATURES + WEATHER_FEATURES
            + ENVIRONMENTAL_NUMERIC_FEATURES + ENVIRONMENTAL_BOOLEAN_FEATURES,
        ),
        "risk_core_random_forest": (
            random_forest_pipeline(
                RISK_CORE_NUMERIC_FEATURES, RISK_CORE_CATEGORICAL_FEATURES,
                RISK_CORE_BOOLEAN_FEATURES),
            RISK_CORE_FEATURES,
        ),
        "risk_core_without_team_random_forest": (
            random_forest_pipeline(
                RISK_CORE_NO_TEAM_NUMERIC_FEATURES,
                RISK_CORE_NO_TEAM_CATEGORICAL_FEATURES,
                RISK_CORE_NO_TEAM_BOOLEAN_FEATURES),
            RISK_CORE_NO_TEAM_FEATURES,
        ),
        "risk_core_plus_environment_random_forest": (
            random_forest_pipeline(
                RISK_CORE_NUMERIC_FEATURES + ENVIRONMENTAL_NUMERIC_FEATURES,
                RISK_CORE_CATEGORICAL_FEATURES,
                RISK_CORE_BOOLEAN_FEATURES + ENVIRONMENTAL_BOOLEAN_FEATURES),
            RISK_CORE_WITH_ENV_FEATURES,
        ),
        "prior_expanded_random_forest": (
            random_forest_pipeline(
                PRIOR_EXPANDED_NUMERIC_FEATURES + WEATHER_FEATURES,
                PRIOR_EXPANDED_CATEGORICAL_FEATURES,
                PRIOR_EXPANDED_BOOLEAN_FEATURES),
            PRIOR_EXPANDED_FEATURES,
        ),
        "expanded_plus_payments_random_forest": (
            random_forest_pipeline(
                PRIOR_EXPANDED_NUMERIC_FEATURES + WEATHER_FEATURES + PAYMENT_FEATURES,
                PRIOR_EXPANDED_CATEGORICAL_FEATURES,
                PRIOR_EXPANDED_BOOLEAN_FEATURES),
            PRIOR_EXPANDED_FEATURES + PAYMENT_FEATURES,
        ),
        "expanded_plus_sales_context_random_forest": (
            random_forest_pipeline(
                PRIOR_EXPANDED_NUMERIC_FEATURES + WEATHER_FEATURES
                + SALES_CONTEXT_NUMERIC_FEATURES,
                PRIOR_EXPANDED_CATEGORICAL_FEATURES
                + SALES_CONTEXT_CATEGORICAL_FEATURES,
                PRIOR_EXPANDED_BOOLEAN_FEATURES),
            PRIOR_EXPANDED_FEATURES + SALES_CONTEXT_NUMERIC_FEATURES
            + SALES_CONTEXT_CATEGORICAL_FEATURES,
        ),
        "expanded_plus_team_area_random_forest": (
            random_forest_pipeline(
                PRIOR_EXPANDED_NUMERIC_FEATURES + WEATHER_FEATURES
                + TEAM_AREA_CONTEXT_NUMERIC_FEATURES,
                PRIOR_EXPANDED_CATEGORICAL_FEATURES
                + TEAM_AREA_CONTEXT_CATEGORICAL_FEATURES,
                PRIOR_EXPANDED_BOOLEAN_FEATURES),
            PRIOR_EXPANDED_FEATURES + TEAM_AREA_CONTEXT_NUMERIC_FEATURES
            + TEAM_AREA_CONTEXT_CATEGORICAL_FEATURES,
        ),
        "expanded_plus_final_context_random_forest": (
            random_forest_pipeline(
                PRIOR_EXPANDED_NUMERIC_FEATURES + WEATHER_FEATURES
                + FINAL_CONTEXT_NUMERIC_FEATURES,
                PRIOR_EXPANDED_CATEGORICAL_FEATURES
                + FINAL_CONTEXT_CATEGORICAL_FEATURES,
                PRIOR_EXPANDED_BOOLEAN_FEATURES + FINAL_CONTEXT_BOOLEAN_FEATURES),
            PRIOR_EXPANDED_FEATURES + FINAL_CONTEXT_NUMERIC_FEATURES
            + FINAL_CONTEXT_BOOLEAN_FEATURES + FINAL_CONTEXT_CATEGORICAL_FEATURES,
        ),
        "expanded_plus_last_internal_random_forest": (
            random_forest_pipeline(
                PRIOR_EXPANDED_NUMERIC_FEATURES + WEATHER_FEATURES
                + FINAL_CONTEXT_NUMERIC_FEATURES + LAST_INTERNAL_NUMERIC_FEATURES,
                PRIOR_EXPANDED_CATEGORICAL_FEATURES
                + FINAL_CONTEXT_CATEGORICAL_FEATURES
                + LAST_INTERNAL_CATEGORICAL_FEATURES,
                PRIOR_EXPANDED_BOOLEAN_FEATURES + FINAL_CONTEXT_BOOLEAN_FEATURES),
            PRIOR_EXPANDED_FEATURES + FINAL_CONTEXT_NUMERIC_FEATURES
            + FINAL_CONTEXT_BOOLEAN_FEATURES + FINAL_CONTEXT_CATEGORICAL_FEATURES
            + LAST_INTERNAL_NUMERIC_FEATURES + LAST_INTERNAL_CATEGORICAL_FEATURES,
        ),
        "combined_hist_gradient_boosting": (
            tree_pipeline(
                HistGradientBoostingClassifier(
                    learning_rate=0.05, max_iter=250, max_leaf_nodes=15,
                    min_samples_leaf=20, l2_regularization=1.0,
                    random_state=42),
                OPERATIONAL_NUMERIC_FEATURES + WEATHER_FEATURES,
                OPERATIONAL_BOOLEAN_FEATURES,
                OPERATIONAL_CATEGORICAL_FEATURES),
            ALL_FEATURES,
        ),
    }
    fitted_models = {}
    probabilities = {
        "training_prevalence_baseline": baseline.predict_proba(
            holdout[["anchor_month"]])[:, 1]
    }
    for name, (model, features) in models.items():
        fitted_models[name] = model.fit(train[features], y_train)
        probabilities[name] = fitted_models[name].predict_proba(holdout[features])[:, 1]

    # Feature selection evidence is generated entirely inside the pre-2026
    # training period. The 2026 holdout is reserved for final reporting.
    selection_cut = int(len(train) * 0.80)
    selection_development = train.sort_values(
        ["prediction_anchor_date", "sales_record_id"]).iloc[:selection_cut]
    selection_validation = train.sort_values(
        ["prediction_anchor_date", "sales_record_id"]).iloc[selection_cut:]
    selection_rows = []
    for name in (
            "combined_random_forest", "environment_increment_random_forest",
            "risk_core_random_forest", "risk_core_without_team_random_forest",
            "risk_core_plus_environment_random_forest"):
        model, features = models[name]
        selected_model = clone(model).fit(
            selection_development[features],
            selection_development["warranty_signal_within_30d"].astype(bool))
        selection_probability = selected_model.predict_proba(
            selection_validation[features])[:, 1]
        selection_y = selection_validation["warranty_signal_within_30d"].astype(bool)
        selection_rows.extend([
            {"model_name": name, "metric_name": "roc_auc",
             "metric_value": float(roc_auc_score(selection_y, selection_probability))},
            {"model_name": name, "metric_name": "average_precision",
             "metric_value": float(average_precision_score(
                 selection_y, selection_probability))},
            {"model_name": name, "metric_name": "brier_score",
             "metric_value": float(brier_score_loss(
                 selection_y, selection_probability))},
        ])
    run_ts = datetime.now(timezone.utc)
    feature_selection_metrics = pd.DataFrame(selection_rows)
    feature_selection_metrics["run_utc"] = run_ts
    feature_selection_metrics["development_rows"] = len(selection_development)
    feature_selection_metrics["validation_rows"] = len(selection_validation)
    feature_selection_metrics["split_definition"] = (
        "chronological_first_80pct_of_pre_2026_train_development;"
        "final_20pct_of_pre_2026_train_validation")
    common = {
        "run_utc": run_ts,
        "training_rows": len(train),
        "holdout_rows": len(holdout),
        "training_positive_rows": int(y_train.sum()),
        "holdout_positive_rows": int(y_holdout.sum()),
        "target_definition": frame["target_definition"].iloc[0],
        "prediction_time_definition": frame["prediction_time_definition"].iloc[0],
        "label_evidence": frame["label_evidence"].iloc[0],
        "split_definition": "anchors_before_2026_train_2024_2025; mature_2026_anchors_holdout",
        "feature_set_definition": "complete-prior-14d-weather cohort; local 0.1-degree grid where available, otherwise service-region daily mean; baseline, logistic, random-forest, and histogram-gradient-boosting benchmarks",
        "evaluation_cohort": "unique_3_of_3_anchors_with_complete_prior_14d_weather",
        "experiment_status": "evaluated_weather_inclusive_not_causal_or_production_ready",
    }
    metrics = pd.DataFrame(sum(
        (metric_rows(name, y_holdout, probability)
         for name, probability in probabilities.items()), []))
    for key, value in common.items():
        metrics[key] = value

    predictions = holdout[["sales_record_id", "prediction_anchor_date"]].copy()
    predictions["actual_warranty_signal_within_30d"] = y_holdout.to_numpy()
    for name, probability in probabilities.items():
        predictions[f"{name}_probability"] = probability
    predictions["run_utc"] = run_ts
    predictions["experiment_status"] = "heldout_experiment_not_production_decision"

    coefficient_frames = []
    for name, model in fitted_models.items():
        if not hasattr(model.named_steps["classifier"], "coef_"):
            continue
        coefficient_frames.append(pd.DataFrame({
            "model_name": name,
            "feature_name": model.named_steps["preprocess"].get_feature_names_out(),
            "coefficient": model.named_steps["classifier"].coef_[0],
        }))
    coefficients = pd.concat(coefficient_frames, ignore_index=True)
    coefficients["absolute_coefficient"] = coefficients["coefficient"].abs()
    coefficients["run_utc"] = run_ts
    coefficients["interpretation"] = (
        "standardized_or_one_hot_log_odds_association_not_causal_effect"
    )

    horizon_metric_frames = []
    horizon_prediction_frames = []
    threshold_rows = []
    for horizon_days in (14, 30, 60, 90):
        target = f"warranty_signal_within_{horizon_days}d"
        horizon_cohort = cohort[cohort[target].notna()].copy()
        horizon_train = horizon_cohort[
            horizon_cohort["evaluation_split"] == "train_2024_2025"
        ].sort_values(["prediction_anchor_date", "sales_record_id"])
        horizon_holdout = horizon_cohort[
            horizon_cohort["evaluation_split"] == "holdout_2026"
        ].sort_values(["prediction_anchor_date", "sales_record_id"])
        first_cut = int(len(horizon_train) * 0.70)
        second_cut = int(len(horizon_train) * 0.85)
        development = horizon_train.iloc[:first_cut]
        calibration = horizon_train.iloc[first_cut:second_cut]
        tuning = horizon_train.iloc[second_cut:]
        if any(part.empty or part[target].nunique() != 2 for part in (
                development, calibration, tuning, horizon_holdout)):
            print(f"SKIP {horizon_days}d calibrated experiment: insufficient classes")
            continue

        base_model = random_forest_pipeline(
            RISK_CORE_NO_TEAM_NUMERIC_FEATURES,
            RISK_CORE_NO_TEAM_CATEGORICAL_FEATURES,
            RISK_CORE_NO_TEAM_BOOLEAN_FEATURES,
        )
        base_model.fit(
            development[RISK_CORE_NO_TEAM_FEATURES], development[target].astype(bool))
        calibration_y = calibration[target].astype(bool)
        calibration_base_probability = base_model.predict_proba(
            calibration[RISK_CORE_NO_TEAM_FEATURES])[:, 1]
        calibration_auc = roc_auc_score(
            calibration_y, calibration_base_probability)
        if calibration_auc > 0.5:
            calibrated_model = CalibratedClassifierCV(
                FrozenEstimator(base_model), method="sigmoid")
            calibrated_model.fit(
                calibration[RISK_CORE_NO_TEAM_FEATURES], calibration_y)
            calibration_method = "sigmoid_on_chronological_15pct_training_slice"
        else:
            # A negative sigmoid slope reverses the risk ordering. Retain the
            # uncalibrated model when the small calibration slice is unstable.
            calibrated_model = base_model
            calibration_method = (
                "calibration_skipped_base_auc_not_above_0_5")
        tuning_probability = calibrated_model.predict_proba(
            tuning[RISK_CORE_NO_TEAM_FEATURES])[:, 1]
        threshold, tuning_f1 = best_f1_threshold(
            tuning[target].astype(bool), tuning_probability)
        holdout_probability = calibrated_model.predict_proba(
            horizon_holdout[RISK_CORE_NO_TEAM_FEATURES])[:, 1]
        uncalibrated_probability = base_model.predict_proba(
            horizon_holdout[RISK_CORE_NO_TEAM_FEATURES])[:, 1]
        y_horizon = horizon_holdout[target].astype(bool)

        calibrated_rows = pd.DataFrame(metric_rows(
            f"calibrated_interaction_rf_{horizon_days}d",
            y_horizon, holdout_probability, threshold))
        calibrated_rows["metric_name"] = calibrated_rows["metric_name"].str.replace(
            "_at_0_5", "_at_optimized_threshold", regex=False)
        uncalibrated_rows = pd.DataFrame(metric_rows(
            f"uncalibrated_interaction_rf_{horizon_days}d",
            y_horizon, uncalibrated_probability))
        horizon_rows = pd.concat(
            [calibrated_rows, uncalibrated_rows], ignore_index=True)
        horizon_rows["horizon_days"] = horizon_days
        horizon_rows["optimized_threshold"] = threshold
        horizon_rows["run_utc"] = run_ts
        horizon_rows["training_rows"] = len(horizon_train)
        horizon_rows["holdout_rows"] = len(horizon_holdout)
        horizon_rows["holdout_positive_rows"] = int(y_horizon.sum())
        horizon_rows["calibration_method"] = calibration_method
        horizon_rows["threshold_method"] = "max_f1_on_separate_final_15pct_training_slice"
        horizon_metric_frames.append(horizon_rows)

        horizon_predictions = horizon_holdout[[
            "sales_record_id", "prediction_anchor_date"]].copy()
        horizon_predictions["horizon_days"] = horizon_days
        horizon_predictions["actual_signal"] = y_horizon.to_numpy()
        horizon_predictions["calibrated_probability"] = holdout_probability
        horizon_predictions["uncalibrated_probability"] = uncalibrated_probability
        horizon_predictions["optimized_threshold"] = threshold
        horizon_predictions["alert_at_optimized_threshold"] = (
            holdout_probability >= threshold)
        horizon_predictions["run_utc"] = run_ts
        horizon_prediction_frames.append(horizon_predictions)
        threshold_rows.append({
            "run_utc": run_ts,
            "horizon_days": horizon_days,
            "optimized_threshold": threshold,
            "tuning_f1": tuning_f1,
            "calibration_base_auc": calibration_auc,
            "calibration_method": calibration_method,
            "development_rows": len(development),
            "calibration_rows": len(calibration),
            "threshold_tuning_rows": len(tuning),
            "holdout_rows": len(horizon_holdout),
        })

    horizon_metrics = pd.concat(horizon_metric_frames, ignore_index=True)
    horizon_predictions = pd.concat(horizon_prediction_frames, ignore_index=True)
    horizon_thresholds = pd.DataFrame(threshold_rows)

    destinations = {
        "warranty_risk_3session_run_metrics": metrics,
        "warranty_risk_3session_holdout_predictions": predictions,
        "warranty_risk_3session_coefficients": coefficients,
        "warranty_risk_horizon_metrics": horizon_metrics,
        "warranty_risk_horizon_predictions": horizon_predictions,
        "warranty_risk_horizon_thresholds": horizon_thresholds,
        "warranty_risk_feature_selection_metrics": feature_selection_metrics,
    }
    for table, data in destinations.items():
        job = client.load_table_from_dataframe(
            data,
            f"{PROJECT}.analytics_ml.{table}",
            job_config=bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE),
        )
        job.result(timeout=120)
        print(f"WROTE analytics_ml.{table}: {len(data)} rows")

    display = metrics.pivot(
        index="metric_name", columns="model_name", values="metric_value")
    print(f"Train: {len(train)} rows / {int(y_train.sum())} positives")
    print(f"Holdout: {len(holdout)} rows / {int(y_holdout.sum())} positives")
    print("Complete prior-14-day weather coverage before fair-cohort filtering:")
    for split_name, split_frame in (("train", frame[frame["evaluation_split"] == "train_2024_2025"]),
                                    ("holdout", frame[frame["evaluation_split"] == "holdout_2026"])):
        print(f"  {split_name}: event-day {int(split_frame['event_day_weather_available'].sum())}/"
              f"{len(split_frame)}, complete prior-14d "
              f"{int(split_frame['complete_prior_14d_weather'].sum())}/{len(split_frame)}")
    print(display.round(4).to_string())
    print("Highest absolute coefficients by model (associations, not causes):")
    print(coefficients.sort_values(["model_name", "absolute_coefficient"],
          ascending=[True, False]).groupby("model_name").head(8)[[
              "model_name", "feature_name", "coefficient"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
