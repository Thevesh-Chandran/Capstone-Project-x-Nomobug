"""Bounded callback candidates selected only using purged pre-2026 folds.

Previously inspected 2026 predictions are diagnostic. All-history artifacts
are refits for later evaluation and carry no training accuracy claim.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import monotonic

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

try:
    from scripts import benchmark_warranty_models as b
    from scripts.compare_flood_models import configure_contracts
    from scripts.compare_callback_blind_spots import (
        TARGETED_NUMERIC, add_targeted_features, training_weights,
        segment_metrics, folds,
    )
    from scripts.callback_evaluation import paired_intervals
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    from compare_flood_models import configure_contracts
    from compare_callback_blind_spots import (
        TARGETED_NUMERIC, add_targeted_features, training_weights,
        segment_metrics, folds,
    )
    from callback_evaluation import paired_intervals

KEYS = ['population', 'sales_record_id', 'anchor_date']
SPECS = {
    'reference_et6': {'model': 'extra_trees_depth6', 'feature_set': 'base', 'policy': 'standard'},
    'focus_rf6': {'model': 'rf_depth6', 'feature_set': 'targeted', 'policy': 'focus_positive_2x'},
    'et10_leaf5': {'model': 'et10_leaf5', 'feature_set': 'targeted', 'policy': 'standard'},
    'rf10_leaf5': {'model': 'rf10_leaf5', 'feature_set': 'targeted', 'policy': 'standard'},
    'rf6_leaf20': {'model': 'rf6_leaf20', 'feature_set': 'targeted', 'policy': 'focus_positive_2x'},
    'hist3_balanced': {'model': 'hist3_balanced', 'feature_set': 'targeted', 'policy': 'standard'},
    'cat4_plain': {'model': 'cat4_plain', 'feature_set': 'targeted', 'policy': 'standard'},
    'cat6_plain': {'model': 'cat6_plain', 'feature_set': 'targeted', 'policy': 'standard'},
    'cat4_balanced': {'model': 'cat4_balanced', 'feature_set': 'targeted', 'policy': 'standard'},
    'cat6_balanced': {'model': 'cat6_balanced', 'feature_set': 'targeted', 'policy': 'standard'},
    'targeted_et6': {'model': 'extra_trees_depth6', 'feature_set': 'targeted', 'policy': 'standard'},
    'policy_et6': {'model': 'extra_trees_depth6', 'feature_set': 'targeted_policy', 'policy': 'standard'},
}
ENSEMBLES = {
    'blend_et_rf': [('reference_et6', .5), ('focus_rf6', .5)],
    'blend_et_cat': [('reference_et6', .5), ('cat4_balanced', .5)],
}


def feature_sets():
    base = list(b.FEATURE_SETS['base_weather_environment'])
    return {'base': base, 'targeted': base + TARGETED_NUMERIC,
            'targeted_policy': base + TARGETED_NUMERIC + ['contract_eligible_at_paid_anchor']}


def add_contract_policy_feature(frame):
    """Encode the owner's warranty rules at this paid anchor, independent of pest.

    This predictor is not an entitlement decision and never suppresses a
    commercial corrective callback. Package counts outside the named policy
    cannot be treated as recognized eligible contracts by this flag.
    """
    frame = frame.copy()
    residential = frame.premise_type.astype('string').str.strip().str.upper().eq('RESIDENTIAL')
    three_final = frame.package_sessions_recorded.eq(3) & frame.service_number.eq(3)
    annual = frame.package_sessions_recorded.isin([4, 6, 12])
    frame['contract_eligible_at_paid_anchor'] = (residential & (three_final | annual)).astype(float)
    return frame


def make_pipeline(name, numeric):
    if name in ['extra_trees_depth6', 'rf_depth6']:
        return b.make_model(name, numeric)
    if name.startswith('cat'):
        depth = int(name[3])
        balanced = name.endswith('balanced')
        pipe = b.make_model(f'catboost_depth{depth}_' + ('balanced' if balanced else 'plain'), numeric)
        pipe.named_steps['classifier'].set_params(
            iterations=500 if depth == 4 else 450,
            l2_leaf_reg=20 if depth == 4 else 30, learning_rate=.035)
        return pipe
    pipe = b.make_model('extra_trees_depth6', numeric)
    if name == 'et10_leaf5':
        classifier = ExtraTreesClassifier(n_estimators=300, max_depth=10,
            min_samples_leaf=5, class_weight='balanced', random_state=42, n_jobs=2)
    elif name in ['rf10_leaf5', 'rf6_leaf20']:
        classifier = RandomForestClassifier(n_estimators=300,
            max_depth=10 if name == 'rf10_leaf5' else 6,
            min_samples_leaf=5 if name == 'rf10_leaf5' else 20,
            class_weight='balanced_subsample', random_state=42, n_jobs=2)
    elif name == 'hist3_balanced':
        classifier = HistGradientBoostingClassifier(max_depth=3, max_iter=250,
            min_samples_leaf=30, learning_rate=.04, l2_regularization=10,
            class_weight='balanced', random_state=42)
    else:
        raise ValueError(f'Unknown bounded candidate: {name}')
    pipe.set_params(classifier=classifier)
    return pipe


def fit_member(name, train, contracts):
    spec = SPECS[name]
    numeric = contracts[spec['feature_set']]
    features = numeric + list(b.CATEGORICAL)
    pipe = make_pipeline(spec['model'], numeric)
    if 'n_jobs' in pipe.named_steps['classifier'].get_params():
        pipe.named_steps['classifier'].set_params(n_jobs=2)
    with threadpool_limits(limits=2):
        pipe.fit(train[features], train[b.TARGET],
                 classifier__sample_weight=training_weights(train, spec['policy']))
    return {'pipeline': pipe, 'features': features, 'member_name': name}


def mixture_members(name):
    return ENSEMBLES[name] if name in ENSEMBLES else [(name, 1.)]


def predict_raw(members, frame):
    weights = np.array([member['weight'] for member in members], dtype=float)
    if not len(weights) or not np.isfinite(weights).all() or (weights <= 0).any() or not np.isclose(weights.sum(), 1.):
        raise ValueError('Ensemble weights must be positive and sum to one')
    predictions = []
    for member in members:
        missing = set(member['features']) - set(frame)
        if missing:
            raise ValueError(f'Scoring data misses features: {sorted(missing)}')
        p = member['pipeline'].predict_proba(frame[member['features']])[:, 1]
        if len(p) != len(frame) or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
            raise ValueError('Invalid member probabilities')
        predictions.append(p)
    return np.average(np.asarray(predictions), axis=0, weights=weights)


def reserved_split(frame):
    train, diagnostic, audit = b.purged_split(frame, b.REPORTING_START)
    if train.empty or diagnostic.empty:
        raise ValueError('Both mature historical training and reserved 2026 are required')
    return train, diagnostic, audit


def development_metrics(frame, raw, name, audit, train):
    segments = segment_metrics(frame, raw, .5)
    return {'fold': name, 'training_rows': len(train),
            'training_positive_rows': int(train[b.TARGET].sum()), **audit,
            **b.score(frame[b.TARGET], raw), 'segments': segments,
            'priority_top20pct': b.priority_review_metrics(frame[b.TARGET], raw)}


def evaluate_development(train, contracts):
    metrics = {name: [] for name in [*SPECS, *ENSEMBLES]}
    predictions = {name: [] for name in metrics}
    for fold_name, past, valid, audit in folds(train):
        fitted = {}
        for name in SPECS:
            started = monotonic()
            fitted[name] = fit_member(name, past, contracts)
            print(f'{fold_name} fitted {name} in {monotonic() - started:.1f}s', flush=True)
        for name in metrics:
            members = [fitted[member] | {'weight': weight}
                       for member, weight in mixture_members(name)]
            raw = predict_raw(members, valid)
            metrics[name].append(development_metrics(valid, raw, fold_name, audit, past))
            predictions[name].append(valid[b.KEYS + ['validation_group']].assign(
                raw_probability=raw, fold=fold_name))
        print(f'Completed purged development fold {fold_name}: {len(past)} training, {len(valid)} validation', flush=True)
    candidates = []
    for name, metric in metrics.items():
        candidate = {'name': name, 'members': mixture_members(name), 'folds': metric,
            'mean_ap': float(np.mean([m['average_precision'] for m in metric])),
            'mean_auc': float(np.mean([m['roc_auc'] for m in metric])),
            'mean_budget_recall': float(np.mean([m['segments']['all']['budget_recall'] for m in metric])),
            'mean_target_union_budget_recall': float(np.mean([m['segments']['target_union']['budget_recall'] for m in metric]))}
        candidates.append(candidate)
        print(f'{name}: development AP={candidate["mean_ap"]:.4f}, review recall={candidate["mean_budget_recall"]:.4f}', flush=True)
    return candidates, {name: pd.concat(parts, ignore_index=True) for name, parts in predictions.items()}


def select_candidates(candidates):
    if not candidates or any(not all(np.isfinite(c[key]) for key in
        ['mean_ap', 'mean_auc', 'mean_budget_recall', 'mean_target_union_budget_recall']) for c in candidates):
        raise ValueError('Complete finite development metrics required')
    reference = next(c for c in candidates if c['name'] == 'reference_et6')
    strongest_ap = max(candidates, key=lambda c: (c['mean_ap'], c['mean_budget_recall'], c['mean_auc']))
    eligible = [c for c in candidates if c['mean_ap'] >= reference['mean_ap'] - 1e-12]
    priority = max(eligible, key=lambda c: (c['mean_budget_recall'], c['mean_ap'], c['mean_auc']))
    return {'reference': reference, 'selected_ap': strongest_ap, 'selected_priority': priority}


def fit_artifact(selection, train, contracts, oof, input_hash, purpose):
    calibrator, calibration = b.fit_calibrator(oof[b.TARGET], oof.raw_probability)
    calibrated = b.apply_calibrator(calibrator, oof.raw_probability)
    threshold = b.select_threshold(oof[b.TARGET], calibrated)
    members = [fit_member(name, train, contracts) | {'weight': weight}
               for name, weight in selection['members']]
    return {'artifact_schema_version': 1, 'members': members, 'calibrator': calibrator,
            'threshold': threshold, 'selection': selection, 'calibration': calibration,
            'input_file_sha256': input_hash, 'training_rows': len(train),
            'training_positive_rows': int(train[b.TARGET].sum()),
            'training_max_anchor_date': str(train.anchor_date.max().date()),
            'training_max_outcome_end_date': str(train.outcome_end_date.max().date()),
            'feature_preparation_options': b.feature_preparation_options(),
            'feature_preparation': 'compare_callback_candidates_v2.prepare_input',
            'purpose': purpose,
            'target': 'recorded_corrective_calendar_callback_within_30d',
            'numeric_feature_sets': contracts, 'categorical_features': list(b.CATEGORICAL),
            'created_at': datetime.now(timezone.utc).isoformat()}


def prepare_input(source, require_outcomes=True):
    configure_contracts(False)
    return add_contract_policy_feature(add_targeted_features(
        b.prepare_frame(source, require_outcomes=require_outcomes)))


def predict_artifact(artifact, source):
    frame = prepare_input(source, require_outcomes=False)
    raw = predict_raw(artifact['members'], frame)
    probability = b.apply_calibrator(artifact['calibrator'], raw)
    return frame[KEYS].assign(raw_probability=raw, probability=probability,
                              threshold=artifact['threshold'])


def ensure_mature(frame, as_of):
    if (frame.outcome_end_date >= pd.Timestamp(as_of)).any():
        raise ValueError('All-history refit requires completed outcomes before refit date')


def historical_training(frame, outcomes_before):
    """Keep only labels that were fully known before the first holdout anchor."""
    cutoff = pd.Timestamp(outcomes_before)
    train = frame[frame.outcome_end_date.lt(cutoff)].copy()
    if train.empty or train[b.TARGET].nunique() != 2:
        raise ValueError('Historical fitting requires mature examples from both classes')
    return train


def verify_model(model_path, input_path):
    artifact = joblib.load(model_path)
    if artifact['input_file_sha256'] != hashlib.sha256(input_path.read_bytes()).hexdigest():
        raise ValueError('Frozen replay source changed')
    expected = pd.read_csv(model_path.parent / 'diagnostic_predictions.csv', dtype={'sales_record_id': str})
    expected.anchor_date = pd.to_datetime(expected.anchor_date)
    input_frame = b.load_dataset_input(input_path)
    source = input_frame[pd.to_datetime(input_frame.anchor_date) >= b.REPORTING_START]
    predicted = predict_artifact(artifact, source)
    joined = expected.merge(predicted, on=KEYS, how='outer', validate='one_to_one',
        indicator=True, suffixes=('_saved', '_replayed'))
    if not joined['_merge'].eq('both').all() or not np.allclose(joined.probability_saved,
            joined.probability_replayed, rtol=0, atol=1e-12):
        raise ValueError('Scoring artifact replay differs')
    return {'rows': len(joined), 'maximum_probability_difference': float(abs(
        joined.probability_saved - joined.probability_replayed).max())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-json', type=Path, default=b.ROOT / 'outputs/cp2-v2/model_callback_normalized_pest/dataset_input.json')
    p.add_argument('--output-dir', type=Path, default=b.ROOT / 'outputs/cp2-v2/candidate_comparison_v2')
    p.add_argument('--verify-model', type=Path)
    p.add_argument('--score-model', type=Path)
    p.add_argument('--score-json', type=Path)
    p.add_argument('--score-output', type=Path)
    p.add_argument('--historical-fit-before', help='Optional additional artifacts: outcomes must end strictly before this holdout start date')
    args = p.parse_args()
    if args.verify_model:
        print(json.dumps(verify_model(args.verify_model, args.input_json))); return
    if args.score_model:
        if not args.score_json or not args.score_output:
            raise ValueError('Scoring requires predictor JSON input and private output path')
        artifact = joblib.load(args.score_model)
        predictions = predict_artifact(artifact, b.load_dataset_input(args.score_json))
        args.score_output.parent.mkdir(parents=True, exist_ok=True)
        predictions.to_csv(args.score_output, index=False)
        print(json.dumps({'scored_rows': len(predictions), 'labels_read': False})); return
    if (args.output_dir / 'candidate_results.json').exists():
        raise ValueError('Completed experiment exists; preserve frozen evidence and use a new output directory')
    frame = prepare_input(b.load_dataset_input(args.input_json))
    train, diagnostic, audit = reserved_split(frame)
    contracts = feature_sets()
    digest = hashlib.sha256(args.input_json.read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates, oof = evaluate_development(train, contracts)
    # Persist selections before any diagnostic predictions are produced.
    selections = select_candidates(candidates)
    (args.output_dir / 'development_selection.json').write_text(json.dumps(
        {'candidates': candidates, 'selections': selections}, indent=2, allow_nan=False), encoding='utf-8')
    results = {}; diagnostic_predictions = {}
    mature_as_of = datetime.now(timezone.utc).astimezone().date()
    ensure_mature(frame, mature_as_of)
    historical = historical_training(frame, args.historical_fit_before) if args.historical_fit_before else None
    for role, selection in selections.items():
        directory = args.output_dir / role
        directory.mkdir(exist_ok=True)
        artifact = fit_artifact(selection, train, contracts, oof[selection['name']], digest,
                                'historical_diagnostic_not_deployment')
        raw = predict_raw(artifact['members'], diagnostic)
        probability = b.apply_calibrator(artifact['calibrator'], raw)
        predicted = diagnostic[b.KEYS + ['validation_group']].assign(
            raw_probability=raw, probability=probability, threshold=artifact['threshold'])
        diagnostic_predictions[role] = predicted
        predicted.to_csv(directory / 'diagnostic_predictions.csv', index=False)
        oof[selection['name']].to_csv(directory / 'development_predictions.csv', index=False)
        joblib.dump(artifact, directory / 'diagnostic_model.joblib')
        all_history = fit_artifact(selection, frame, contracts, oof[selection['name']], digest,
                                  'all_mature_refit_for_new_unseen_evaluation_not_deployment')
        joblib.dump(all_history, directory / 'all_mature_model.joblib')
        if historical is not None:
            historical_artifact = fit_artifact(selection, historical, contracts, oof[selection['name']], digest,
                'mature_before_later_historical_holdout_not_deployment')
            historical_artifact['training_outcome_end_exclusive'] = args.historical_fit_before
            joblib.dump(historical_artifact, directory / 'historical_model.joblib')
        results[role] = {'selection_name': selection['name'], 'threshold': artifact['threshold'],
            'calibration': artifact['calibration'],
            'diagnostic': b.score(diagnostic[b.TARGET], probability, artifact['threshold']),
            'priority_top20pct': b.priority_review_metrics(diagnostic[b.TARGET], probability),
            'segments': segment_metrics(diagnostic, probability, artifact['threshold']),
            'all_mature_training_rows': len(frame), 'all_mature_training_positive_rows': int(frame[b.TARGET].sum()),
            'diagnostic_model_sha256': hashlib.sha256((directory / 'diagnostic_model.joblib').read_bytes()).hexdigest(),
            'all_mature_model_sha256': hashlib.sha256((directory / 'all_mature_model.joblib').read_bytes()).hexdigest()}
        if historical is not None:
            results[role]['historical_fit'] = {
                'outcome_end_exclusive': args.historical_fit_before, 'training_rows': len(historical),
                'training_positive_rows': int(historical[b.TARGET].sum()),
                'max_anchor_date': str(historical.anchor_date.max().date()),
                'max_outcome_end_date': str(historical.outcome_end_date.max().date()),
                'artifact_sha256': hashlib.sha256((directory / 'historical_model.joblib').read_bytes()).hexdigest()}
    intervals = {role: paired_intervals(diagnostic, diagnostic_predictions['reference'], prediction)
                 for role, prediction in diagnostic_predictions.items() if role != 'reference'}
    report = {'status': 'experimental_not_deployment', 'input_file_sha256': digest,
        'target': 'recorded_corrective_calendar_callback_within_30d',
        'original_rows': len(frame), 'training_rows': len(train),
        'training_positive_rows': int(train[b.TARGET].sum()), 'diagnostic_rows': len(diagnostic),
        'diagnostic_positive_rows': int(diagnostic[b.TARGET].sum()), 'split_audit': audit,
        'all_2026_groups_excluded_before_development_selection': True,
        'selection_rules': {'selected_ap': 'maximum mean 2025 AP; mean review recall then AUC tie breaks',
            'selected_priority': 'maximum mean 2025 global20 review recall with AP at least reference'},
        'bounded_single_models': SPECS, 'fixed_ensembles': ENSEMBLES,
        'candidates': candidates, 'results': results, 'paired_diagnostic_intervals': intervals,
        'diagnostic_caveat': '2026 previously inspected and features motivated by its errors; not fresh accuracy',
        'all_mature_caveat': 'all mature training outcomes used only after development selection; no training performance claim',
        'feature_preparation_source_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest()
             for name, path in {'benchmark': Path(b.__file__), 'comparison': Path(__file__),
                'targeted_features': Path(add_targeted_features.__code__.co_filename),
                'aligned_evaluation': Path(paired_intervals.__code__.co_filename)}.items()}}
    (args.output_dir / 'candidate_results.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'selections': {role: selection['name'] for role, selection in selections.items()},
                      'diagnostic': results}, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
