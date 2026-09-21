"""Benchmark repeated warranty-coverage intervals and spatial sensitivity.

This is feasibility evidence only. The label is a recorded Calendar warranty
signal during a mature service interval, not confirmed pest recurrence.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
SOURCE = f"{PROJECT}.analytics_ml.warranty_coverage_service_episodes"
MAX_BYTES = 100 * 1024 * 1024
TARGET = "any_warranty_claim_in_interval"

BASE_NUMERIC = [
    "service_number", "package_sessions_recorded", "sale_total_rm",
    "location_uncertainty_radius_m",
]
WEATHER_NUMERIC = [
    "prior_3d_precipitation_mm", "prior_7d_precipitation_mm",
    "prior_14d_precipitation_mm", "prior_7d_relative_humidity_mean_pct",
    "prior_7d_soil_moisture_0_to_7cm_mean",
]
WATERWAY_NUMERIC = [
    "hotosm_nearest_waterway_m", "hotosm_water_features_500m",
    "hotosm_water_features_1km", "hotosm_water_features_2km",
    "hotosm_nearest_drainage_m", "hotosm_nearest_flowing_water_m",
    "hotosm_nearest_standing_water_m", "hotosm_drainage_features_2km",
    "hotosm_flowing_water_features_2km", "hotosm_standing_water_features_2km",
]
CATEGORICAL = [
    "pest_category", "package_category", "calendar_pest_text_category",
    "calendar_service_method_category",
]


def model(numeric: list[str]) -> Pipeline:
    return Pipeline([
        ("preprocess", ColumnTransformer([
            ("numeric", Pipeline([
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("scale", StandardScaler()),
            ]), numeric),
            ("categorical", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encode", OneHotEncoder(handle_unknown="ignore", min_frequency=5)),
            ]), CATEGORICAL),
        ])),
        ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])


def metrics(y: pd.Series, probability: np.ndarray) -> dict:
    return {
        "roc_auc": float(roc_auc_score(y, probability)),
        "average_precision": float(average_precision_score(y, probability)),
        "brier_score": float(brier_score_loss(y, probability)),
    }


def main() -> None:
    columns = [
        "sales_record_id", "service_anchor_event_row", "service_date",
        "evaluation_split", "area_cell", TARGET,
        "warranty_claim_count_in_interval", "exposure_days",
        "complete_prior_14d_weather", *BASE_NUMERIC, *WEATHER_NUMERIC,
        *WATERWAY_NUMERIC, *CATEGORICAL,
    ]
    sql = f"select {', '.join(dict.fromkeys(columns))} from `{SOURCE}`"
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False))
    if dry.total_bytes_processed > MAX_BYTES:
        raise SystemExit("Episode evaluation exceeds 100 MiB input cap")
    frame = pd.DataFrame(dict(row) for row in client.query(
        sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES)
    ).result(timeout=300))
    frame[TARGET] = frame[TARGET].astype(bool)
    train = frame[frame["evaluation_split"] == "train_2024_2025"].copy()
    test = frame[frame["evaluation_split"] == "holdout_2026"].copy()

    run_utc = datetime.now(timezone.utc)
    result_rows = []
    for name, numeric in (
        ("base_without_weather", BASE_NUMERIC),
        ("base_plus_prior_weather", BASE_NUMERIC + WEATHER_NUMERIC),
        ("base_plus_hotosm_waterways", BASE_NUMERIC + WATERWAY_NUMERIC),
        ("base_plus_weather_and_hotosm", BASE_NUMERIC + WEATHER_NUMERIC
         + WATERWAY_NUMERIC),
    ):
        fitted = model(numeric).fit(train[numeric + CATEGORICAL], train[TARGET])
        probability = fitted.predict_proba(test[numeric + CATEGORICAL])[:, 1]
        result_rows.append({
            "run_utc": run_utc, "model": name,
            "training_rows": len(train), "training_positive_rows": int(train[TARGET].sum()),
            "reporting_rows": len(test), "reporting_positive_rows": int(test[TARGET].sum()),
            "reporting_prevalence": float(test[TARGET].mean()),
            **metrics(test[TARGET], probability),
        })

    scale_rows = []
    for prefix, scale_note in (
        (3, "broad_geohash_about_150km"),
        (4, "area_geohash_about_20_to_40km"),
        (5, "local_geohash_about_5km_weather_still_9_to_11km"),
    ):
        scoped = frame[frame["area_cell"].notna()].copy()
        scoped["area_group"] = scoped["area_cell"].str.slice(0, prefix)
        for (split, area), group in scoped.groupby(["evaluation_split", "area_group"]):
            rain = group["prior_14d_precipitation_mm"]
            correlation = np.nan
            if len(group) >= 10 and group[TARGET].nunique() == 2 and rain.nunique() > 1:
                correlation = float(pd.concat([rain, group[TARGET].astype(int)], axis=1)
                                    .corr().iloc[0, 1])
            scale_rows.append({
                "run_utc": run_utc, "geohash_prefix_length": prefix,
                "scale_note": scale_note, "evaluation_split": split,
                "area_group": area, "interval_rows": len(group),
                "package_rows": int(group["sales_record_id"].nunique()),
                "positive_intervals": int(group[TARGET].sum()),
                "claim_events": int(group["warranty_claim_count_in_interval"].sum()),
                "interval_positive_rate": float(group[TARGET].mean()),
                "mean_prior_14d_rain_mm": float(rain.mean()) if rain.notna().any() else np.nan,
                "rain_target_correlation": correlation,
                "metric_supported": bool(len(group) >= 30 and group[TARGET].sum() >= 5
                                         and (~group[TARGET]).sum() >= 5),
            })

    outputs = {
        "warranty_coverage_episode_evaluation": pd.DataFrame(result_rows),
        "warranty_coverage_spatial_scale_sensitivity": pd.DataFrame(scale_rows),
    }
    for table, data in outputs.items():
        client.load_table_from_dataframe(
            data, f"{PROJECT}.analytics_ml.{table}",
            job_config=bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE),
        ).result(timeout=120)
        print(f"WROTE analytics_ml.{table}: {len(data)} rows")
    print(pd.DataFrame(result_rows).round(4).to_string(index=False))
    supported = pd.DataFrame(scale_rows)
    print("Supported area-period groups:", int(supported["metric_supported"].sum()),
          "of", len(supported))


if __name__ == "__main__":
    main()
