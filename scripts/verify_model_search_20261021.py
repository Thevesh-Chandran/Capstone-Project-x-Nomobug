"""Independent arithmetic/source checks for the 21 October research artifacts.

Does not fit models, choose cutoffs, modify production or query live sources.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, precision_score, recall_score,
    f1_score, average_precision_score, brier_score_loss, confusion_matrix,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/model_validation/20261021_management_model_search'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(observed, expected):
    assert np.isclose(observed, expected, rtol=1e-10, atol=1e-10), (observed, expected)


def verify_precision():
    folder = ROOT / 'outputs/model_validation/20261021_precision_targets_v2'
    protocol = load(folder / 'protocol.json')
    assert 'ENTIRE' in protocol['method']
    assert all(digest(ROOT / p) == value for p, value in protocol['protected'].items())
    source = load(folder / 'source_receipt.json')
    assert all(digest(ROOT / p) == value for p, value in source['hashes'].items())
    results = load(folder / 'results.json')
    checks = []
    for row in results:
        target, policy = row['target'], row['policy']
        frame = pd.read_csv(folder / f'{target}_{policy}_assessment.csv')
        actual = frame.actual.astype(int).to_numpy()
        probability = frame.probability.to_numpy()
        cutoff = row['threshold']
        predicted = probability >= cutoff
        assert len(actual) == row['rows'] and int(actual.sum()) == row['positives']
        tn, fp, fn, tp = confusion_matrix(actual, predicted, labels=[0, 1]).ravel()
        assert [int(tp), int(fp), int(fn), int(tn)] == [row[k] for k in ['TP', 'FP', 'FN', 'TN']]
        for name, function, arg in [
            ('accuracy', accuracy_score, predicted),
            ('balanced_accuracy', balanced_accuracy_score, predicted),
            ('precision', lambda a, p: precision_score(a, p, zero_division=0), predicted),
            ('recall', recall_score, predicted),
            ('f1', lambda a, p: f1_score(a, p, zero_division=0), predicted),
            ('average_precision', average_precision_score, probability),
            ('brier_score', brier_score_loss, probability),
        ]:
            close(function(actual, arg), row[name])
        close(1 - actual.mean(), row['always_no_accuracy'])
        expected_gate = (row['positives'] >= 20 and row['precision'] >= .5
                         and row['recall'] >= .2 and row['accuracy'] > row['always_no_accuracy'])
        assert expected_gate == row['passes_research_gate']
        selection = load(folder / f'{target}_selection.json')[policy]
        for key in ['family', 'features', 'history', 'threshold']:
            assert selection[key] == row[key]
        frozen = load(folder / f'{target}_frozen.json')[policy]
        assert digest(folder / frozen['file']) == frozen['sha256']
        assert row['input_count'] == len(source['feature_sets'][row['features']])
        assert not {'callback', 'warranty_claim_within_30d', 'outcome_end_date', 'complete_final'}.intersection(source['feature_sets'][row['features']])
        checks.append({'target': target, 'policy': policy, 'metrics_recomputed': True})
    assert len(results) == 9
    # Replay the split separately; the full modelling run is not repeated.
    from scripts.research_precision_targets_v2_20261021 import datasets, START, END
    from scripts import benchmark_warranty_models as b
    datasets_by_target, _, _ = datasets()
    for target, data in datasets_by_target.items():
        assessment = data[data.anchor_date.between(START, END)]
        pool = data[data.outcome_end_date.lt(START)]
        pool = pool[~pool.validation_group.isin(set(assessment.validation_group))]
        b.assert_package_property_disjoint(pool, assessment)
        assert pool.outcome_end_date.lt(START).all()
        for a, z in [('2025-07-01', '2025-10-01'), ('2025-10-01', '2026-01-01'), ('2026-01-01', '2026-04-01')]:
            training, validation, _ = b.purged_split(pool, a, z)
            b.assert_package_property_disjoint(training, validation)
            b.assert_package_property_disjoint(validation, assessment)
            assert training.outcome_end_date.lt(pd.Timestamp(a)).all()
            assert validation.outcome_end_date.lt(START).all()
        for row in [r for r in results if r['target'] == target]:
            close(len(assessment), row['rows'])
            close(assessment[b.TARGET].sum(), row['positives'])
            actual = pd.read_csv(folder / f"{target}_{row['policy']}_assessment.csv").actual.astype(int)
            assert actual.tolist() == assessment[b.TARGET].astype(int).tolist()
    return checks


def verify_forecasts():
    folder = ROOT / 'outputs/model_validation/20261021_management_forecasts_v2'
    rows = load(folder / 'results.json')
    protocol = load(folder / 'protocol.json')
    first_assessment = min(pd.to_datetime(protocol['assessment_origins']))
    checks = []
    for row in rows:
        task = row['task']
        frame = pd.read_csv(folder / f'{task}_assessment.csv')
        for column, key in [('selected', 'assessment'), ('baseline', 'baseline_assessment'), ('visible_only', 'visible_only_assessment')]:
            difference = frame[column] - frame.actual
            close(difference.abs().mean(), row[key]['mae'])
            close(np.sqrt((difference ** 2).mean()), row[key]['rmse'])
            close(difference.abs().sum() / frame.actual.sum(), row[key]['wape'])
        close(1 - row['assessment']['mae'] / row['baseline_assessment']['mae'], row['mae_improvement_fraction'])
        matrix = pd.read_csv(folder / f'{task}_matrix.csv', parse_dates=['origin', 'outcome_end', 'last_outcome_update'])
        chosen = load(folder / f'{task}_selection.json')
        assert not {'actual', 'late_additions', 'outcome_end', 'last_outcome_update'}.intersection(chosen['feature_names'])
        maturity = load(folder / f'{task}_validation_maturity.json')
        # The corrected selection's actual validation origins come from the saved ledger.
        development = pd.read_csv(folder / 'development_predictions.csv')
        dates = pd.to_datetime(development.loc[development.target.eq(row['target']) & development.horizon_weeks.eq(row['horizon_weeks']), 'origin']).unique()
        used = matrix[matrix.origin.isin(dates)]
        assert len(used) > 0
        assert (used.outcome_end <= first_assessment).all()
        assert (used.last_outcome_update < first_assessment).all()
        assert (frame.visible <= frame.actual + 1e-9).all()
        expected_gate = (row['mae_improvement_fraction'] >= .1 and row['uncertainty']['baseline_minus_selected_mae_95pct_interval'][0] > 0)
        assert expected_gate == row['research_gate_passed']
        checks.append({'task': task, 'metrics_recomputed': True, 'validation_mature_before_assessment': True, 'independent_calendar_history_available': False})
    assert len(rows) == 4
    assert all(digest(ROOT / p) == value for p, value in protocol['protected'].items())
    return checks


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {'precision_models': verify_precision(), 'forecasts': verify_forecasts(),
              'other_branch_checks': {
                  'repurchase': load(ROOT / 'outputs/model_validation/20261021_renewal_targets/acceptance.json'),
                  'enquiry': load(ROOT / 'outputs/model_validation/20261021_enquiry_conversion/verification.json'),
              },
              'scope': 'Arithmetic, source hashes, preserved artifacts, maturity and split replay. No claim of complete historical event-version reconstruction or new independent test.'}
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'precision_policies': len(result['precision_models']), 'forecast_tasks': len(result['forecasts']), 'verification': 'PASS'}))


if __name__ == '__main__':
    main()
