"""Keep the reviewed experimental model contract safe to interpret and replay."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_experiment_does_not_grant_entitlement_or_claim_independent_validation():
    contract = json.loads((ROOT / 'config/warranty_model_experiment_v4.json').read_text())
    assert contract['status'] == 'diagnostic_only_not_operational'
    assert contract['target_type'] == 'binary_categorical'
    assert contract['prediction_type'] == 'numerical_probability_0_to_1'
    assert 'not an untouched final test' in contract['reporting_caveat']
    targets = {model['population']: model['business_target'] for model in contract['models']}
    assert targets['matched_packages_recorded_callback_30d'] == 'recorded_corrective_callback_within_30d'
    assert targets['residential_3x_final_30d'] == 'recorded_warranty_claim_within_30d'


def test_selected_features_exclude_outcomes_future_dates_and_customer_identifiers():
    contract = json.loads((ROOT / 'config/warranty_model_experiment_v4.json').read_text())
    forbidden = {'warranty_signal_within_30d', 'warranty_claim_count_30d',
                 'sales_record_id', 'address_hash', 'anchor_event_row',
                 'anchor_date', 'outcome_end_date', 'observed_through',
                 'next_service_date', 'phone', 'email', 'customer_name'}
    for model in contract['models']:
        assert not forbidden.intersection(model['features'])
        assert len(model['features']) == len(set(model['features']))
        assert 0 <= model['threshold'] <= 1
        assert len(model['dataset_input_sha256']) == 64
        assert set(model['feature_preparation_options']) == {'premise_context', 'normalize_pest_context'}
