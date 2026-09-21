import pandas as pd

from scripts.analyze_warranty_label_review import summarize, wilson_interval


def test_wilson_interval_contains_observed_proportion():
    low, high = wilson_interval(8, 10)
    assert low < 0.8 < high


def test_incomplete_review_lists_remaining_ids():
    frame = pd.DataFrame(
        {
            "Review ID": ["R001", "R002"],
            "Stratum": ["POSITIVE_EXPLICIT", "NEGATIVE_COMPLIMENTARY"],
            "Review label": ["Confirmed warranty claim", ""],
        }
    )
    result = summarize(frame)
    assert result["complete"] is False
    assert result["remaining_review_ids"] == ["R002"]


def test_complete_review_reports_precision_and_negative_error_rate():
    frame = pd.DataFrame(
        {
            "Review ID": ["R001", "R002", "R003", "R004"],
            "Stratum": [
                "POSITIVE_EXPLICIT",
                "POSITIVE_SEQUENCE_ELIGIBLE",
                "NEGATIVE_COMPLIMENTARY",
                "NEGATIVE_OTHER_MATCHED",
            ],
            "Review label": [
                "Confirmed warranty claim",
                "Not a warranty claim",
                "Confirmed warranty claim",
                "Not a warranty claim",
            ],
            "Error reason": ["", "Sequence false positive", "Missed claim", ""],
        }
    )
    result = summarize(frame)
    assert result["complete"] is True
    assert result["system_positive_precision"] == 0.5
    assert result["hard_negative_positive_rate"] == 0.5
    assert result["error_reasons"] == {
        "Sequence false positive": 1,
        "Missed claim": 1,
    }
