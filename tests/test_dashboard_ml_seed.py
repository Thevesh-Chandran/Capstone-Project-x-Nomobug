"""Guard the published model aggregates against stale or private source rows."""

import csv
import json

from scripts.generate_dashboard_ml_seed import DESTINATION, SOURCE, rows_from_source


def test_dashboard_seed_matches_frozen_holdout() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    expected = rows_from_source(source)
    with DESTINATION.open(newline="", encoding="utf-8") as handle:
        actual = list(csv.DictReader(handle))

    assert len(actual) == 16
    assert [(row["model_role"], row["metric_name"]) for row in actual] == [
        (row["model_role"], row["metric_name"]) for row in expected
    ]
    for got, want in zip(actual, expected):
        assert float(got["metric_value"]) == want["metric_value"]
    assert set(actual[0]) == {"model_role", "metric_name", "metric_value"}


def test_dashboard_source_rejects_changed_holdout_population() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    source["positive_rows"] = 6
    try:
        rows_from_source(source)
    except ValueError as exc:
        assert "holdout population changed" in str(exc)
    else:
        raise AssertionError("Changed holdout population was accepted")
