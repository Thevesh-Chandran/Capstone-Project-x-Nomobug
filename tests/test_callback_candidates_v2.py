import numpy as np
import pandas as pd
import pytest

from scripts import benchmark_warranty_models as b
from scripts import compare_callback_candidates_v2 as c
from scripts.compare_flood_models import configure_contracts


@pytest.fixture(autouse=True)
def isolated_contracts(monkeypatch):
    monkeypatch.setattr(b, 'CATEGORICAL', list(b.CATEGORICAL))
    monkeypatch.setattr(b, 'FEATURE_SETS', {k: list(v) for k, v in b.FEATURE_SETS.items()})
    monkeypatch.setattr(b, 'FLOOD_CONTEXT_ENABLED', b.FLOOD_CONTEXT_ENABLED)
    monkeypatch.setattr(b, 'REPORTED_FLOOD_CONTEXT_ENABLED', b.REPORTED_FLOOD_CONTEXT_ENABLED)


class FixedPredictor:
    def __init__(self, feature, scale):
        self.feature = feature
        self.scale = scale

    def predict_proba(self, frame):
        p = frame[self.feature].to_numpy() * self.scale
        return np.column_stack([1 - p, p])


def test_ensemble_honors_weights_and_member_feature_contracts():
    members = [
        {'pipeline': FixedPredictor('one', .2), 'features': ['one'], 'weight': .25},
        {'pipeline': FixedPredictor('two', .8), 'features': ['two'], 'weight': .75},
    ]
    frame = pd.DataFrame({'one': [1, 0], 'two': [1, 1], b.TARGET: [True, False]})
    assert np.allclose(c.predict_raw(members, frame), [.65, .6])
    with pytest.raises(ValueError, match='misses features'):
        c.predict_raw(members, frame.drop(columns='two'))


def test_ensemble_rejects_nonprobabilities_and_unbounded_weights():
    member = {'pipeline': FixedPredictor('one', 2.), 'features': ['one'], 'weight': 1.}
    with pytest.raises(ValueError, match='Invalid member'):
        c.predict_raw([member], pd.DataFrame({'one': [1]}))
    member['weight'] = -.1
    with pytest.raises(ValueError, match='weights'):
        c.predict_raw([member], pd.DataFrame({'one': [0]}))


def test_priority_selection_preserves_reference_ap_without_diagnostic_access():
    reference = dict(name='reference_et6', mean_ap=.25, mean_auc=.75,
                     mean_budget_recall=.5, mean_target_union_budget_recall=.1)
    low_ap = reference | dict(name='low_ap', mean_ap=.24, mean_budget_recall=.9)
    high_ap = reference | dict(name='high_ap', mean_ap=.3, mean_budget_recall=.4)
    high_recall = reference | dict(name='high_recall', mean_ap=.26, mean_budget_recall=.6)
    selected = c.select_candidates([reference, low_ap, high_ap, high_recall])
    assert selected['selected_ap']['name'] == 'high_ap'
    assert selected['selected_priority']['name'] == 'high_recall'
    with pytest.raises(ValueError, match='finite development'):
        c.select_candidates([reference | {'mean_ap': np.nan}])


def test_reservation_removes_every_2026_component_before_selection():
    frame = pd.DataFrame({'anchor_date': pd.to_datetime(['2025-08-01', '2025-09-01', '2026-01-01']),
        'outcome_end_date': pd.to_datetime(['2025-08-31', '2025-10-01', '2026-01-31']),
        'sales_record_id': ['old', 'independent', 'new'],
        'address_hash': ['shared', 'other', 'shared'],
        'validation_group': ['same', 'other', 'same'], b.TARGET: [True, False, True]})
    train, diagnostic, audit = c.reserved_split(frame)
    assert train.sales_record_id.tolist() == ['independent']
    assert diagnostic.sales_record_id.tolist() == ['new']
    assert audit['property_purged_training_rows'] == 1


def test_all_mature_refit_excludes_incomplete_last_day():
    frame = pd.DataFrame({'outcome_end_date': pd.to_datetime(['2026-09-26', '2026-09-27'])})
    with pytest.raises(ValueError, match='completed outcomes'):
        c.ensure_mature(frame, '2026-09-27')
    c.ensure_mature(frame.iloc[:1], '2026-09-27')


def test_historical_fit_uses_only_labels_mature_before_holdout_start():
    frame = pd.DataFrame({'anchor_date': pd.to_datetime(['2026-07-14', '2026-07-15', '2026-07-16']),
        'outcome_end_date': pd.to_datetime(['2026-08-13', '2026-08-14', '2026-08-15']),
        b.TARGET: [True, False, True]})
    train = c.historical_training(frame, '2026-08-15')
    assert train.anchor_date.dt.day.tolist() == [14, 15]
    with pytest.raises(ValueError, match='both classes'):
        c.historical_training(frame, '2026-08-14')


def raw_fixture():
    configure_contracts(False)
    columns = set(b.KEYS + b.BASE_NUMERIC + b.CATEGORICAL + b.WEATHER_NUMERIC
                  + b.ENVIRONMENT_NUMERIC + b.LANDCOVER_NUMERIC)
    frame = pd.DataFrame({col: [np.nan, np.nan] for col in columns})
    frame['population'] = 'callback'
    frame['sales_record_id'] = ['b', 'a']
    frame['anchor_date'] = '2026-09-28'
    frame['outcome_end_date'] = '2026-10-28'
    frame['pest_category'] = 'Lipas dan semut'
    frame['package_category'] = '3x'
    frame['premise_type'] = 'Residential'
    frame['service_number'] = [1, 2]
    frame['package_sessions_recorded'] = 3
    for col in ['prior_property_warranty_claims', 'prior_property_service_events',
                'prior_package_warranty_claims', 'prior_package_service_events']:
        frame[col] = 0
    return frame


def test_artifact_scoring_never_requires_or_reads_unknown_outcomes():
    artifact = {'members': [{'pipeline': FixedPredictor('anchor_is_first', .3),
        'features': ['anchor_is_first'], 'weight': 1.}], 'calibrator': None, 'threshold': .2}
    frame = raw_fixture()
    first = c.predict_artifact(artifact, frame.drop(columns=b.TARGET))
    second = c.predict_artifact(artifact, frame.assign(**{b.TARGET: True}))
    pd.testing.assert_frame_equal(first, second)
    assert first.sales_record_id.tolist() == ['a', 'b']
    assert first.probability.tolist() == [0., .3]
    assert b.TARGET not in first


def test_stronger_variants_have_declared_reproducible_complexity():
    configure_contracts(False)
    numeric = c.feature_sets()['targeted']
    tree = c.make_pipeline('et10_leaf5', numeric).named_steps['classifier']
    assert tree.max_depth == 10 and tree.min_samples_leaf == 5 and tree.random_state == 42
    booster = c.make_pipeline('hist3_balanced', numeric).named_steps['classifier']
    assert booster.class_weight == 'balanced' and booster.l2_regularization == 10
    cat = c.make_pipeline('cat6_plain', numeric).named_steps['classifier']
    params = cat.get_params()
    assert params['depth'] == 6 and params['l2_leaf_reg'] == 30
    assert not params['allow_writing_files']
    with pytest.raises(ValueError, match='Unknown bounded'):
        c.make_pipeline('unlimited_tuning', numeric)


@pytest.mark.parametrize('premise', ['RESIDENTIAL', ' residential ', 'COMMERCIAL', 'commercial'])
def test_contract_feature_matches_owner_policy_at_every_paid_stage_for_any_pest(premise):
    rows = []
    for sessions in [1, 3, 4, 6, 12]:
        for service in range(1, sessions + 1):
            for pest in ['COCKROACH', 'ANT|RODENT', 'TERMITE', 'UNSPECIFIED']:
                rows.append({'premise_type': premise, 'package_sessions_recorded': sessions,
                    'service_number': service, 'pest_category': pest, b.TARGET: True})
    frame = pd.DataFrame(rows)
    encoded = c.add_contract_policy_feature(frame)
    expected = [float(premise.strip().upper() == 'RESIDENTIAL' and
        (row['package_sessions_recorded'] in [4, 6, 12]
         or (row['package_sessions_recorded'] == 3 and row['service_number'] == 3))) for row in rows]
    assert encoded.contract_eligible_at_paid_anchor.tolist() == expected
    # Contractual ineligibility does not replace operational callback outcomes.
    assert encoded[b.TARGET].all()
    changed = c.add_contract_policy_feature(frame.assign(**{b.TARGET: False}))
    assert changed.contract_eligible_at_paid_anchor.tolist() == expected
