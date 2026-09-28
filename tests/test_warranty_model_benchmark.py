import json
import joblib
import numpy as np
import pandas as pd
import subprocess
import sys
from scripts import benchmark_warranty_models as benchmark

from scripts.benchmark_warranty_models import (
    BASE_NUMERIC, CATEGORICAL, ENVIRONMENT_NUMERIC, KEYS, LANDCOVER_NUMERIC,
    TARGET, WEATHER_NUMERIC,
    apply_calibrator, fit_calibrator, make_model, prepare_frame,
    load_dataset_input, persist_dataset_input, priority_review_metrics,
    purged_split, score, select_threshold,
)


def test_temporal_split_embargoes_unmatured_labels_and_purges_test_properties():
    frame = pd.DataFrame({
        "anchor_date": pd.to_datetime(["2024-01-01", "2025-03-15", "2024-02-01",
                                        "2025-04-05"]),
        "outcome_end_date": pd.to_datetime(["2024-01-31", "2025-04-14", "2024-03-01",
                                             "2025-05-05"]),
        "validation_group": ["old", "immature", "test-property", "test-property"],
    })
    train, test, audit = purged_split(frame, "2025-04-01", "2025-07-01")
    assert train.index.tolist() == [0]
    assert test.index.tolist() == [3]
    assert audit == {"embargoed_training_rows": 1,
                     "property_purged_training_rows": 1}


def test_prepare_frame_keeps_missing_environment_distinct_and_groups_unknown_properties():
    columns = set(KEYS + BASE_NUMERIC + CATEGORICAL + WEATHER_NUMERIC
                  + ENVIRONMENT_NUMERIC + LANDCOVER_NUMERIC)
    frame = pd.DataFrame({column: [np.nan, np.nan] for column in columns})
    frame["population"] = "residential_3x_final_30d"
    frame[TARGET] = [False, True]
    frame["sales_record_id"] = ["one", "two"]
    frame["anchor_date"] = ["2025-01-01", "2025-01-02"]
    frame["outcome_end_date"] = ["2025-01-31", "2025-02-01"]
    frame["hotosm_nearest_waterway_m"] = [0, np.nan]
    frame["prior_14d_precipitation_mm"] = [10, 10]
    result = prepare_frame(frame)
    pd.testing.assert_frame_equal(result, prepare_frame(frame.iloc[::-1]))
    assert result["validation_group"].tolist() == ["package:one", "package:two"]
    assert result["water_rain_interaction"].iloc[0] == 10
    assert pd.isna(result["water_rain_interaction"].iloc[1])


def test_benchmark_preparation_and_split_keep_package_property_components_disjoint():
    columns = set(KEYS + BASE_NUMERIC + CATEGORICAL + WEATHER_NUMERIC
                  + ENVIRONMENT_NUMERIC + LANDCOVER_NUMERIC)
    frame = pd.DataFrame({column: [np.nan] * 4 for column in columns})
    frame['population'] = 'matched_packages_recorded_callback_30d'
    frame[TARGET] = [False, True, False, True]
    frame['sales_record_id'] = ['a', 'b', 'safe', 'a']
    frame['address_hash'] = ['north', 'north', 'safe', 'south']
    frame['anchor_date'] = ['2025-01-01'] * 3 + ['2025-04-02']
    frame['outcome_end_date'] = ['2025-01-31'] * 3 + ['2025-05-02']
    prepared = prepare_frame(frame)
    train, test, audit = purged_split(prepared, '2025-04-01', '2025-07-01')
    assert train['sales_record_id'].tolist() == ['safe']
    assert test['sales_record_id'].tolist() == ['a']
    assert audit['property_purged_training_rows'] == 2
    assert benchmark.validation_group_coverage(prepared)['connected_components'] == 2


def test_benchmark_bootstrap_samples_connected_components():
    from scripts.warranty_validation_splits import connected_validation_groups
    frame = pd.DataFrame({
        'sales_record_id': ['a', 'a', 'b', 'safe'],
        'address_hash': ['north', 'south', 'south', 'safe'],
        TARGET: [False, True, False, True],
        'probability': [0.1, 0.8, 0.2, 0.9], 'threshold': [0.5] * 4,
    })
    frame['validation_group'] = connected_validation_groups(frame)
    result = benchmark.clustered_bootstrap(frame, repeats=10)
    assert result['groups'] == 2
    assert result['valid_repeats'] > 0


def test_majority_accuracy_and_ap_baseline_expose_imbalanced_dummy_performance():
    result = score([False] * 8 + [True] * 2, [0.2] * 10)
    assert result["accuracy"] == 0.8
    assert result["majority_class_accuracy"] == 0.8
    assert result["balanced_accuracy"] == 0.5
    assert result["recall"] == 0
    assert result["average_precision"] == 0.2
    assert result["ap_lift_over_prevalence"] == 1


def test_threshold_comes_from_supplied_development_predictions():
    threshold = select_threshold([False, False, True, True], [0.1, 0.2, 0.6, 0.9])
    assert 0.2 < threshold <= 0.6
    assert score([False, False, True, True], [0.1, 0.2, 0.6, 0.9], threshold)["f1"] == 1


def test_model_handles_missing_numeric_features_and_unseen_pest_categories():
    model = make_model("lr_c1.0_plain", ["history"])
    train = pd.DataFrame({"history": [0.0, np.nan, 2.0, 4.0],
                          **{column: ["A", "A", "B", "B"] for column in CATEGORICAL}})
    model.fit(train, [False, False, True, True])
    test = train.iloc[[0]].copy()
    test["pest_category"] = "UNSEEN"
    probability = model.predict_proba(test)[0, 1]
    assert 0 <= probability <= 1


def test_positive_platt_calibration_preserves_ranking_and_reports_fit_scope():
    raw = np.array([0.1, 0.2, 0.3, 0.4, 0.7, 0.8, 0.9])
    y = [False, False, False, True, False, True, True]
    calibrator, metadata = fit_calibrator(y, raw)
    calibrated = apply_calibrator(calibrator, raw)
    assert metadata["applied"] is True
    assert metadata["slope"] > 0
    assert np.all(np.diff(calibrated) > 0)
    assert score(y, raw)["roc_auc"] == score(y, calibrated)["roc_auc"]
    assert score(y, raw)["average_precision"] == score(y, calibrated)["average_precision"]
    assert metadata["development_calibrated_brier_is_in_sample_for_calibration"] is True


def test_inverse_platt_calibration_is_not_promoted():
    raw = np.array([0.1, 0.2, 0.8, 0.9])
    calibrator, metadata = fit_calibrator([True, True, False, False], raw)
    assert calibrator is None
    assert metadata["applied"] is False
    assert np.array_equal(apply_calibrator(calibrator, raw), raw)


def test_platt_logit_transform_does_not_collapse_small_distinct_scores():
    raw = np.array([1e-14, 1e-10, 0.1, 0.5, 0.9, 1 - 1e-10])
    calibrator, _ = fit_calibrator([False, False, False, True, True, True], raw)
    calibrated = apply_calibrator(calibrator, raw)
    assert np.all(np.diff(calibrated) > 0)


def test_priority_review_reports_workload_precision_recall_and_cutoff_ties():
    result = priority_review_metrics([False, True, False, False, True],
                                     [0.1, 0.8, 0.4, 0.2, 0.8])
    assert result["target_rows"] == 1
    assert result["selected_rows_including_ties"] == 2
    assert result["realized_fraction"] == 0.4
    assert result["precision"] == 1
    assert result["recall"] == 1
    assert result["precision_lift_over_prevalence"] == 2.5


def test_native_catboost_imputes_within_training_and_artifact_reloads(tmp_path):
    model = make_model("catboost_depth3_plain", ["history"])
    train = pd.DataFrame({"history": [0.0, np.nan, 2.0, 4.0] * 5,
                          **{column: ["A", "A", "B", "B"] * 5
                             for column in CATEGORICAL}})
    model.fit(train, [False, False, True, True] * 5)
    test = train.iloc[[0]].copy()
    test["pest_category"] = "UNSEEN"
    probability = model.predict_proba(test)[0, 1]
    assert 0 <= probability <= 1
    transformed = model.named_steps["preprocess"].transform(test)
    assert transformed["categorical__pest_category"].iloc[0] == "UNSEEN"
    assert "numeric__missingindicator_history" in transformed
    artifact = tmp_path / "native_catboost.joblib"
    joblib.dump(model, artifact)
    loaded = joblib.load(artifact)
    assert np.array_equal(model.predict_proba(test), loaded.predict_proba(test))
    test_input = tmp_path / "fixture_input.joblib"
    joblib.dump(test, test_input)
    fresh = subprocess.run([
        sys.executable, "-c",
        "import joblib,sys; model=joblib.load(sys.argv[1]); "
        "frame=joblib.load(sys.argv[2]); print(model.predict_proba(frame)[0,1])",
        str(artifact), str(test_input),
    ], capture_output=True, text=True, check=True)
    assert float(fresh.stdout.strip()) == probability


def test_dataset_fingerprint_is_stable_across_row_and_column_order(tmp_path):
    frame = pd.DataFrame({"population": ["one", "one"],
                          "sales_record_id": ["sale2", "sale1"],
                          "anchor_date": pd.to_datetime(["2025-01-02", "2025-01-01"]),
                          "weather": [np.nan, 2.0]})
    first = persist_dataset_input(frame, tmp_path / "first")
    second = persist_dataset_input(frame.iloc[::-1][list(reversed(frame.columns))],
                                   tmp_path / "second")
    assert first == second
    saved = json.loads((tmp_path / "first" / "dataset_input.json").read_text())
    assert saved["columns"] == sorted(frame.columns)
    assert saved["records"][0]["sales_record_id"] == "sale1"
    reloaded = load_dataset_input(tmp_path / "first" / "dataset_input.json")
    assert persist_dataset_input(reloaded, tmp_path / "reloaded") == first


def test_callback_population_filter_precedes_snapshot_and_hash(tmp_path):
    frame = pd.DataFrame({"population": ["policy", "callback"],
                          "sales_record_id": ["one", "two"],
                          "anchor_date": ["2025-01-01", "2025-01-01"]})
    selected = benchmark.filter_populations(frame, ["callback"])
    benchmark.persist_dataset_input(selected, tmp_path)
    saved = benchmark.load_dataset_input(tmp_path / "dataset_input.json")
    assert saved["population"].tolist() == ["callback"]


def test_explicit_premise_context_extends_native_categories_without_changing_defaults(monkeypatch):
    default_categories = list(benchmark.CATEGORICAL)
    monkeypatch.setattr(benchmark, "CATEGORICAL", list(default_categories))
    benchmark.configure_premise_context(False)
    assert benchmark.CATEGORICAL == default_categories
    benchmark.configure_premise_context(True)
    benchmark.configure_premise_context(True)
    assert benchmark.CATEGORICAL == default_categories + ["premise_type"]
    model = benchmark.make_model("catboost_depth3_plain", ["history"])
    train = pd.DataFrame({"history": [0.0, 1.0, 2.0, 3.0] * 5,
                          **{column: ["A", "A", "B", "B"] * 5
                             for column in default_categories},
                          "premise_type": ["RESIDENTIAL", "COMMERCIAL"] * 10})
    model.fit(train, [False, False, True, True] * 5)
    transformed = model.named_steps["preprocess"].transform(train.iloc[[0]])
    assert transformed["categorical__premise_type"].iloc[0] == "RESIDENTIAL"


def test_validation_group_coverage_discloses_package_only_fallback():
    frame = pd.DataFrame({"validation_group": ["property:one", "property:one",
                                              "package:two"],
                          "address_hash": ["one", "one", None]})
    result = benchmark.validation_group_coverage(frame)
    assert result["rows_with_property_hash"] == 2
    assert result["rows_grouped_by_package_only"] == 1
    assert result["distinct_property_groups"] == 1
    assert result["property_hash_row_coverage"] == 2 / 3


def test_pest_aliases_normalize_case_punctuation_order_and_known_languages():
    first, indicators = benchmark.normalize_pest_context("Lipas, semut DAN tikus (Promo)")
    second, _ = benchmark.normalize_pest_context("Rats + Ants & Cockroaches")
    assert first == second == "ANT|COCKROACH|RODENT"
    assert indicators["pest_has_cockroach"] == 1
    assert indicators["pest_distinct_known_types"] == 3
    assert indicators["pest_has_other_terms"] == 0
    assert benchmark.normalize_pest_context("ANAI-ANAI + GPC")[0] == "GENERAL_CONTROL|TERMITE"
    assert benchmark.normalize_pest_context("Prevention")[0] == "UNSPECIFIED"


def test_pest_normalization_keeps_unknown_terms_and_avoids_substring_matches():
    category, indicators = benchmark.normalize_pest_context("Lipas dan kamitetep")
    assert category == "COCKROACH|OTHER"
    assert indicators["pest_has_other_terms"] == 1
    category, indicators = benchmark.normalize_pest_context("restaurant")
    assert category == "OTHER"
    assert indicators["pest_has_ant"] == 0
    assert indicators["pest_has_rodent"] == 0


def test_normalized_pest_context_is_explicit_and_leaves_default_contract_unchanged(monkeypatch):
    original_categories = list(benchmark.CATEGORICAL)
    original_features = {key: list(value) for key, value in benchmark.FEATURE_SETS.items()}
    monkeypatch.setattr(benchmark, "CATEGORICAL", list(original_categories))
    monkeypatch.setattr(benchmark, "FEATURE_SETS", {key: list(value)
                                                 for key, value in original_features.items()})
    benchmark.configure_pest_context(False)
    assert benchmark.CATEGORICAL == original_categories
    assert benchmark.FEATURE_SETS == original_features
    benchmark.configure_pest_context(True)
    assert benchmark.CATEGORICAL == original_categories + ["normalized_pest_category"]
    assert all(set(benchmark.PEST_CONTEXT_NUMERIC).issubset(numeric)
               for numeric in benchmark.FEATURE_SETS.values())


def test_normalized_pest_features_do_not_mutate_warehouse_column_contract(monkeypatch):
    source_numeric = list(benchmark.BASE_NUMERIC)
    monkeypatch.setattr(benchmark, "CATEGORICAL", list(benchmark.CATEGORICAL))
    monkeypatch.setattr(benchmark, "FEATURE_SETS", {"base": benchmark.BASE_NUMERIC})
    benchmark.configure_pest_context(True)
    assert benchmark.BASE_NUMERIC == source_numeric
    assert benchmark.FEATURE_SETS["base"] is not benchmark.BASE_NUMERIC


def test_callback_business_target_is_distinct_from_contractual_entitlement():
    metadata = benchmark.business_target_metadata(["matched_packages_recorded_callback_30d"])
    assert metadata["target"] == "recorded_corrective_callback_within_30d"
    assert metadata["target_column"] == TARGET
    assert metadata["grants_warranty_entitlement"] is False
    assert benchmark.business_target_metadata(["residential_3x_final_30d"])["target"] == TARGET
