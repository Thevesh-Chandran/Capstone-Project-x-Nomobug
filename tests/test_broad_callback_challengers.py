import json

import numpy as np
import pandas as pd
import pytest

from scripts import compare_broad_callback_challengers as x


def raw_history():
    return pd.DataFrame({'prior_area_claims_90d': [2, 0], 'prior_area_services_90d': [10, 0],
                         'prior_property_service_events': [3, 0], 'prior_package_service_events': [2, 0],
                         'days_since_prior_property_claim': [30, np.nan],
                         'prior_14d_precipitation_mm': [20, 0], 'prior_14d_wet_days_1mm': [4, 0],
                         'prior_7d_precipitation_mm': [10, 0], 'prior_30d_precipitation_mm': [100, 0],
                         'prior_7d_relative_humidity_mean_pct': [80, np.nan],
                         'prior_30d_relative_humidity_mean_pct': [75, 70],
                         'prior_7d_soil_moisture_0_to_7cm_mean': [.4, np.nan],
                         'prior_30d_soil_moisture_0_to_7cm_mean': [.3, .2],
                         'prior_7d_temperature_mean_c': [30, np.nan],
                         'prior_30d_temperature_mean_c': [29, 28],
                         'days_since_previous_service': [14, np.nan], 'anchor_is_first': [0, 1]})


def test_engineering_uses_known_history_and_preserves_undefined_measurements():
    frame = raw_history()
    expected = x.add_features(frame)
    assert np.isclose(expected.loc[0, 'area_return_rate_smoothed'], .15)
    assert np.isclose(expected.loc[0, 'property_claim_recency_30d'], np.exp(-1))
    assert expected.loc[0, 'rain_per_wet_day_14d'] == 5
    assert expected.loc[0, 'recent_rain_share_30d'] == .1
    assert expected.loc[0, 'humidity_change_7_vs_30d'] == 5
    assert expected.loc[0, 'gap_rain_interaction'] == 140
    assert expected.loc[1, 'rain_per_wet_day_14d'] != expected.loc[1, 'rain_per_wet_day_14d']
    assert expected.loc[1, 'first_property_claim_recency'] != expected.loc[1, 'first_property_claim_recency']
    with_target = x.add_features(frame.assign(**{x.b.TARGET: [True, False]}))
    pd.testing.assert_frame_equal(expected[x.ENGINEERED], with_target[x.ENGINEERED])
    assert not set(x.ENGINEERED) & {x.b.TARGET, 'claim_request_date', 'callback_visit_reason'}


def test_selection_preserves_main_metric_and_does_not_claim_tie_as_gain():
    control = dict(name='v5_control', mean_ap=.25, mean_review_recall=.5, mean_auc=.8)
    ap_loss = control | dict(name='recall_only', mean_ap=.24, mean_review_recall=.9)
    recall_loss = control | dict(name='ap_only', mean_ap=.9, mean_review_recall=.49)
    assert x.select([control, ap_loss, recall_loss])['primary'] == control
    assert x.select([control, ap_loss, recall_loss])['priority'] == control
    candidate = control | dict(name='gain', mean_ap=.26, mean_review_recall=.51)
    assert x.select([control, candidate])['primary']['name'] == 'gain'
    assert x.select([control, candidate])['priority']['name'] == 'gain'
    with pytest.raises(ValueError, match='finite'):
        x.select([control | {'mean_ap': np.nan}])


def test_declared_contracts_have_no_identity_or_target_predictors(monkeypatch):
    monkeypatch.setattr(x.b, 'CATEGORICAL', list(x.b.CATEGORICAL))
    monkeypatch.setattr(x.b, 'FEATURE_SETS', {k: list(v) for k, v in x.b.FEATURE_SETS.items()})
    x.c.configure_contracts(False)
    protocol = json.loads(x.PROTOCOL.read_text())
    assert len({spec['name'] for spec in protocol['models'] + protocol['ensembles']}) == 37
    for spec in protocol['models']:
        numeric = x.numeric_contract(spec['features'])
        assert not set(numeric) & {x.b.TARGET, *x.c.KEYS, 'address_hash'}
        pipe = x.pipeline(spec)
        params = pipe.named_steps['classifier'].get_params()
        assert params.get('n_jobs', 2) in (2, None)
    assert 'prior_7d_precipitation_mm' not in x.numeric_contract('history_only')
    assert 'water_rain_interaction' not in x.numeric_contract('no_environment')
    with pytest.raises(ValueError, match='Unknown'):
        x.numeric_contract('future_weather')


class Constant:
    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, frame):
        return np.tile([1 - self.probability, self.probability], (len(frame), 1))


def test_first_expert_only_changes_known_first_service_stage():
    frame = pd.DataFrame({'service_number': [1, 2, 3], 'x': [1, 2, 3]})
    member = dict(pipeline=Constant(.2), first_service_pipeline=Constant(.7), features=['x'])
    assert np.allclose(x.predict_member(member, frame), [.7, .2, .2])
    assert np.allclose(x.predict_members([member | {'weight': 1.}], frame), [.7, .2, .2])
    with pytest.raises(ValueError, match='ensemble'):
        x.predict_members([member | {'weight': -.5}], frame)


def source_row():
    return dict(population='test_callback', sales_record_id='test-sale', anchor_date='2026-01-01',
                outcome_end_date='2026-01-31', warranty_signal_within_30d=True,
                service_number=1, package_sessions_recorded=3, premise_type='RESIDENTIAL')


@pytest.mark.parametrize('update', [{x.b.TARGET: None}, {x.b.TARGET: 'unknown'},
                                    {'outcome_end_date': '2026-01-30'}, {'service_number': 4},
                                    {'service_number': 1.5}, {'sales_record_id': None}])
def test_audit_rejects_invalid_outcomes_windows_keys_and_overrun_visits(update):
    with pytest.raises(ValueError):
        x.audit_source(pd.DataFrame([source_row() | update]))


def test_audit_counts_service_windows_and_refuses_duplicates():
    assert x.audit_source(pd.DataFrame([source_row()]))['first_positive_windows'] == 1
    with pytest.raises(ValueError, match='Unique'):
        x.audit_source(pd.DataFrame([source_row(), source_row()]))


def test_predictor_replay_refuses_changed_challenger_code():
    with pytest.raises(ValueError, match='code changed'):
        x.predict_artifact({'code_sha256': 'changed'}, pd.DataFrame())


def test_plain_catboost_fits_without_passing_json_null_to_native_options(monkeypatch):
    monkeypatch.setattr(x.b, 'CATEGORICAL', ['pest'])
    monkeypatch.setattr(x, 'numeric_contract', lambda _: ['x'])
    frame = pd.DataFrame({'x': np.arange(40), 'pest': ['A', 'B'] * 20,
                          x.b.TARGET: [True, False] * 20})
    spec = {'name': 'plain_test', 'family': 'cat', 'features': 'targeted',
            'params': {'iterations': 2, 'auto_class_weights': None}}
    assert np.isfinite(x.predict_member(x.fit(spec, frame), frame)).all()
