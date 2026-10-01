import numpy as np
import pandas as pd
import pytest

from scripts import benchmark_warranty_models as b
from scripts import compare_first_service_challengers as f
from scripts.compare_flood_models import configure_contracts


def test_late_august_holdout_is_excluded_before_preparation():
    source = pd.DataFrame({'anchor_date': ['2026-08-14', '2026-08-15', '2026-10-01'],
                           'marker': [1, 2, 3]})
    assert f.allowed_source(source).marker.tolist() == [1]


def test_first_reservation_preserves_exact_common_budget_and_high_scores():
    scores = np.array([.9, .8, .7, .6, .5, .4, .3, .2, .1, 0.])
    first = np.array([False] * 7 + [True] * 3)
    assert np.flatnonzero(f.review_mask(scores, first)).tolist() == [0, 1]
    assert np.flatnonzero(f.review_mask(scores, first, .25)).tolist() == [0, 7]
    assert f.review_mask(scores, np.zeros(10, dtype=bool), .25).sum() == 2


def test_review_ties_are_stable_and_do_not_expand_capacity():
    assert np.flatnonzero(f.review_mask(np.ones(10), [False] * 10)).tolist() == [0, 1]
    with pytest.raises(ValueError, match='Finite'):
        f.review_mask([np.nan], [True])
    with pytest.raises(ValueError, match='Aligned'):
        f.review_mask([.5, .2], [True])


def test_selection_rejects_first_gain_at_cost_of_ap_or_total_recall():
    control = dict(name='v5_control__reserve0', mean_ap=.25,
                   mean_review_recall=.5, mean_first_recall=0.)
    bad_ap = control | dict(name='bad_ap', mean_ap=.24, mean_first_recall=.9)
    bad_recall = control | dict(name='bad_recall', mean_review_recall=.49, mean_first_recall=.9)
    valid = control | dict(name='valid', mean_ap=.26, mean_first_recall=.1)
    assert f.select_candidate([control, bad_ap, bad_recall, valid])['name'] == 'valid'
    assert f.select_candidate([control, bad_ap, bad_recall])['name'] == control['name']
    with pytest.raises(ValueError, match='Finite complete'):
        f.select_candidate([control | {'mean_ap': np.nan}])


def test_ablated_feature_contract_excludes_stage_but_keeps_environment(monkeypatch):
    monkeypatch.setattr(b, 'CATEGORICAL', list(b.CATEGORICAL))
    monkeypatch.setattr(b, 'FEATURE_SETS', {k: list(v) for k, v in b.FEATURE_SETS.items()})
    configure_contracts(False)
    numeric, categorical = f.feature_columns('stage_reduced')
    assert not set(numeric) & f.STAGE_FIELDS
    assert not any(x.startswith(('first_pest_', 'final_pest_')) for x in numeric)
    assert 'package_category' not in categorical
    assert 'prior_14d_precipitation_mm' in numeric
    with pytest.raises(ValueError, match='Unknown'):
        f.feature_columns('unregistered')


def test_review_metrics_distinguish_first_service_from_total_coverage():
    frame = pd.DataFrame({'service_number': [1, 2, 1, 2, 1],
                          b.TARGET: [True, True, False, False, False]})
    global_review = f.review_metrics(frame, [.1, .9, .2, .3, .4], 0.)
    reserved_review = f.review_metrics(frame, [.1, .9, .2, .3, .4], .25)
    assert global_review['all']['reviewed'] == reserved_review['all']['reviewed'] == 1
    assert global_review['first_service']['found'] == 0
    # Reservation chooses the highest-scored first service, even when it is
    # negative; it must not use labels to manufacture better coverage.
    assert reserved_review['first_service']['reviewed'] == 1
    assert reserved_review['all']['found'] == 0
