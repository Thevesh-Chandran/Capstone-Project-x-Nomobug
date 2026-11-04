import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.build_cp2_decision_support import counts, development_rows, holdout_rows, select_exact

ROOT = Path(__file__).resolve().parents[1]


def sample():
    return pd.DataFrame({"population": ["test"] * 10, "sales_record_id": list(map(str, range(10))),
        "anchor_date": ["2025-05-01"] * 10, "score": [1.] * 9 + [None],
        "warranty_signal_within_30d": [True, False] * 5})


def test_ties_are_order_independent_exact_budget_and_do_not_use_labels():
    frame = sample()
    a = select_exact(frame, "score")
    assert a.sum() == 2 and not a.iloc[-1]
    shuffled = frame.sample(frac=1, random_state=5)
    assert set(frame.loc[a, "sales_record_id"]) == set(shuffled.loc[select_exact(shuffled, "score"), "sales_record_id"])
    frame["warranty_signal_within_30d"] = ~frame.warranty_signal_within_30d
    assert a.equals(select_exact(frame, "score"))


def test_duplicate_keys_and_invalid_scores_rejected():
    frame = sample()
    with pytest.raises(ValueError, match="duplicate"):
        select_exact(pd.concat([frame, frame.iloc[:1]], ignore_index=True), "score")
    frame.loc[0, "score"] = float("inf")
    with pytest.raises(ValueError, match="Invalid"):
        select_exact(frame, "score")


def test_zero_positives_is_undefined_capture_and_unknown_is_not_negative():
    labels = pd.Series([False, False])
    result = counts(labels, pd.Series([True, False]))
    assert result["callback_capture"] is None and result["review_precision"] == 0
    with pytest.raises(ValueError, match="binary"):
        counts(pd.Series([None, False]), pd.Series([True, False]))


def test_published_holdout_counts_reconcile_and_random_is_labelled():
    source = json.loads((ROOT / "config/warranty_new_holdout_v5.json").read_text())
    rows = holdout_rows(source)
    assert [r["callbacks_found"] for r in rows] == [4, 3, 1]
    assert rows[0]["reviews_without_callback"] == 16
    assert "expectation" in rows[2]["evidence_type"]
    source["results"]["selected_ap"]["segments"]["all"]["budget_FP"] = 15
    with pytest.raises(ValueError, match="reconcile"):
        holdout_rows(source)


def test_development_comparison_rejects_label_mismatch_or_future_test_rows():
    p = sample().rename(columns={"score": "raw_probability"}).fillna({"raw_probability": .1})
    p["fold"] = "2025_q2"
    f = p.copy()
    f["prior_property_warranty_claims"] = 0
    f.loc[0, "warranty_signal_within_30d"] = False
    with pytest.raises(ValueError, match="align"):
        development_rows(p, f)
    f["warranty_signal_within_30d"] = p.warranty_signal_within_30d
    p["fold"] = "holdout"
    with pytest.raises(ValueError, match="2025"):
        development_rows(p, f)


def test_new_views_pass_release_privacy_gate_only_with_aggregate_fields():
    from types import SimpleNamespace
    from google.cloud import bigquery
    from scripts.cp2_reporting_release import MANAGEMENT_GOLD_VIEWS, verify_management_privacy
    for name in ["dashboard_attention", "dashboard_model_review", "dashboard_followup_baselines", "dashboard_feature_comparison"]:
        assert name in MANAGEMENT_GOLD_VIEWS
        client = SimpleNamespace(get_table=lambda _: SimpleNamespace(schema=[bigquery.SchemaField("customer_email", "STRING")]))
        with pytest.raises(ValueError, match="Private field"):
            verify_management_privacy(client, [("gold", name, "candidate")])
