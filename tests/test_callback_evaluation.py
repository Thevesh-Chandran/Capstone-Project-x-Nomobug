import numpy as np
import pandas as pd
import pytest

from scripts import benchmark_warranty_models as b
from scripts.callback_evaluation import KEYS, paired_intervals
from scripts.compare_callback_blind_spots import paired_intervals as historical_intervals


def cohort():
    return pd.DataFrame({
        "population": ["callback"] * 10,
        "sales_record_id": list("abcdefghij"),
        "anchor_date": pd.to_datetime(["2025-01-01"] * 10),
        "validation_group": list("abcdefghij"),
        b.TARGET: [True, True] + [False] * 8,
        "service_number": [1] * 10,
        "pest_distinct_known_types": [1] * 10,
        "normalized_pest_category": ["COCKROACH"] * 10,
    })


def predictions(frame):
    reference = frame[KEYS + [b.TARGET]].assign(
        probability=[.99, .98, .7, .6, .5, .4, .3, .2, .1, .05])
    candidate = reference.assign(probability=[.1, .05, .7, .6, .5, .4, .3, .2, .99, .98])
    return reference, candidate


def test_shuffled_logs_cannot_reverse_the_paired_model_comparison():
    frame = cohort()
    reference, candidate = predictions(frame)
    expected = paired_intervals(frame, reference, candidate, 100)
    actual = paired_intervals(frame.iloc[::-1], reference.sample(frac=1, random_state=7),
                              candidate.iloc[::-1], 100)
    assert actual == expected
    assert expected["confidence_95pct"]["average_precision"][1] < 0
    assert expected["confidence_95pct"]["all_budget_recall"][1] < 0


def test_sorted_historical_results_remain_exactly_replayable():
    frame = cohort()
    reference, candidate = predictions(frame)
    assert paired_intervals(frame, reference, candidate, 30) == historical_intervals(
        frame, reference, candidate, 30)


@pytest.mark.parametrize("change", ["missing", "extra", "changed_target", "duplicate"])
def test_prediction_cohort_must_match_one_to_one_with_equal_outcomes(change):
    frame = cohort()
    reference, candidate = predictions(frame)
    if change == "missing":
        candidate = candidate.iloc[1:]
    elif change == "extra":
        candidate = pd.concat([candidate, candidate.iloc[[0]].assign(sales_record_id="extra")])
    elif change == "changed_target":
        candidate.loc[0, b.TARGET] = False
    else:
        candidate = pd.concat([candidate, candidate.iloc[[0]]])
    with pytest.raises((ValueError, pd.errors.MergeError)):
        paired_intervals(frame, reference, candidate, 10)


@pytest.mark.parametrize("invalid", [np.nan, np.inf, -.1, 1.1])
def test_invalid_saved_probabilities_cannot_enter_confidence_intervals(invalid):
    frame = cohort()
    reference, candidate = predictions(frame)
    candidate.loc[0, "probability"] = invalid
    with pytest.raises(ValueError, match="finite probabilities"):
        paired_intervals(frame, reference, candidate, 10)


def test_no_outcomes_or_duplicate_cohort_cannot_be_evaluated():
    frame = cohort()
    reference, candidate = predictions(frame)
    with pytest.raises(ValueError, match="Duplicate paired"):
        paired_intervals(pd.concat([frame, frame.iloc[[0]]]), reference, candidate, 10)
    frame[b.TARGET] = frame[b.TARGET].astype("object")
    frame.loc[0, b.TARGET] = None
    with pytest.raises(ValueError, match="cannot be null"):
        paired_intervals(frame, reference, candidate, 10)
