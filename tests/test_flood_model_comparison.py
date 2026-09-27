import numpy as np
import pandas as pd
import pytest

from scripts import benchmark_warranty_models as benchmark
from scripts import compare_flood_models as comparison


@pytest.fixture
def isolated_contracts(monkeypatch):
    monkeypatch.setattr(benchmark, "CATEGORICAL", list(benchmark.CATEGORICAL))
    monkeypatch.setattr(benchmark, "FEATURE_SETS",
                        {key: list(value) for key, value in benchmark.FEATURE_SETS.items()})
    monkeypatch.setattr(benchmark, "FLOOD_CONTEXT_ENABLED", False)
    monkeypatch.setattr(benchmark, "REPORTED_FLOOD_CONTEXT_ENABLED", False)


def source_fixture():
    columns = set(benchmark.KEYS + benchmark.BASE_NUMERIC + benchmark.CATEGORICAL
                  + benchmark.WEATHER_NUMERIC + benchmark.ENVIRONMENT_NUMERIC
                  + benchmark.LANDCOVER_NUMERIC)
    columns -= benchmark.DERIVED_CATEGORICAL
    frame = pd.DataFrame({column: [np.nan, np.nan] for column in columns})
    frame["population"] = "matched_packages_recorded_callback_30d"
    frame[benchmark.TARGET] = [False, True]
    frame["sales_record_id"] = ["one", "two"]
    frame["anchor_date"] = ["2025-01-01", "2026-01-01"]
    frame["outcome_end_date"] = ["2025-01-31", "2026-01-31"]
    return frame


def test_flood_context_is_explicit_and_does_not_change_default_contract(isolated_contracts):
    original_features = {key: list(value) for key, value in benchmark.FEATURE_SETS.items()}
    original_base = list(benchmark.BASE_NUMERIC)
    benchmark.configure_flood_context(False)
    assert benchmark.FEATURE_SETS == original_features
    assert benchmark.feature_preparation_options() == {
        "premise_context": False, "normalize_pest_context": False}
    benchmark.prepare_frame(source_fixture())  # No flood source fields required.
    benchmark.configure_flood_context(True)
    benchmark.configure_flood_context(True)
    assert benchmark.BASE_NUMERIC == original_base
    assert benchmark.FEATURE_SETS["base"] is not benchmark.BASE_NUMERIC
    assert all(numeric.count(benchmark.FLOOD_NUMERIC[0]) == 1
               for numeric in benchmark.FEATURE_SETS.values())
    assert benchmark.feature_preparation_options()["flood_context"] is True
    with pytest.raises(ValueError, match="missing contracted columns"):
        benchmark.prepare_frame(source_fixture())


def test_flood_missing_measurements_are_not_converted_to_dry_days(isolated_contracts):
    frame = source_fixture()
    for column in benchmark.FLOOD_NUMERIC:
        frame[column] = [np.nan, "0"]
    frame["gfm_prior_30d_observed_days"] = [0, "5"]
    frame["gfm_prior_30d_flood_detected_days"] = [0, "0"]
    benchmark.configure_flood_context(True)
    prepared = benchmark.prepare_frame(frame)
    assert prepared["gfm_prior_30d_max_flood_fraction_1km"].isna().iloc[0]
    assert prepared["gfm_prior_30d_max_flood_fraction_1km"].iloc[1] == 0
    assert prepared["gfm_prior_30d_observed_days"].dtype == float
    assert prepared["gfm_prior_30d_observed_days"].tolist() == [0, 5]


@pytest.mark.parametrize("column,value,error", [
    ("gfm_prior_30d_max_flood_fraction_1km", 1.1, "outside"),
    ("gfm_days_since_valid_observation", -1, "Negative"),
    ("gfm_prior_30d_flood_detected_days", 31, "counts violate"),
])
def test_flood_contract_rejects_impossible_values(isolated_contracts, column, value, error):
    frame = source_fixture()
    for feature in benchmark.FLOOD_NUMERIC:
        frame[feature] = 0
    frame[column] = value
    benchmark.configure_flood_context(True)
    with pytest.raises(ValueError, match=error):
        benchmark.prepare_frame(frame)


def test_ablation_resets_contracts_and_preserves_every_anchor_and_split(isolated_contracts):
    comparison.configure_contracts(False)
    raw = source_fixture()
    for column in benchmark.FLOOD_NUMERIC:
        raw[column] = np.nan
    baseline = benchmark.prepare_frame(raw)
    baseline_features = {key: list(value) for key, value in benchmark.FEATURE_SETS.items()}
    comparison.configure_contracts(True)
    flood = benchmark.prepare_frame(raw)
    assert comparison.split_receipt(baseline) == comparison.split_receipt(flood)
    for name, numeric in benchmark.FEATURE_SETS.items():
        assert numeric == baseline_features[name] + benchmark.FLOOD_NUMERIC
    comparison.configure_contracts(False)
    assert benchmark.FEATURE_SETS == baseline_features
    assert "flood_context" not in benchmark.feature_preparation_options()


def test_observation_only_control_excludes_every_detected_flood_measurement(isolated_contracts):
    comparison.configure_contracts(False)
    baseline = {key: list(value) for key, value in benchmark.FEATURE_SETS.items()}
    categories = list(benchmark.CATEGORICAL)
    comparison.configure_observation_only_contracts()
    assert benchmark.CATEGORICAL == categories
    for name, numeric in benchmark.FEATURE_SETS.items():
        assert numeric == baseline[name] + comparison.OBSERVATION_ONLY_NUMERIC
        assert not any("flood_fraction" in column or "detected" in column
                       for column in numeric)


def test_reported_regional_context_is_separate_from_observed_satellite_context(isolated_contracts):
    comparison.configure_contracts(False)
    baseline = {key: list(value) for key, value in benchmark.FEATURE_SETS.items()}
    comparison.configure_contracts(False, True)
    for name, numeric in benchmark.FEATURE_SETS.items():
        assert numeric == baseline[name] + benchmark.REPORTED_FLOOD_NUMERIC
        assert not any(column.startswith("gfm_") for column in numeric)
    assert benchmark.feature_preparation_options() == {
        "premise_context": True, "normalize_pest_context": True,
        "reported_flood_context": True}
    frame = source_fixture()
    for column in benchmark.REPORTED_FLOOD_NUMERIC:
        frame[column] = "0"
    assert benchmark.prepare_frame(frame)["gdacs_prior_30d_reported_events"].dtype == float
    frame["gdacs_prior_7d_reported_events"] = 1
    with pytest.raises(ValueError, match="nested windows"):
        benchmark.prepare_frame(frame)


def test_paired_bootstrap_uses_identical_component_samples_and_rejects_different_cohorts():
    baseline = pd.DataFrame({
        "population": ["callback"] * 4,
        "sales_record_id": ["one", "two", "three", "four"],
        "anchor_date": ["2026-01-01"] * 4,
        "outcome_end_date": ["2026-01-31"] * 4,
        "validation_group": ["property:one", "property:one",
                             "property:two", "property:two"],
        benchmark.TARGET: [False, True, False, True],
        "probability": [0.1, 0.9, 0.2, 0.8], "threshold": [0.5] * 4,
    })
    result = comparison.paired_bootstrap(baseline, baseline.copy(), repeats=20)
    assert result["groups"] == 2
    assert result["valid_repeats"] == 20
    assert all(interval == [0, 0] for interval in result["confidence_95pct"].values())
    with pytest.raises(ValueError, match="different anchors"):
        comparison.paired_bootstrap(baseline, baseline.iloc[:-1], repeats=1)
