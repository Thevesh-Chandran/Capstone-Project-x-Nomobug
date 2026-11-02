import json

import numpy as np
import pandas as pd
import pytest

from scripts import evaluate_broad_callback_challenger as e


def evidence():
    protocol = {'new_retrospective_period': {'start': '2026-08-28', 'end': '2026-08-31',
                                             'outcomes_complete_through': '2026-09-30'}}
    source = {'complete_calendar_inventory': True, 'calendar_count': 6,
              'complete_outcomes_through': '2026-09-30',
              'earliest_extraction_at_utc': '2026-10-01T02:00:00+00:00'}
    features = {'complete_outcomes_through': '2026-09-30', 'temporary_tables_only': True,
                'query_maximum_bytes_billed': e.x.b.MAX_BYTES}
    selection = {'created_at_utc': '2026-10-01T01:00:00+00:00'}
    return source, features, selection, protocol


def test_selection_must_precede_fresh_extraction_and_coverage_must_be_complete():
    source, features, selection, protocol = evidence()
    e.validate_evidence(source, features, selection, protocol)
    for changes in [{'calendar_count': 5}, {'complete_calendar_inventory': False},
                    {'complete_outcomes_through': '2026-09-29'},
                    {'earliest_extraction_at_utc': '2026-10-01T00:00:00+00:00'}]:
        with pytest.raises(ValueError):
            e.validate_evidence(source | changes, features, selection, protocol)
    with pytest.raises(ValueError, match='bounded'):
        e.validate_evidence(source, features | {'query_maximum_bytes_billed': 2 * e.x.b.MAX_BYTES},
                            selection, protocol)


def rows():
    return pd.DataFrame([{'population': 'test_callback', 'sales_record_id': f'test-sale-{i}',
                          'anchor_date': day, 'outcome_end_date': end,
                          e.x.b.TARGET: bool(i % 2), 'service_number': 1,
                          'package_sessions_recorded': 3, 'premise_type': 'RESIDENTIAL'}
                         for i, (day, end) in enumerate([('2026-08-27', '2026-09-26'),
                                                        ('2026-08-28', '2026-09-27'),
                                                        ('2026-08-31', '2026-09-30'),
                                                        ('2026-09-01', '2026-10-01')])])


def test_cohort_boundaries_include_only_the_declared_four_days():
    selected = e.cohort(rows(), evidence()[3])
    assert selected.anchor_date.tolist() == ['2026-08-28', '2026-08-31']
    with pytest.raises(ValueError, match='No eligible'):
        e.cohort(rows().iloc[:1], evidence()[3])
    invalid = rows()
    invalid.loc[1, 'outcome_end_date'] = '2026-10-01'
    with pytest.raises(ValueError, match='30 days'):
        e.cohort(invalid, evidence()[3])


def test_paired_bootstrap_keeps_identical_models_equal_and_handles_no_positives():
    frame = rows().assign(validation_group=['a', 'b', 'b', 'c'])
    scores = np.array([.1, .9, .2, .8])
    result = e.bootstrap(frame, scores, scores, repeats=30)
    assert result['components'] == 3
    assert result['intervals_95pct']['average_precision'] == [0., 0.]
    frame[e.x.b.TARGET] = False
    result = e.bootstrap(frame, scores, scores, repeats=30)
    assert result['intervals_95pct']['roc_auc'] is None


def test_main_refuses_any_repeat_before_reading_new_outcomes(tmp_path, monkeypatch):
    import sys
    monkeypatch.setattr(e.x.b, 'ROOT', tmp_path)
    experiment = tmp_path / 'outputs' / 'experiment'
    (experiment / 'later_period_evaluation').mkdir(parents=True)
    monkeypatch.setattr(sys, 'argv', ['evaluate', '--experiment-dir', str(experiment),
                                    '--source-run-dir', str(tmp_path / 'outputs' / 'missing_source')])
    with pytest.raises(ValueError, match='One-time'):
        e.main()
