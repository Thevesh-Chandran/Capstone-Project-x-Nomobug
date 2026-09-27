"""Bounded, property-purged temporal benchmark of corrected warranty outcomes.

The 2026 period has already been inspected. It is diagnostic reporting, never
used to select features, model families, hyperparameters, or alert thresholds.
Only sanitized fields are read; all generated outputs remain local and ignored.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, balanced_accuracy_score,
    brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from warranty_validation_splits import (
        assert_package_property_disjoint, connected_validation_groups,
    )
except ModuleNotFoundError:
    from scripts.warranty_validation_splits import (
        assert_package_property_disjoint, connected_validation_groups,
    )


PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
SOURCE = f"{PROJECT}.analytics_ml.warranty_fixed_horizon_dataset"
ROOT = Path(__file__).resolve().parents[1]
TARGET = "warranty_signal_within_30d"
MAX_BYTES = 100 * 1024 * 1024
KEYS = ["population", TARGET, "sales_record_id", "address_hash",
        "anchor_date", "outcome_end_date"]
BASE_NUMERIC = [
    "service_number", "package_sessions_recorded", "sale_total_rm",
    "days_since_previous_service", "days_sale_to_anchor",
    "prior_package_warranty_claims", "prior_package_service_events",
    "prior_property_warranty_claims", "prior_property_service_events",
    "days_since_prior_property_claim", "prior_property_claims_90d",
    "prior_area_claims_90d", "prior_area_services_90d", "anchor_month_sin",
    "anchor_month_cos", "location_uncertainty_radius_m",
]
CATEGORICAL = ["pest_category", "package_category",
               "calendar_pest_text_category", "calendar_service_method_category"]
PEST_ALIASES = {
    "ANT": r"\b(?:ants?|semut)\b",
    "COCKROACH": r"\b(?:cockroach(?:es)?|roach(?:es)?|lipas)\b",
    "RODENT": r"\b(?:rodents?|rats?|mouse|mice|tikus)\b",
    "BED_BUG": r"\b(?:bed ?bugs?|pepijat)\b",
    "TERMITE": r"\b(?:termites?|anai(?: anai)?)\b",
    "MOSQUITO": r"\b(?:mosquito(?:es|s)?|nyamuk)\b",
    "FLY": r"\b(?:flies|fly|lalat)\b",
    "GENERAL_CONTROL": r"\b(?:gpc|general pest control)\b",
}
PEST_CONTEXT_NUMERIC = ([f"pest_has_{category.lower()}" for category in PEST_ALIASES]
                        + ["pest_has_other_terms", "pest_distinct_known_types"])
PEST_NON_TYPE_WORDS = set("dan and with plus promo promotion preventive prevention "
                         "package pest control session sessions treatment service services "
                         "unknown tbc none na n a x".split())
DERIVED_CATEGORICAL = {"normalized_pest_category"}
WEATHER_NUMERIC = [
    "prior_1d_precipitation_mm", "prior_3d_precipitation_mm",
    "prior_7d_precipitation_mm", "prior_14d_precipitation_mm",
    "prior_30d_precipitation_mm", "prior_7d_wet_days_1mm", "prior_14d_wet_days_1mm",
    "prior_30d_wet_days_1mm", "prior_14d_heavy_rain_days_10mm",
    "prior_14d_max_daily_precipitation_mm", "days_since_last_rain_1mm_capped_30d",
    "prior_7d_temperature_mean_c", "prior_7d_temperature_max_c",
    "prior_30d_temperature_mean_c", "prior_7d_relative_humidity_mean_pct",
    "prior_30d_relative_humidity_mean_pct",
    "prior_7d_soil_moisture_0_to_7cm_mean",
    "prior_30d_soil_moisture_0_to_7cm_mean", "prior_3d_vs_previous_11d_daily_rain_trend_mm",
]
ENVIRONMENT_NUMERIC = [
    "elevation_m", "local_relief_500m_m", "nearest_mapped_water_m",
    "nearest_mapped_forest_m", "hotosm_nearest_waterway_m",
    "hotosm_water_features_500m", "hotosm_water_features_1km",
    "hotosm_water_features_2km", "hotosm_nearest_drainage_m",
    "hotosm_nearest_flowing_water_m", "hotosm_nearest_standing_water_m",
]
DERIVED_NUMERIC = ["log1p_waterway_distance", "water_rain_interaction",
                   "drainage_rain_interaction", "rain_soil_interaction"]
LANDCOVER_NUMERIC = [
    f"worldcover_{category}_fraction_{buffer}m"
    for buffer in (250, 1000)
    for category in ("builtup", "tree", "grass", "crop", "water", "wetland")
]
FLOOD_NUMERIC = [
    "gfm_prior_7d_max_flood_fraction_1km",
    "gfm_prior_14d_max_flood_fraction_1km",
    "gfm_prior_30d_max_flood_fraction_1km",
    "gfm_prior_30d_observed_days",
    "gfm_prior_30d_flood_detected_days",
    "gfm_days_since_detected_flood_capped_30d",
    "gfm_days_since_valid_observation",
    "gfm_prior_30d_max_valid_fraction_1km",
]
FLOOD_CONTEXT_ENABLED = False
REPORTED_FLOOD_NUMERIC = [
    "gdacs_prior_7d_reported_events", "gdacs_prior_14d_reported_events",
    "gdacs_prior_30d_reported_events", "gdacs_days_since_reported_event_capped_30d",
]
REPORTED_FLOOD_CONTEXT_ENABLED = False
COMPACT_NUMERIC = [
    "service_number", "package_sessions_recorded", "days_since_previous_service",
    "prior_package_warranty_claims", "prior_property_warranty_claims",
    "days_since_prior_property_claim", "prior_property_claims_90d",
    "anchor_month_sin", "anchor_month_cos",
]
FEATURE_SETS = {
    "compact_history": COMPACT_NUMERIC,
    "base": BASE_NUMERIC,
    "base_weather": BASE_NUMERIC + WEATHER_NUMERIC,
    "base_weather_environment": (BASE_NUMERIC + WEATHER_NUMERIC
                                 + ENVIRONMENT_NUMERIC + DERIVED_NUMERIC),
    "compact_history_landcover": COMPACT_NUMERIC + LANDCOVER_NUMERIC,
    "base_weather_environment_landcover": (BASE_NUMERIC + WEATHER_NUMERIC
                                           + ENVIRONMENT_NUMERIC + DERIVED_NUMERIC
                                           + LANDCOVER_NUMERIC),
}
DEVELOPMENT_FOLDS = [
    ("2025_q2", "2025-04-01", "2025-07-01"),
    ("2025_q3", "2025-07-01", "2025-10-01"),
    ("2025_q4", "2025-10-01", "2026-01-01"),
]
REPORTING_START = "2026-01-01"


def configure_premise_context(enabled: bool) -> None:
    """Add client type only for an explicitly requested separate experiment."""
    if enabled and "premise_type" not in CATEGORICAL:
        CATEGORICAL.append("premise_type")


def normalize_pest_context(value) -> tuple[str, dict]:
    """Normalize known aliases without guessing the meaning of unknown pest terms."""
    text = "" if pd.isna(value) else unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"[^\w]+", " ", text)
    text = " ".join(text.split())
    matched = []
    remainder = text
    for category, pattern in PEST_ALIASES.items():
        if re.search(pattern, text):
            matched.append(category)
            remainder = re.sub(pattern, " ", remainder)
    other = any(word not in PEST_NON_TYPE_WORDS and not word.isdigit()
                for word in remainder.split())
    category = "|".join(sorted(matched + (["OTHER"] if other else []))) or "UNSPECIFIED"
    indicators = {f"pest_has_{name.lower()}": float(name in matched) for name in PEST_ALIASES}
    indicators["pest_has_other_terms"] = float(other)
    indicators["pest_distinct_known_types"] = float(len(set(matched) - {"GENERAL_CONTROL"}))
    return category, indicators


def configure_pest_context(enabled: bool) -> None:
    if not enabled:
        return
    if "normalized_pest_category" not in CATEGORICAL:
        CATEGORICAL.append("normalized_pest_category")
    for feature_set, numeric in list(FEATURE_SETS.items()):
        # Some default contracts alias BASE_NUMERIC/COMPACT_NUMERIC. Copy them
        # so derived context never enters the warehouse source-column contract.
        FEATURE_SETS[feature_set] = numeric + [
            column for column in PEST_CONTEXT_NUMERIC if column not in numeric]


def configure_flood_context(enabled: bool) -> None:
    """Require observed satellite context only for an explicit ablation run."""
    global FLOOD_CONTEXT_ENABLED
    FLOOD_CONTEXT_ENABLED = enabled
    if enabled:
        for feature_set, numeric in list(FEATURE_SETS.items()):
            # Copy contracts: base/compact lists may otherwise alias constants.
            FEATURE_SETS[feature_set] = numeric + [
                column for column in FLOOD_NUMERIC if column not in numeric]


def configure_reported_flood_context(enabled: bool) -> None:
    global REPORTED_FLOOD_CONTEXT_ENABLED
    REPORTED_FLOOD_CONTEXT_ENABLED = enabled
    if enabled:
        for feature_set, numeric in list(FEATURE_SETS.items()):
            FEATURE_SETS[feature_set] = numeric + [
                column for column in REPORTED_FLOOD_NUMERIC if column not in numeric]


def optional_flood_source_numeric() -> list[str]:
    return ((FLOOD_NUMERIC if FLOOD_CONTEXT_ENABLED else [])
            + (REPORTED_FLOOD_NUMERIC if REPORTED_FLOOD_CONTEXT_ENABLED else []))


def feature_preparation_options() -> dict:
    options = {
        "premise_context": "premise_type" in CATEGORICAL,
        "normalize_pest_context": "normalized_pest_category" in CATEGORICAL,
    }
    # Preserve previously frozen two-option contracts for historical models.
    if FLOOD_CONTEXT_ENABLED:
        options["flood_context"] = True
    if REPORTED_FLOOD_CONTEXT_ENABLED:
        options["reported_flood_context"] = True
    return options


def flood_context_coverage(frame: pd.DataFrame) -> dict:
    return {
        "rows": len(frame),
        "rows_with_prior_30d_valid_observation": int(
            frame["gfm_prior_30d_observed_days"].gt(0).sum()),
        "rows_with_prior_30d_detected_flood": int(
            frame["gfm_prior_30d_flood_detected_days"].gt(0).sum()),
        "rows_with_prior_30d_flood_fraction": int(
            frame["gfm_prior_30d_max_flood_fraction_1km"].notna().sum()),
        "interpretation": "observed_nearby_flood_context_not_confirmed_property_flooding",
    }


def filter_populations(frame: pd.DataFrame, populations: list[str] | None) -> pd.DataFrame:
    if not populations:
        return frame
    missing = sorted(set(populations) - set(frame["population"].astype(str)))
    if missing:
        raise ValueError(f"Requested populations are absent from input: {missing}")
    return frame[frame["population"].isin(populations)].copy()


def validation_group_coverage(frame: pd.DataFrame) -> dict:
    properties = frame['address_hash'].astype('string').str.strip()
    property_rows = properties.notna() & properties.ne('')
    property_components = frame['validation_group'].str.startswith('property:')
    return {"rows_with_property_hash": int(property_rows.sum()),
            "rows_grouped_by_package_only": int((~property_components).sum()),
            "rows_without_hash_linked_through_package": int((~property_rows & property_components).sum()),
            "property_hash_row_coverage": float(property_rows.mean()),
            "distinct_property_groups": int(frame.loc[property_components, "validation_group"].nunique()),
            "distinct_package_fallback_groups": int(frame.loc[~property_components, "validation_group"].nunique()),
            "connected_components": int(frame['validation_group'].nunique()),
            "group_definition": "connected_package_property_bipartite_components",
            "limitation": "unobserved_properties_cannot_link_other_unidentified_packages"}


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate identifiers/dates and derive features without reading outcomes."""
    source_categorical = [column for column in CATEGORICAL if column not in DERIVED_CATEGORICAL]
    missing = sorted(set(KEYS + BASE_NUMERIC + source_categorical
                         + WEATHER_NUMERIC + ENVIRONMENT_NUMERIC
                         + LANDCOVER_NUMERIC
                         + optional_flood_source_numeric()) - set(frame))
    if missing:
        raise ValueError(f"Dataset is missing contracted columns: {missing}")
    frame = frame.copy()
    if frame[KEYS].drop(columns="address_hash").isna().any().any():
        raise ValueError("Null target, population, sale identifier, or outcome dates")
    if not frame[TARGET].isin([True, False, 0, 1]).all():
        raise ValueError("Target must contain resolved binary labels")
    frame[TARGET] = frame[TARGET].astype(bool)
    for column in ("anchor_date", "outcome_end_date"):
        frame[column] = pd.to_datetime(frame[column], errors="raise")
    # Warehouse row order is undefined. Stable order is essential for seeded
    # bootstrapping/tree fits and identical replay of the saved input manifest.
    frame = frame.sort_values(['population', 'sales_record_id', 'anchor_date'],
                              kind='stable').reset_index(drop=True)
    if (frame["outcome_end_date"] < frame["anchor_date"]).any():
        raise ValueError("Outcome window ends before its prediction anchor")
    if frame.duplicated(["population", "sales_record_id", "anchor_date"]).any():
        raise ValueError("Duplicate population/sale/anchor prediction rows")
    frame["validation_group"] = connected_validation_groups(frame)
    for column in (BASE_NUMERIC + WEATHER_NUMERIC + ENVIRONMENT_NUMERIC
                   + LANDCOVER_NUMERIC + optional_flood_source_numeric()):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
        frame[column] = frame[column].replace([np.inf, -np.inf], np.nan)
    if FLOOD_CONTEXT_ENABLED:
        for column in FLOOD_NUMERIC:
            if frame[column].dropna().lt(0).any():
                raise ValueError(f"Negative observed flood feature: {column}")
            if "fraction" in column and frame[column].dropna().gt(1).any():
                raise ValueError(f"Observed flood fraction outside [0,1]: {column}")
        observed = frame["gfm_prior_30d_observed_days"]
        detected = frame["gfm_prior_30d_flood_detected_days"]
        if ((detected > observed) | (observed > 30)).any():
            raise ValueError("Flood detected/observed day counts violate 30-day window")
    if REPORTED_FLOOD_CONTEXT_ENABLED:
        for column in REPORTED_FLOOD_NUMERIC:
            if frame[column].dropna().lt(0).any():
                raise ValueError(f"Negative reported regional flood feature: {column}")
        if (frame["gdacs_prior_7d_reported_events"] > frame["gdacs_prior_14d_reported_events"]).any() or (
                frame["gdacs_prior_14d_reported_events"] > frame["gdacs_prior_30d_reported_events"]).any():
            raise ValueError("Reported regional flood event counts violate nested windows")
        if frame["gdacs_days_since_reported_event_capped_30d"].gt(30).any():
            raise ValueError("Reported regional flood recency exceeds capped window")
    pest_context = frame["pest_category"].map(normalize_pest_context)
    frame["normalized_pest_category"] = pest_context.map(lambda value: value[0])
    for column in PEST_CONTEXT_NUMERIC:
        frame[column] = pest_context.map(lambda value: value[1][column])
    for column in CATEGORICAL:
        frame[column] = frame[column].astype("string").fillna("UNKNOWN").astype(str)
    rain = frame["prior_14d_precipitation_mm"]
    water = frame["hotosm_nearest_waterway_m"].clip(lower=0)
    drain = frame["hotosm_nearest_drainage_m"].clip(lower=0)
    frame["log1p_waterway_distance"] = np.log1p(water)
    frame["water_rain_interaction"] = rain / (1 + water / 1000)
    frame["drainage_rain_interaction"] = rain / (1 + drain / 1000)
    frame["rain_soil_interaction"] = (
        rain * frame["prior_7d_soil_moisture_0_to_7cm_mean"])
    return frame


def purged_split(frame: pd.DataFrame, test_start: str,
                 test_end: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Keep mature past labels and remove every test property from training."""
    start = pd.Timestamp(test_start)
    test_mask = frame["anchor_date"] >= start
    if test_end is not None:
        test_mask &= frame["anchor_date"] < pd.Timestamp(test_end)
    test = frame[test_mask].copy()
    immature = ((frame["anchor_date"] < start)
                & (frame["outcome_end_date"] >= start))
    train = frame[frame["outcome_end_date"] < start].copy()
    shared = train["validation_group"].isin(set(test["validation_group"]))
    audit = {"embargoed_training_rows": int(immature.sum()),
             "property_purged_training_rows": int(shared.sum())}
    train = train[~shared].copy()
    assert set(train["validation_group"]).isdisjoint(test["validation_group"])
    assert_package_property_disjoint(train, test)
    assert (train["outcome_end_date"] < start).all()
    return train, test, audit


def model_specs() -> list[str]:
    return ([f"lr_c{value}_{weight}" for value in (0.1, 1.0, 10.0)
             for weight in ("plain", "balanced")]
            + ["rf_depth3", "rf_depth6", "extra_trees_depth6",
               "hist_depth2", "hist_depth3", "catboost_depth3_plain",
               "catboost_depth4_plain", "catboost_depth3_balanced", "dummy_prior"])


def make_model(name: str, numeric: list[str]) -> Pipeline:
    if name.startswith("catboost_"):
        from catboost import CatBoostClassifier
        depth = int(name.split("_")[1][-1])
        classifier = CatBoostClassifier(
            depth=depth, iterations=250, learning_rate=0.04,
            l2_leaf_reg=8 if depth == 3 else 12,
            auto_class_weights="Balanced" if name.endswith("balanced") else None,
            cat_features=[f"categorical__{column}" for column in CATEGORICAL],
            random_seed=42, thread_count=2, verbose=False, allow_writing_files=False,
            loss_function="Logloss")
        preprocess = ColumnTransformer([
            ("numeric", SimpleImputer(strategy="median", add_indicator=True,
                                       keep_empty_features=True), numeric),
            ("categorical", SimpleImputer(strategy="constant", fill_value="UNKNOWN"),
             CATEGORICAL),
        ]).set_output(transform="pandas")
        return Pipeline([("preprocess", preprocess), ("classifier", classifier)])
    if name.startswith("lr_"):
        parts = name.split("_")
        classifier = LogisticRegression(
            C=float(parts[1][1:]), class_weight=("balanced" if parts[2]
                                               == "balanced" else None),
            max_iter=2000, random_state=42)
    elif name.startswith("rf_"):
        classifier = RandomForestClassifier(
            n_estimators=160, max_depth=int(name[-1]), min_samples_leaf=10,
            class_weight="balanced_subsample", random_state=42, n_jobs=-1)
    elif name == "extra_trees_depth6":
        classifier = ExtraTreesClassifier(
            n_estimators=160, max_depth=6, min_samples_leaf=10,
            class_weight="balanced", random_state=42, n_jobs=-1)
    elif name.startswith("hist_"):
        classifier = HistGradientBoostingClassifier(
            max_depth=int(name[-1]), min_samples_leaf=20, max_iter=140,
            learning_rate=0.05, l2_regularization=3.0, random_state=42)
    elif name == "dummy_prior":
        classifier = DummyClassifier(strategy="prior")
    else:
        raise ValueError(f"Unknown model family: {name}")
    preprocess = ColumnTransformer([
        ("numeric", Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True,
                                      keep_empty_features=True)),
            ("scale", StandardScaler()),
        ]), numeric),
        ("categorical", OneHotEncoder(handle_unknown="ignore", min_frequency=5,
                                      sparse_output=False), CATEGORICAL),
    ])
    return Pipeline([("preprocess", preprocess), ("classifier", classifier)])


def score(y, probability, threshold: float = 0.5) -> dict:
    y = np.asarray(y, dtype=bool)
    probability = np.asarray(probability, dtype=float)
    alert = probability >= threshold
    two_classes = np.unique(y).size == 2
    return {
        "rows": len(y), "positives": int(y.sum()), "prevalence": float(y.mean()),
        "roc_auc": float(roc_auc_score(y, probability)) if two_classes else None,
        "average_precision": float(average_precision_score(y, probability))
        if y.any() else None,
        "brier_score": float(brier_score_loss(y, probability)),
        "accuracy": float(accuracy_score(y, alert)),
        "balanced_accuracy": float(balanced_accuracy_score(y, alert))
        if two_classes else None,
        "precision": float(precision_score(y, alert, zero_division=0)),
        "recall": float(recall_score(y, alert, zero_division=0)),
        "f1": float(f1_score(y, alert, zero_division=0)),
        "alert_rows": int(alert.sum()), "threshold": float(threshold),
        "majority_class_accuracy": float(max(y.mean(), 1 - y.mean())),
        "ap_lift_over_prevalence": (float(average_precision_score(y, probability)
                                              / y.mean()) if y.any() else None),
    }


def select_threshold(y, probability) -> float:
    """Use development out-of-fold predictions only; report ties conservatively."""
    candidates = np.linspace(0.02, 0.98, 97)
    values = [f1_score(y, np.asarray(probability) >= threshold, zero_division=0)
              for threshold in candidates]
    best = max(values)
    return float(max(threshold for threshold, value in zip(candidates, values)
                     if value >= best - 1e-12))


def fit_calibrator(y, raw_probability) -> tuple[LogisticRegression | None, dict]:
    """Fit a monotonic Platt mapping using pre-reporting OOF scores only."""
    clipped = np.clip(np.asarray(raw_probability, dtype=float),
                      np.nextafter(0.0, 1.0), np.nextafter(1.0, 0.0))
    logits = (np.log(clipped) - np.log1p(-clipped)).reshape(-1, 1)
    fitted = LogisticRegression(C=1.0, max_iter=2000, random_state=42).fit(logits, y)
    slope = float(fitted.coef_[0, 0])
    metadata = {"method": "platt_on_pre2026_purged_walk_forward_oof",
                "fitted_rows": len(clipped), "slope": slope,
                "intercept": float(fitted.intercept_[0]),
                "development_calibrated_brier_is_in_sample_for_calibration": True,
                "ranking_invariant": True}
    if slope <= 0:
        metadata["method"] = "skipped_nonpositive_platt_slope"
        metadata["applied"] = False
        return None, metadata
    metadata["applied"] = True
    return fitted, metadata


def apply_calibrator(calibrator, raw_probability) -> np.ndarray:
    raw = np.asarray(raw_probability, dtype=float)
    if calibrator is None:
        return raw.copy()
    clipped = np.clip(raw, np.nextafter(0.0, 1.0), np.nextafter(1.0, 0.0))
    logits = (np.log(clipped) - np.log1p(-clipped)).reshape(-1, 1)
    return calibrator.predict_proba(logits)[:, 1]


def priority_review_metrics(y, probability, fraction: float = 0.2) -> dict:
    """Describe a predeclared review budget; keep equal scores together."""
    y = np.asarray(y, dtype=bool)
    probability = np.asarray(probability, dtype=float)
    if not len(y) or not 0 < fraction <= 1:
        raise ValueError("Priority review requires nonempty scores and fraction in (0,1]")
    target_rows = max(1, int(np.ceil(fraction * len(y))))
    cutoff = float(np.sort(probability)[-target_rows])
    selected = probability >= cutoff
    precision = float(y[selected].mean())
    recall = float(y[selected].sum() / y.sum()) if y.any() else 0.0
    return {"target_fraction": fraction, "target_rows": target_rows,
            "selected_rows_including_ties": int(selected.sum()),
            "realized_fraction": float(selected.mean()), "score_cutoff": cutoff,
            "cutoff_tied_rows": int((probability == cutoff).sum()),
            "precision": precision, "recall": recall,
            "precision_lift_over_prevalence": precision / float(y.mean())
            if y.any() else None,
            "selection": "within_batch_top_fraction_including_cutoff_ties"}


def clustered_bootstrap(frame: pd.DataFrame, repeats: int = 500) -> dict:
    groups = [group for _, group in frame.groupby("validation_group", sort=False)]
    rng = np.random.default_rng(42)
    results = []
    for _ in range(repeats):
        sample = pd.concat([groups[index] for index in
                            rng.integers(0, len(groups), len(groups))])
        if sample[TARGET].nunique() != 2:
            continue
        results.append(score(sample[TARGET], sample["probability"],
                             float(frame["threshold"].iloc[0])))
    intervals = {}
    for metric in ("roc_auc", "average_precision", "brier_score", "accuracy",
                   "balanced_accuracy", "precision", "recall", "f1"):
        values = [result[metric] for result in results]
        intervals[metric] = (np.quantile(values, [0.025, 0.975]).tolist()
                             if values else None)
    return {"valid_repeats": len(results), "groups": len(groups),
            "confidence_95pct": intervals}


def benchmark_population(frame: pd.DataFrame, output: Path,
                         bootstrap_repeats: int = 500,
                         model_names: list[str] | None = None) -> dict:
    population = str(frame["population"].iloc[0])
    fold_data = []
    skipped = []
    for fold_name, start, end in DEVELOPMENT_FOLDS:
        train, test, audit = purged_split(frame, start, end)
        if (len(train) < 30 or len(test) < 15 or train[TARGET].nunique() < 2
                or min(test[TARGET].sum(), (~test[TARGET]).sum()) < 3):
            skipped.append({"fold": fold_name, "training_rows": len(train),
                            "test_rows": len(test), **audit})
            continue
        fold_data.append((fold_name, train, test, audit))
    if len(fold_data) < 2:
        return {"population": population, "status": "insufficient_temporal_folds",
                "usable_folds": len(fold_data), "skipped_folds": skipped,
                "validation_group_coverage": validation_group_coverage(frame)}
    metrics, predictions = [], {}
    for feature_set, numeric in FEATURE_SETS.items():
        features = numeric + CATEGORICAL
        for model_name in (model_names or model_specs()):
            if model_name == "dummy_prior" and feature_set != "compact_history":
                continue
            key = (feature_set, model_name)
            predictions[key] = []
            for fold_name, train, test, audit in fold_data:
                fitted = make_model(model_name, numeric).fit(train[features], train[TARGET])
                probability = fitted.predict_proba(test[features])[:, 1]
                metrics.append({"feature_set": feature_set, "model": model_name,
                                "fold": fold_name, "training_rows": len(train),
                                **audit, **score(test[TARGET], probability)})
                predicted = test[KEYS + ["validation_group"]].copy()
                predicted["probability"] = probability
                predicted["fold"] = fold_name
                predictions[key].append(predicted)
            mean_ap = np.mean([row["average_precision"] for row in metrics
                               if (row["feature_set"], row["model"]) == key])
            print(f"{population} {feature_set} {model_name}: development AP {mean_ap:.4f}",
                  flush=True)
    folds = pd.DataFrame(metrics)
    summary = folds.groupby(["feature_set", "model"], as_index=False).agg(
        mean_average_precision=("average_precision", "mean"),
        sd_average_precision=("average_precision", "std"),
        mean_roc_auc=("roc_auc", "mean"), mean_brier=("brier_score", "mean"),
        mean_ap_lift_over_prevalence=("ap_lift_over_prevalence", "mean"),
        development_folds=("fold", "count"))
    summary = summary.sort_values(["mean_average_precision", "mean_roc_auc"],
                                  ascending=False, kind="stable")
    winner = summary.iloc[0]
    feature_set, model_name = str(winner["feature_set"]), str(winner["model"])
    oof = pd.concat(predictions[(feature_set, model_name)], ignore_index=True)
    oof["raw_probability"] = oof["probability"]
    calibrator, calibration_metadata = fit_calibrator(oof[TARGET], oof["raw_probability"])
    oof["probability"] = apply_calibrator(calibrator, oof["raw_probability"])
    threshold = select_threshold(oof[TARGET], oof["probability"])
    output.mkdir(parents=True, exist_ok=True)
    folds.to_csv(output / f"{population}_fold_metrics.csv", index=False)
    summary.to_csv(output / f"{population}_candidate_summary.csv", index=False)
    oof.to_csv(output / f"{population}_selected_development_predictions.csv", index=False)
    result = {
        "population": population, "status": "experimental_diagnostic_only",
        "rows": len(frame), "positive_rows": int(frame[TARGET].sum()),
        "selected_model": model_name, "selected_feature_set": feature_set,
        "selected_features": FEATURE_SETS[feature_set] + CATEGORICAL,
        "feature_preparation_options": feature_preparation_options(),
        "selected_is_prevalence_baseline": model_name == "dummy_prior",
        "selection": winner.to_dict(), "skipped_folds": skipped,
        "validation_group_coverage": validation_group_coverage(frame),
        "development_threshold": threshold,
        "calibration": calibration_metadata,
        "development_oof_raw": score(oof[TARGET], oof["raw_probability"]),
        "development_oof": score(oof[TARGET], oof["probability"], threshold),
        "development_priority_top20pct": priority_review_metrics(
            oof[TARGET], oof["probability"]),
        "candidate_count": len(summary),
        "weather_nonmissing_rows": int(frame["prior_14d_precipitation_mm"].notna().sum()),
        "mapped_water_context_nonmissing_rows": int(frame["hotosm_nearest_waterway_m"].notna().sum()),
        "landcover_250m_rows": int(frame[[column for column in LANDCOVER_NUMERIC
                                          if column.endswith("_250m")]].notna().all(axis=1).sum()),
        "landcover_1000m_rows": int(frame[[column for column in LANDCOVER_NUMERIC
                                           if column.endswith("_1000m")]].notna().all(axis=1).sum()),
    }
    if FLOOD_CONTEXT_ENABLED:
        result["flood_context_coverage"] = flood_context_coverage(frame)
    train, diagnostic, audit = purged_split(frame, REPORTING_START)
    result["diagnostic_split_audit"] = audit
    if FLOOD_CONTEXT_ENABLED:
        result["flood_context_coverage_by_period"] = {
            "purged_pre2026_training": flood_context_coverage(train),
            "diagnostic_2026": flood_context_coverage(diagnostic),
        }
    if train[TARGET].nunique() < 2 or diagnostic[TARGET].nunique() < 2:
        result["diagnostic_status"] = "insufficient_classes_after_property_purge"
        return result
    numeric = FEATURE_SETS[feature_set]
    features = numeric + CATEGORICAL
    fitted = make_model(model_name, numeric).fit(train[features], train[TARGET])
    raw_probability = fitted.predict_proba(diagnostic[features])[:, 1]
    probability = apply_calibrator(calibrator, raw_probability)
    scored = diagnostic[KEYS + ["validation_group"]].copy()
    scored["raw_probability"] = raw_probability
    scored["probability"] = probability
    scored["threshold"] = threshold
    result["diagnostic_2026_raw"] = score(scored[TARGET], raw_probability)
    result["diagnostic_2026"] = score(scored[TARGET], probability, threshold)
    result["diagnostic_2026_threshold_0_5"] = score(scored[TARGET], probability)
    result["diagnostic_priority_top20pct"] = priority_review_metrics(
        scored[TARGET], probability)
    diagnostic_scored = diagnostic.copy()
    diagnostic_scored["probability"] = probability
    segments = []
    for column in ("package_sessions_recorded", "pest_category"):
        for value, segment in diagnostic_scored.groupby(column, dropna=False):
            supported = (len(segment) >= 50 and int(segment[TARGET].sum()) >= 10
                         and int((~segment[TARGET]).sum()) >= 10)
            segments.append({"segment_column": column, "segment_value": str(value),
                             "metric_supported": supported,
                             **score(segment[TARGET], segment["probability"], threshold)})
    result["diagnostic_segments"] = segments
    baseline_probability = np.repeat(float(train[TARGET].mean()), len(diagnostic))
    result["diagnostic_prevalence_baseline"] = score(
        scored[TARGET], baseline_probability)
    result["diagnostic_clustered_bootstrap"] = clustered_bootstrap(
        scored, bootstrap_repeats)
    scored.to_csv(output / f"{population}_diagnostic_predictions.csv", index=False)
    joblib.dump({"pipeline": fitted, "features": features, "calibrator": calibrator,
                 "threshold": threshold, "population": population,
                 "feature_preparation_options": result["feature_preparation_options"],
                 "business_target": business_target_metadata([population]),
                 "feature_preparation": "benchmark_warranty_models.prepare_frame",
                 "training_outcome_end_exclusive": REPORTING_START,
                 "purpose": "frozen_diagnostic_model_not_deployment"},
                output / f"{population}_selected_model.joblib")
    return result


def read_frame(source: str) -> pd.DataFrame:
    if not re.fullmatch(r"[a-z0-9-]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+", source):
        raise ValueError("Expected project.dataset.table source")
    from google.cloud import bigquery
    source_categorical = [column for column in CATEGORICAL if column not in DERIVED_CATEGORICAL]
    columns = (KEYS + BASE_NUMERIC + source_categorical + WEATHER_NUMERIC
               + ENVIRONMENT_NUMERIC + LANDCOVER_NUMERIC
               + optional_flood_source_numeric())
    sql = f"select {', '.join(columns)} from `{source}`"
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False))
    if dry.total_bytes_processed > MAX_BYTES:
        raise ValueError("Benchmark input exceeds 100 MiB guard")
    return pd.DataFrame(dict(row) for row in client.query(
        sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES)
    ).result(timeout=300))


def business_target_metadata(populations: list[str]) -> dict:
    callback_only = bool(populations) and all("callback" in population for population in populations)
    return {
        "target": "recorded_corrective_callback_within_30d" if callback_only else TARGET,
        "target_column": TARGET,
        "claim_meaning": ("recorded_corrective_callback_visit_independent_of_contractual_"
                          "entitlement_not_biological_recurrence" if callback_only else
                          "recorded_calendar_warranty_not_biological_recurrence"),
        "grants_warranty_entitlement": False,
    }


def persist_dataset_input(frame: pd.DataFrame, output: Path) -> str:
    """Save canonical sanitized query inputs and fingerprint columns plus records."""
    columns = sorted(frame.columns)
    ordered = frame.sort_values(["population", "sales_record_id", "anchor_date"],
                                kind="stable")[columns]
    rows = json.loads(ordered.to_json(orient="records", date_format="iso"))
    canonical = json.dumps({"columns": columns, "records": rows},
                           sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    (output / "dataset_input.json").write_text(canonical, encoding="utf-8")
    return digest


def load_dataset_input(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "records" in payload and "columns" in payload:
        return pd.DataFrame(payload["records"], columns=payload["columns"])
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    raise ValueError("Input JSON must contain records or the saved dataset manifest")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--input-json", type=Path)
    parser.add_argument("--population", action="append",
                        help="Benchmark only this population; repeat to include several")
    parser.add_argument("--premise-context", action="store_true",
                        help="Include premise_type category for a separate callback experiment")
    parser.add_argument("--normalize-pest-context", action="store_true",
                        help="Add deterministic known pest aliases and multi-pest indicators")
    parser.add_argument("--flood-context", action="store_true",
                        help="Include strictly prior observed satellite flood context")
    parser.add_argument("--reported-flood-context", action="store_true",
                        help="Include conservative prior reported regional GDACS context")
    parser.add_argument("--feature-set", action="append", choices=list(FEATURE_SETS),
                        help="Restrict feature contracts for a bounded challenger")
    parser.add_argument("--model", action="append", choices=model_specs(),
                        help="Restrict model candidates for a bounded challenger")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs" / "cp2-v2" / "model_benchmark")
    parser.add_argument("--bootstrap-repeats", type=int, default=500)
    args = parser.parse_args()
    configure_premise_context(args.premise_context)
    configure_pest_context(args.normalize_pest_context)
    configure_flood_context(args.flood_context)
    configure_reported_flood_context(args.reported_flood_context)
    if args.feature_set:
        for feature_set in list(FEATURE_SETS):
            if feature_set not in args.feature_set:
                del FEATURE_SETS[feature_set]
    selected_models = list(dict.fromkeys(args.model)) if args.model else None
    if selected_models is not None and "dummy_prior" not in selected_models:
        selected_models.append("dummy_prior")
    frame = (load_dataset_input(args.input_json) if args.input_json
             else read_frame(args.source))
    frame = filter_populations(frame, args.population)
    if frame.empty:
        raise SystemExit("No mature corrected warranty examples")
    input_digest = persist_dataset_input(frame, args.output_dir)
    frame = load_dataset_input(args.output_dir / 'dataset_input.json')
    frame = prepare_frame(frame)
    if frame.empty:
        raise SystemExit("No mature corrected warranty examples")
    results = [benchmark_population(group.copy(), args.output_dir,
                                     args.bootstrap_repeats, selected_models)
               for _, group in frame.groupby("population", sort=True)]
    report = {
        "run_utc": datetime.now(timezone.utc).isoformat(), "source": args.source,
        "dataset_input_sha256": input_digest,
        "dataset_input_file": "dataset_input.json",
        "requested_populations": args.population,
        "premise_context_enabled": args.premise_context,
        "pest_normalization_enabled": args.normalize_pest_context,
        "feature_preparation_options": feature_preparation_options(),
        "pest_alias_contract": PEST_ALIASES if args.normalize_pest_context else None,
        "requested_models": args.model,
        "requested_feature_sets": args.feature_set,
        "categorical_feature_contract": list(CATEGORICAL),
        **business_target_metadata([result["population"] for result in results]),
        "horizon_days": 30,
        "selection_period_end_exclusive": REPORTING_START,
        "validation": "purged_walk_forward_with_disjoint_package_property_components",
        "probability_calibration": "positive_slope_platt_fitted_only_to_pre2026_oof",
        "priority_review_budget": "top20pct_with_ties_reported",
        "landcover_reference": "ESA_WorldCover_2021_historical_map_before_model_anchors",
        "reporting_caveat": "2026 already inspected; not an untouched final test",
        "target_comparison_caveat": "Compare AP lift/support as populations have different prevalence",
        "populations": results,
    }
    if args.flood_context:
        report["flood_context_enabled"] = True
        report["flood_feature_contract"] = list(FLOOD_NUMERIC)
    if args.reported_flood_context:
        report["reported_flood_context_enabled"] = True
        report["reported_flood_feature_contract"] = list(REPORTED_FLOOD_NUMERIC)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "benchmark_results.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
