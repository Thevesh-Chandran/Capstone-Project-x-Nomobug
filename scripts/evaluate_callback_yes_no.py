"""Evaluate saved forward predictions for all services, with earlier-only calibration."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from scripts import benchmark_warranty_models as b
from scripts import compare_callback_candidates_v2 as c


def main():
    directory = b.ROOT / 'outputs/model_validation/20261016_validated_forward_cv'
    output = directory / 'yes_no_evaluation'
    if output.exists():
        raise ValueError('Preserve completed evidence; output already exists')
    protocol = json.loads((directory / 'protocol.json').read_text(encoding='utf-8'))
    source_path = b.ROOT / protocol['inputs']['features']['path']
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != protocol['inputs']['features']['sha256']:
        raise ValueError('Source changed')
    source = c.prepare_input(b.load_dataset_input(source_path))
    metadata = source[c.KEYS + ['validation_group', 'outcome_end_date']]
    records = {}
    for model in protocol['models']:
        parts = []
        for fold, _, _ in protocol['folds']:
            frame = pd.read_csv(directory / f'{fold}_{model}_predictions_private.csv',
                                dtype={'sales_record_id': str})
            frame.anchor_date = pd.to_datetime(frame.anchor_date)
            frame = frame.merge(metadata, on=c.KEYS, validate='one_to_one')
            frame['fold'] = fold
            parts.append(frame)
        records[model] = pd.concat(parts, ignore_index=True)
    output.mkdir()
    declaration = {'purpose': 'all_service_30_day_yes_no_prediction',
        'calibration': 'positive-slope Platt on earlier 2025 out-of-fold scores only',
        'cutoff': 'maximum calibration F1; highest threshold wins ties',
        'calibration_exclusions': 'all 2026 diagnostic property/package groups and outcomes ending on or after 2026-01-01',
        'reliability_bins': [0, .05, .1, .2, .4, 1],
        'limits': 'Posthoc historical diagnostic; not untouched accuracy or an operational cost-optimal cutoff. No replacement of frozen production settings.'}
    (output / 'evaluation_rule.json').write_text(json.dumps(declaration, indent=2), encoding='utf-8')
    results = []
    for model, frame in records.items():
        test = frame[frame.fold.str.startswith('2026')].copy()
        calibration = frame[frame.fold.isin(protocol['selection_folds'])
            & frame.outcome_end_date.lt('2026-01-01')
            & ~frame.validation_group.isin(set(test.validation_group))].copy()
        if calibration[b.TARGET].nunique() != 2:
            raise ValueError('Both classes required for calibration')
        calibrator, details = b.fit_calibrator(calibration[b.TARGET], calibration.probability)
        calibrated = b.apply_calibrator(calibrator, calibration.probability)
        threshold = b.select_threshold(calibration[b.TARGET], calibrated)
        probability = b.apply_calibrator(calibrator, test.probability)
        y = test[b.TARGET].to_numpy(dtype=bool)
        tn, fp, fn, tp = confusion_matrix(y, probability >= threshold, labels=[False, True]).ravel()
        prior = float(calibration[b.TARGET].mean())
        reliability = []
        edges = declaration['reliability_bins']
        for i, (lo, hi) in enumerate(zip(edges, edges[1:])):
            mask = (probability >= lo) & ((probability <= hi) if i == len(edges)-2 else (probability < hi))
            reliability.append({'lower': lo, 'upper': hi, 'services': int(mask.sum()),
                'mean_probability': float(probability[mask].mean()) if mask.any() else None,
                'observed_return_rate': float(y[mask].mean()) if mask.any() else None})
        result = {'model': model, 'calibration_rows': len(calibration),
            'calibration_positive_windows': int(calibration[b.TARGET].sum()),
            'calibration_details': details, 'threshold': threshold,
            **b.score(y, probability, threshold),
            'true_positives': int(tp), 'false_positives': int(fp),
            'false_negatives': int(fn), 'true_negatives': int(tn),
            'prior_probability_baseline_brier': float(np.mean((y.astype(float)-prior)**2)),
            'mean_predicted_probability': float(probability.mean()), 'reliability': reliability}
        test.assign(calibrated_probability=probability, predicted_return=probability >= threshold).to_csv(
            output / f'{model}_predictions_private.csv', index=False)
        results.append(result)
    (output / 'results.json').write_text(json.dumps({'rule': declaration, 'models': results},
        indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps([{k: r[k] for k in ['model','rows','positives','threshold','accuracy',
        'precision','recall','f1','true_positives','false_positives','false_negatives',
        'brier_score','prior_probability_baseline_brier','calibration_rows']} for r in results], indent=2))


if __name__ == '__main__':
    main()
