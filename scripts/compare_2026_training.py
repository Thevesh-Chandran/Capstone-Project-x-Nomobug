"""Exploratory early-2026 training comparison on a frozen later-2026 cohort."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

try:
    from scripts import benchmark_warranty_models as b
    from scripts.compare_flood_models import configure_contracts, paired_bootstrap
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    from compare_flood_models import configure_contracts, paired_bootstrap

FINAL_START = '2026-07-01'
RECENT_START = '2026-01-01'
FOLDS = [('march', '2026-03-01', '2026-04-01'),
         ('april', '2026-04-01', '2026-05-01'),
         ('may', '2026-05-01', '2026-06-01')]
MODELS = ['extra_trees_depth6', 'rf_depth3', 'rf_depth6',
          'catboost_depth4_plain', 'lr_c1.0_plain']
SETS = ['compact_history', 'base', 'base_weather_environment']
ROOT = b.ROOT


def partitions(frame, recent_only):
    """Reserve later groups globally before selection, calibration and fitting."""
    train, test, audit = b.purged_split(frame, FINAL_START)
    if recent_only:
        train = train[train.anchor_date.ge(RECENT_START)].copy()
    assert train.outcome_end_date.lt(FINAL_START).all()
    b.assert_package_property_disjoint(train, test)
    return train, test, audit


def development_splits(train):
    result = []
    for name, start, end in FOLDS:
        past, validation, audit = b.purged_split(train, start, end)
        if (len(past) < 30 or len(validation) < 15
                or past[b.TARGET].nunique() < 2
                or min(validation[b.TARGET].sum(), (~validation[b.TARGET]).sum()) < 3):
            raise ValueError(f'Insufficient development support: {name}')
        result.append((name, past, validation, audit))
    return result


def evaluate_candidates(train, directory):
    splits = development_splits(train)
    candidates, predictions = [], {}
    for feature_set in SETS:
        numeric = b.FEATURE_SETS[feature_set]
        features = numeric + b.CATEGORICAL
        for model in MODELS:
            parts, metrics = [], []
            for name, past, validation, audit in splits:
                fitted = b.make_model(model, numeric).fit(past[features], past[b.TARGET])
                p = validation[b.KEYS + ['validation_group']].copy()
                p['raw_probability'] = fitted.predict_proba(validation[features])[:, 1]
                p['fold'] = name
                parts.append(p)
                metrics.append({'fold': name, 'training_rows': len(past), **audit,
                                **b.score(p[b.TARGET], p.raw_probability)})
            candidate = {'feature_set': feature_set, 'model': model,
                         'mean_average_precision': float(np.mean([m['average_precision'] for m in metrics])),
                         'mean_roc_auc': float(np.mean([m['roc_auc'] for m in metrics])),
                         'folds': metrics}
            candidates.append(candidate)
            predictions[(feature_set, model)] = pd.concat(parts, ignore_index=True)
            print(f'{directory.name} {feature_set} {model}: development AP {candidate["mean_average_precision"]:.4f}', flush=True)
    winner = max(candidates, key=lambda c: (c['mean_average_precision'], c['mean_roc_auc']))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'development_candidates.json').write_text(json.dumps(candidates, indent=2))
    return winner, candidates, predictions


def fit_variant(train, test, selection, oof, output, name):
    numeric = b.FEATURE_SETS[selection['feature_set']]
    features = numeric + b.CATEGORICAL
    calibrator, calibration = b.fit_calibrator(oof[b.TARGET], oof.raw_probability)
    if calibration['applied']:
        calibration['method'] = 'platt_on_march_to_may2026_purged_oof'
    calibration['outcomes_known_before'] = FINAL_START
    oof = oof.copy()
    oof['probability'] = b.apply_calibrator(calibrator, oof.raw_probability)
    threshold = b.select_threshold(oof[b.TARGET], oof.probability)
    fitted = b.make_model(selection['model'], numeric).fit(train[features], train[b.TARGET])
    artifact = {'pipeline': fitted, 'features': features, 'calibrator': calibrator,
                'threshold': threshold, 'population': str(train.population.iloc[0]),
                'feature_preparation_options': b.feature_preparation_options(),
                'training_outcome_end_exclusive': FINAL_START,
                'purpose': 'exploratory_diagnostic_not_deployment'}
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output / 'selected_model.joblib')
    oof.to_csv(output / 'development_predictions.csv', index=False)
    return score_artifact(artifact, test, output, name, selection, len(train), int(train[b.TARGET].sum()), calibration)


def score_artifact(artifact, test, output, name, selection, train_rows, train_positive, calibration):
    predictions = test[b.KEYS + ['validation_group']].copy()
    predictions['raw_probability'] = artifact['pipeline'].predict_proba(test[artifact['features']])[:, 1]
    predictions['probability'] = b.apply_calibrator(artifact['calibrator'], predictions.raw_probability)
    predictions['threshold'] = artifact['threshold']
    output.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output / 'diagnostic_predictions.csv', index=False)
    return {'variant': name, 'training_rows': train_rows, 'training_positive_rows': train_positive,
            'selection': selection, 'selected_features': artifact['features'],
            'feature_preparation_options': artifact['feature_preparation_options'],
            'calibration': calibration, 'diagnostic': b.score(test[b.TARGET], predictions.probability, artifact['threshold']),
            'priority_top20pct': b.priority_review_metrics(test[b.TARGET], predictions.probability)}


def verify_artifact(input_path, artifact_path, prediction_path):
    configure_contracts(False)
    frame = b.prepare_frame(b.load_dataset_input(input_path))
    _, test, _ = partitions(frame, False)
    artifact = joblib.load(artifact_path)
    expected = pd.read_csv(prediction_path, dtype={'sales_record_id': str})
    assert test.sales_record_id.astype(str).tolist() == expected.sales_record_id.tolist()
    assert test.anchor_date.dt.strftime('%Y-%m-%d').tolist() == expected.anchor_date.tolist()
    raw = artifact['pipeline'].predict_proba(test[artifact['features']])[:, 1]
    probability = b.apply_calibrator(artifact['calibrator'], raw)
    np.testing.assert_allclose(raw, expected.raw_probability, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(probability, expected.probability, rtol=1e-12, atol=1e-12)
    assert np.isfinite(probability).all() and ((probability >= 0) & (probability <= 1)).all()
    return {'rows': len(test), 'passed': True, 'max_difference': float(np.max(abs(probability-expected.probability)))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-json', type=Path, default=ROOT/'outputs/cp2-v2/model_callback_normalized_pest/dataset_input.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'outputs/cp2-v2/training_2026_comparison')
    parser.add_argument('--verify-artifact', type=Path)
    parser.add_argument('--predictions', type=Path)
    args = parser.parse_args()
    if args.verify_artifact:
        print(json.dumps(verify_artifact(args.input_json, args.verify_artifact, args.predictions)))
        return
    configure_contracts(False)
    raw = b.load_dataset_input(args.input_json)
    digest = b.persist_dataset_input(raw, args.output_dir)
    frame = b.prepare_frame(raw)
    all_train, test, audit = partitions(frame, False)
    recent_train, recent_test, _ = partitions(frame, True)
    assert test[b.KEYS].equals(recent_test[b.KEYS])
    cfg = json.loads((ROOT/'config/warranty_model_experiment_v4.json').read_text())
    original = next(m for m in cfg['models'] if m['population'] == str(frame.population.iloc[0]))
    if digest != original['dataset_input_sha256']:
        raise ValueError('Frozen reference model and comparison source differ')
    frozen_artifact = joblib.load(original['model_artifact'])
    frozen_train, _, _ = b.purged_split(frame, '2026-01-01')
    b.assert_package_property_disjoint(frozen_train, test)
    historical_oof = pd.read_csv(Path(original['model_artifact']).parent /
        f"{frame.population.iloc[0]}_selected_development_predictions.csv")
    shared_oof = historical_oof.validation_group.isin(test.validation_group)
    output = args.output_dir/'frozen_v4'
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(frozen_artifact, output/'selected_model.joblib')
    results = {'frozen_v4': score_artifact(frozen_artifact, test, output, 'frozen_v4', original['selection'],
                                        len(frozen_train), int(frozen_train[b.TARGET].sum()), original['calibration'])}
    for regime, train in [('all_history', all_train), ('2026_only', recent_train)]:
        winner, candidates, oof = evaluate_candidates(train, args.output_dir/regime)
        locked = next(c for c in candidates if c['model']=='extra_trees_depth6' and c['feature_set']=='base_weather_environment')
        for kind, selection in [('locked', locked), ('selected', winner)]:
            name = regime+'_'+kind
            results[name] = fit_variant(train, test, selection,
                                       oof[(selection['feature_set'], selection['model'])], args.output_dir/name, name)
    baseline = pd.read_csv(args.output_dir/'frozen_v4/diagnostic_predictions.csv')
    bootstraps = {}
    for name in results:
        if name != 'frozen_v4':
            other = pd.read_csv(args.output_dir/name/'diagnostic_predictions.csv')
            bootstraps[name] = paired_bootstrap(baseline, other, repeats=200)
            bootstraps[name]['direction'] = name+'_minus_frozen_v4'
    later = pd.read_csv(args.output_dir/'2026_only_locked/diagnostic_predictions.csv')
    earlier = pd.read_csv(args.output_dir/'all_history_locked/diagnostic_predictions.csv')
    bootstraps['2026_only_minus_all_history_locked'] = paired_bootstrap(earlier, later, repeats=200)
    bootstraps['2026_only_minus_all_history_locked']['direction'] = '2026_only_locked_minus_all_history_locked'
    report = {'dataset_input_sha256': digest, 'target': 'recorded_corrective_callback_within_30d',
              'reporting_caveat': '2026 previously inspected; exploratory, not an independent final test',
              'final_start': FINAL_START, 'final_end_inclusive': str(test.anchor_date.max().date()),
              'development_windows': FOLDS, 'all_development_outcomes_before_final_cutoff': True,
              'final_groups_excluded_before_selection_and_calibration': True,
              'final_group_exclusion_applies_to': 'both_updated_regimes_not_original_frozen_development',
              'frozen_reference_final_fit_disjoint': True,
              'frozen_reference_historical_development_overlap_rows': int(shared_oof.sum()),
              'frozen_reference_historical_development_overlap_components': int(historical_oof.loc[shared_oof,'validation_group'].nunique()),
              'recent_training_means_anchor_2026_not_erased_historical_predictors': True,
              'candidate_evaluations': 30, 'split_audit': audit,
              'test_keys_sha256': hashlib.sha256(test[b.KEYS].to_json(orient='records',date_format='iso').encode()).hexdigest(),
              'results': results, 'paired_cluster_bootstraps': bootstraps}
    (args.output_dir/'comparison_results.json').write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({name: {'selection':v['selection'], 'diagnostic':v['diagnostic'],
                            'priority':v['priority_top20pct']} for name,v in results.items()}, indent=2))


if __name__ == '__main__':
    main()
