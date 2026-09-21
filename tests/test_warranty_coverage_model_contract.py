import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_warranty_coverage_episodes as model  # noqa: E402


def test_repeated_coverage_contract_matches_selected_history_features():
    contract = json.loads((
        ROOT / "config" / "warranty_coverage_episode_model_v1.json"
    ).read_text(encoding="utf-8"))
    features = model.BASE_NUMERIC + model.HISTORY_NUMERIC + model.CATEGORICAL
    encoded = json.dumps(features, separators=(",", ":")).encode()
    assert contract["status"] == "validated_experimental_not_operational"
    assert contract["selected_feature_set"] == "base_plus_prior_history"
    assert contract["features"] == features
    assert contract["ordered_feature_sha256"] == hashlib.sha256(encoded).hexdigest()
    assert contract["environment_decision"] == (
        "weather_and_hotosm_waterways_not_selected_after_package_grouped_validation")
