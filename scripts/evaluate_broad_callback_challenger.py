"""One-time later-period check of challengers frozen before fresh source extraction."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from scripts import compare_broad_callback_challengers as x
from scripts import compare_first_service_challengers as first


def aware(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() is None:
        raise ValueError('Timezone-bearing evidence timestamps required')
    return parsed.astimezone(timezone.utc)


def validate_evidence(source_receipt, feature_receipt, selection, protocol):
    period = protocol['new_retrospective_period']
    required = period['outcomes_complete_through']
    if (source_receipt.get('complete_calendar_inventory') is not True
            or source_receipt.get('calendar_count') != 6
            or source_receipt['complete_outcomes_through'] < required
            or feature_receipt['complete_outcomes_through'] != source_receipt['complete_outcomes_through']):
        raise ValueError('Complete authoritative Calendar outcome coverage required')
    if aware(source_receipt['earliest_extraction_at_utc']) <= aware(selection['created_at_utc']):
        raise ValueError('Fresh sources must be extracted after development selection was frozen')
    if feature_receipt.get('temporary_tables_only') is not True or feature_receipt.get('query_maximum_bytes_billed') != x.b.MAX_BYTES:
        raise ValueError('Governed bounded source derivation required')


def cohort(source, protocol):
    period = protocol['new_retrospective_period']
    dates = pd.to_datetime(source.anchor_date, errors='raise')
    selected = source.loc[dates.between(period['start'], period['end'])].copy()
    if selected.empty:
        raise ValueError('No eligible mature service windows in declared later period')
    x.audit_source(selected)
    end = pd.to_datetime(selected.outcome_end_date, errors='raise')
    if (end > pd.Timestamp(period['outcomes_complete_through'])).any():
        raise ValueError('Declared evaluation outcome window is incomplete')
    return selected


def bootstrap(frame, baseline, challenger, repeats=300):
    """Paired connected-component uncertainty with the same exact review budget."""
    if len(frame) != len(baseline) or len(frame) != len(challenger):
        raise ValueError('Aligned paired scores required')
    groups = list(frame.groupby('validation_group', sort=False).indices.values())
    y = frame[x.b.TARGET].to_numpy(dtype=bool)
    values = {'roc_auc': [], 'average_precision': [], 'review_recall': []}
    rng = np.random.default_rng(42)
    for _ in range(repeats):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        if np.unique(y[idx]).size != 2:
            continue
        metrics = [x.b.score(y[idx], p[idx]) for p in (baseline, challenger)]
        for key in ('roc_auc', 'average_precision'):
            values[key].append(metrics[1][key] - metrics[0][key])
        reviews = [first.review_mask(p[idx], np.zeros(len(idx), dtype=bool)) for p in (baseline, challenger)]
        values['review_recall'].append(float((reviews[1] & y[idx]).sum() / y[idx].sum()
                                            - (reviews[0] & y[idx]).sum() / y[idx].sum()))
    return {'direction': 'challenger_minus_control', 'components': len(groups),
            'requested_repeats': repeats,
            'valid_repeats': {key: len(value) for key, value in values.items()},
            'intervals_95pct': {key: [float(v) for v in np.quantile(value, [.025, .975])]
                                if value else None for key, value in values.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment-dir', type=Path, required=True)
    parser.add_argument('--source-run-dir', type=Path, required=True)
    args = parser.parse_args()
    experiment = first.private_output(args.experiment_dir)
    source_dir = first.private_output(args.source_run_dir)
    out = experiment / 'later_period_evaluation'
    if out.exists():
        raise ValueError('One-time later-period result must not be overwritten or repeated')
    protocol = json.loads(x.PROTOCOL.read_text())
    results = json.loads((experiment / 'results.json').read_text())
    selection_path = experiment / 'development_selection.json'
    selection = json.loads(selection_path.read_text())
    if (results['selection_sha256'] != x.digest(selection_path)
            or selection['protocol_sha256'] != x.digest(x.PROTOCOL)
            or selection['code_sha256'] != x.digest(x.__file__)
            or results['selected'] != selection['selected']):
        raise ValueError('Declared model selection or feature code changed')
    frozen = x.b.ROOT / 'outputs/cp2-v2/prospective_callback_v2/bundle.json'
    if x.digest(frozen) != protocol['frozen_bundle_sha256']:
        raise ValueError('Frozen October bundle changed')
    source_receipt = json.loads((source_dir / 'source_receipt.json').read_text())
    feature_receipt = json.loads((source_dir / 'feature_receipt.json').read_text())
    validate_evidence(source_receipt, feature_receipt, selection, protocol)
    for filename, key in [('calendar_private.json', 'calendar_sha256'), ('sheets_private.json', 'sheets_sha256')]:
        if x.digest(source_dir / filename) != source_receipt[key]:
            raise ValueError('Fresh source snapshot hash changed')
    data_path = source_dir / 'features/mature_labels/dataset_input.json'
    if x.digest(data_path) != feature_receipt['mature_input_sha256']:
        raise ValueError('Fresh derived feature hash changed')
    # Authenticate artifacts and chronology before accessing the held-out input.
    models = {}
    for role, metadata in results['historical_artifacts'].items():
        path = first.private_output(x.b.ROOT / metadata['path'])
        if x.digest(path) != metadata['sha256']:
            raise ValueError('Frozen later-period artifact changed')
        if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) >= aware(source_receipt['earliest_extraction_at_utc']):
            raise ValueError('Artifact must exist before fresh outcome extraction')
        model = joblib.load(path)
        if (model['training_max_outcome_end_date'] >= protocol['new_retrospective_period']['start']
                or model['selection'] != selection['selected'][role]):
            raise ValueError('Artifact training maturity or selection escaped protocol')
        models[role] = model
    selected_source = cohort(x.b.load_dataset_input(data_path), protocol)
    frame = x.prepare(selected_source)
    out.mkdir()
    source_hash = x.b.persist_dataset_input(selected_source, out / 'cohort_private')
    role_results, probabilities = {}, {}
    predictors = selected_source.drop(columns=[x.b.TARGET])
    for role, model in models.items():
        replay = x.predict_artifact(model, predictors)
        if not replay[x.c.KEYS].equals(frame[x.c.KEYS]):
            raise ValueError('Held-out inference key alignment failed')
        probability = replay.probability.to_numpy()
        probabilities[role] = probability
        raw = x.predict_members(model['members'], frame)
        role_results[role] = {'selection': model['selection'],
                              **x.b.score(frame[x.b.TARGET], probability, model['threshold']),
                              'review': first.review_metrics(frame, raw, 0.)}
        frame[x.c.KEYS + [x.b.TARGET]].assign(probability=probability).to_csv(out / f'{role}_predictions_private.csv', index=False)
    intervals = {role: bootstrap(frame, probabilities['control'], probabilities[role]) for role in ('primary', 'priority')}
    result = {'status': 'one_time_retrospective_later_period_not_online_prediction',
              'evaluated_at_utc': datetime.now(timezone.utc).isoformat(),
              'protocol_sha256': x.digest(x.PROTOCOL), 'selection_sha256': x.digest(selection_path),
              'evaluator_sha256': x.digest(__file__), 'source_run_receipt_sha256': x.digest(source_dir / 'source_receipt.json'),
              'feature_receipt_sha256': x.digest(source_dir / 'feature_receipt.json'),
              'cohort_input_sha256': source_hash, 'period': protocol['new_retrospective_period'],
              'rows': len(frame), 'positive_windows': int(frame[x.b.TARGET].sum()),
              'role_results': role_results, 'paired_uncertainty': intervals,
              'limits': ['Only four calendar days of services; limited positives cannot establish a dependable win.',
                         'Returning customers allowed; historical source revisions cannot all be reconstructed.',
                         'No model reselection, threshold tuning, or October-model replacement from these outcomes.']}
    x.write(out / 'result.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
