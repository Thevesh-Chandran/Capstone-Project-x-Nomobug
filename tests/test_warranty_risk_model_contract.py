import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_warranty_risk_baseline as model  # noqa: E402


def test_current_warranty_risk_model_contract_matches_code():
    contract = json.loads((
        ROOT / "config" / "warranty_risk_model_v3.json").read_text(encoding="utf-8"))
    encoded = json.dumps(
        model.RISK_CORE_NO_TEAM_FEATURES, separators=(",", ":")).encode()
    assert contract['superseded_by'] == 'warranty_fixed_30d_reviewed_v4'
    assert contract["selected_horizon_days"] == 30
    assert contract["eligible_population"] == "residential_3x_packages_only"
    assert contract["model_variant"] == "logistic_l2"
    assert contract["priority_review_percentile_cutoff"] == 0.5
    assert contract["high_risk_tier_supported"] is False
    assert contract["feature_count"] == len(model.RISK_CORE_NO_TEAM_FEATURES)
    assert contract["ordered_feature_sha256"] == hashlib.sha256(encoded).hexdigest()
    assert not any(feature == "assigned_team_calendar"
                   for feature in model.RISK_CORE_NO_TEAM_FEATURES)
    assert not any(feature == "pest_team_category"
                   for feature in model.RISK_CORE_NO_TEAM_FEATURES)


def test_prediction_safe_contract_excludes_event_day_weather():
    assert not (set(model.EVENT_DAY_WEATHER_FEATURES)
                & set(model.RISK_CORE_NO_TEAM_FEATURES))


def test_v1_contract_is_explicitly_superseded():
    contract = json.loads((
        ROOT / "config" / "warranty_risk_model_v1.json").read_text(encoding="utf-8"))
    assert contract["status"] == "superseded_due_to_event_day_weather_leakage"
    assert contract["superseded_by"] == "warranty_risk_60d_v2"


def test_v2_contract_is_explicitly_superseded_by_confirmed_policy_model():
    contract = json.loads((
        ROOT / "config" / "warranty_risk_model_v2.json").read_text(encoding="utf-8"))
    assert contract["status"] == "superseded_due_to_warranty_policy_scope_and_horizon"
    assert contract["superseded_by"] == "warranty_risk_residential_3x_30d_v3"
