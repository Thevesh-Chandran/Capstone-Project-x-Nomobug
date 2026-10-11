from datetime import datetime, timezone
import json

import pandas as pd
import pytest

from scripts import evaluate_cp2_followup_policy as p


def frame():
    return pd.DataFrame({"population": ["p"] * 6, "sales_record_id": list("abcdef"),
        "anchor_date": ["2026-10-12"] * 3 + ["2026-10-13"] * 3,
        "service_number": [1, 2, 2, 1, 2, 2],
        "challenger_all_history": [.9, .2, .1, .8, .3, .1],
        "prior_property_warranty_claims": [0, 5, None, 0, 0, 3],
        "warranty_signal_within_30d": [True, False, False, True, False, False]})


def test_daily_budget_is_equal_and_first_service_blind_spot_visible():
    rows = p.compare_daily(frame())
    assert [r["reviews"] for r in rows] == [2, 2, 2]
    assert rows[0]["callbacks_found"] == 2 and rows[1]["callbacks_found"] == 0
    assert rows[0]["first_service_callbacks_found"] == 2
    assert rows[1]["first_service_callbacks_found"] == 0
    assert rows[1]["history_missing_services"] == 1
    assert rows[2]["callbacks_found"] == pytest.approx(2/3)


def test_unknown_labels_or_invalid_probabilities_fail():
    f = frame()
    f["warranty_signal_within_30d"] = f.warranty_signal_within_30d.astype(object)
    f.loc[0, "warranty_signal_within_30d"] = None
    with pytest.raises(ValueError, match="binary"):
        p.compare_daily(f)
    f = frame()
    f.loc[0, "challenger_all_history"] = 1.1
    with pytest.raises(ValueError, match="probability"):
        p.compare_daily(f)


def test_second_evaluation_rejected_before_reading_sources(tmp_path, monkeypatch):
    result = tmp_path / 'result.json'
    result.write_text('{}')
    monkeypatch.setattr(p, 'RESULT', result)
    with pytest.raises(ValueError, match="already recorded"):
        p.evaluate(tmp_path / 'absent.json', tmp_path)


def test_protocol_hash_rules_and_maturity_guards(monkeypatch):
    monkeypatch.setattr(p, 'sha', lambda path: 'expected')
    protocol = {'rules': p.RULES, 'code_sha256': 'expected', 'ranking_code_sha256': 'expected',
        'collection_sha256': 'expected', 'bundle_sha256': 'expected',
        'declared_at_utc': '2026-10-11T04:00:00+00:00', 'cohort_start': '2026-10-12',
        'earliest_evaluation': '2026-11-30'}
    protocol['record_sha256'] = p.frozen.record_digest(protocol)
    with pytest.raises(ValueError, match='not matured'):
        p.check_protocol(protocol, datetime(2026,10,12,tzinfo=timezone.utc))
    p.check_protocol(protocol, datetime(2026,11,30,tzinfo=timezone.utc))
    protocol['bundle_sha256'] = 'changed'
    protocol['record_sha256'] = p.frozen.record_digest(protocol)
    with pytest.raises(ValueError, match='hash changed'):
        p.check_protocol(protocol, datetime(2026,11,30,tzinfo=timezone.utc))
