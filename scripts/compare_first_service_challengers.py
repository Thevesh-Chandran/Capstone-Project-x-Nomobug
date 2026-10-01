"""Bounded first-service improvement experiment; never changes the live model.

Uses existing dependencies and fixed contracts. Excludes the already consumed
late-August holdout before feature preparation and group reservation. The old
2026 cohort remains an explicitly exploratory diagnostic.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from scripts import benchmark_warranty_models as b
from scripts import compare_callback_candidates_v2 as c
from scripts.compare_callback_blind_spots import folds

PROTOCOL = b.ROOT / 'config/cp2_first_service_challenger_v1.json'
MODEL_NAMES = ('v5_control', 'first_weight4', 'first_weight8', 'stage_reduced')
RESERVES = (0.0, 0.1, 0.25)
STAGE_FIELDS = {
    'service_number', 'package_sessions_recorded', 'days_since_previous_service',
    'days_sale_to_anchor', 'prior_package_warranty_claims', 'prior_package_service_events',
    'anchor_is_first', 'anchor_is_final', 'anchor_is_single_service',
    'anchor_service_progress', 'anchor_remaining_services',
    'prior_package_return_rate_smoothed', 'first_service_prior_property_return_rate',
    'first_service_no_property_history', 'first_service_rain_14d',
}


def allowed_source(source):
    dates = pd.to_datetime(source.anchor_date, errors='raise')
    return source.loc[dates.lt('2026-08-15')].copy()


def feature_columns(name):
    if name not in MODEL_NAMES:
        raise ValueError('Unknown bounded model contract')
    numeric = list(c.feature_sets()['targeted'])
    categorical = list(b.CATEGORICAL)
    if name == 'stage_reduced':
        numeric = [f for f in numeric if f not in STAGE_FIELDS
                   and not f.startswith(('first_pest_', 'final_pest_'))]
        categorical = [f for f in categorical if f != 'package_category']
    return numeric, categorical


def fit_member(name, train):
    numeric, categorical = feature_columns(name)
    pipe = c.make_pipeline('et10_leaf5', numeric)
    # make_pipeline uses the global categorical contract. Replace only the
    # categorical transformer columns for this explicit feature ablation.
    preprocess = pipe.named_steps['preprocess']
    preprocess.transformers = [(n, transformer, categorical if n == 'categorical' else cols)
                               for n, transformer, cols in preprocess.transformers]
    weight = np.ones(len(train))
    factor = {'first_weight4': 4., 'first_weight8': 8.}.get(name, 1.)
    weight[(train.service_number.eq(1) & train[b.TARGET]).to_numpy()] = factor
    with threadpool_limits(limits=2):
        pipe.fit(train[numeric + categorical], train[b.TARGET],
                 classifier__sample_weight=weight)
    return {'pipeline': pipe, 'features': numeric + categorical, 'weight': 1.}


def review_mask(scores, first, reserve=0.0, fraction=0.2):
    """Exact common capacity; stable canonical input order resolves score ties."""
    scores = np.asarray(scores, dtype=float)
    first = np.asarray(first, dtype=bool)
    if not len(scores) or scores.ndim != 1 or first.shape != scores.shape:
        raise ValueError('Aligned nonempty scores and service-stage mask required')
    if not np.isfinite(scores).all() or not 0 < fraction <= 1 or not 0 <= reserve <= 1:
        raise ValueError('Finite scores and bounded review settings required')
    budget = min(len(scores), max(1, int(np.ceil(len(scores) * fraction))))
    order = np.argsort(-scores, kind='stable')
    reserved = min(int(np.ceil(budget * reserve)), int(first.sum()))
    selected = list(order[first[order]][:reserved])
    selected_set = set(selected)
    selected.extend(int(i) for i in order if i not in selected_set)
    mask = np.zeros(len(scores), dtype=bool)
    mask[selected[:budget]] = True
    return mask


def review_metrics(frame, scores, reserve):
    y = frame[b.TARGET].to_numpy(dtype=bool)
    first = frame.service_number.eq(1).to_numpy()
    alert = review_mask(scores, first, reserve)
    result = {}
    for name, group in [('all', np.ones(len(y), dtype=bool)), ('first_service', first)]:
        positives = int(y[group].sum())
        found = int((alert & y & group).sum())
        reviewed = int((alert & group).sum())
        result[name] = {'services': int(group.sum()), 'positives': positives,
                        'reviewed': reviewed, 'found': found,
                        'recall': found / positives if positives else None,
                        'precision': found / reviewed if reviewed else None}
    return result


def select_candidate(candidates):
    control = next(x for x in candidates if x['name'] == 'v5_control__reserve0')
    required = ('mean_ap', 'mean_review_recall', 'mean_first_recall')
    if any(not np.isfinite(x[k]) for x in candidates for k in required):
        raise ValueError('Finite complete development support required')
    eligible = [x for x in candidates
                if x['mean_ap'] >= control['mean_ap'] - 1e-12
                and x['mean_review_recall'] >= control['mean_review_recall'] - 1e-12
                and x['mean_first_recall'] > control['mean_first_recall'] + 1e-12]
    return max(eligible, key=lambda x: (x['mean_first_recall'], x['mean_review_recall'],
                                      x['mean_ap'])) if eligible else control


def predict_artifact(artifact, source):
    frame = c.prepare_input(source, require_outcomes=False)
    raw = c.predict_raw([artifact['member']], frame)
    probability = b.apply_calibrator(artifact['calibrator'], raw)
    return frame[c.KEYS].assign(raw_probability=raw, probability=probability)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path,
                        default=b.ROOT / 'outputs/cp2-v2/first_service_challenger_v1')
    args = parser.parse_args()
    out = args.output_dir
    if out.exists():
        raise ValueError('Preserve experiment evidence; choose a new output directory')
    protocol_bytes = PROTOCOL.read_bytes()
    protocol = json.loads(protocol_bytes)
    source_path = b.ROOT / protocol['source_relative_path']
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != protocol['source_sha256']:
        raise ValueError('Source hash differs from predeclared protocol')
    source = allowed_source(b.load_dataset_input(source_path))
    frame = c.prepare_input(source)
    train, diagnostic, split_audit = c.reserved_split(frame)
    if not train.anchor_date.lt('2026-01-01').all() or not diagnostic.anchor_date.lt('2026-08-15').all():
        raise ValueError('Development/diagnostic dates escaped the contract')
    out.mkdir(parents=True)
    (out / 'protocol.json').write_bytes(protocol_bytes)
    metrics = {f'{name}__reserve{int(reserve * 100)}': []
               for name in MODEL_NAMES for reserve in RESERVES}
    oof = {name: [] for name in MODEL_NAMES}
    support = []
    for fold, past, valid, audit in folds(train):
        first_positives = int(valid.loc[valid.service_number.eq(1), b.TARGET].sum())
        if first_positives == 0:
            raise ValueError('First-service validation support missing')
        support.append({'fold': fold, 'training_services': len(past),
                        'validation_services': len(valid), 'first_positive_windows': first_positives,
                        **audit})
        for name in MODEL_NAMES:
            member = fit_member(name, past)
            raw = c.predict_raw([member], valid)
            ap = b.score(valid[b.TARGET], raw)['average_precision']
            oof[name].append(valid[b.KEYS + ['validation_group']].assign(raw_probability=raw))
            for reserve in RESERVES:
                key = f'{name}__reserve{int(reserve * 100)}'
                metrics[key].append({'fold': fold, 'average_precision': ap,
                                     'review': review_metrics(valid, raw, reserve)})
            print(f'{fold}: {name} fitted; AP={ap:.4f}', flush=True)
    candidates = []
    for name in MODEL_NAMES:
        for reserve in RESERVES:
            key = f'{name}__reserve{int(reserve * 100)}'
            parts = metrics[key]
            candidates.append({'name': key, 'model': name, 'first_review_reserve': reserve,
                               'mean_ap': float(np.mean([x['average_precision'] for x in parts])),
                               'mean_review_recall': float(np.mean([x['review']['all']['recall'] for x in parts])),
                               'mean_first_recall': float(np.mean([x['review']['first_service']['recall'] for x in parts])),
                               'folds': parts})
    selected = select_candidate(candidates)
    declaration = {'created_at_utc': datetime.now(timezone.utc).isoformat(),
                   'protocol_sha256': hashlib.sha256(protocol_bytes).hexdigest(),
                   'split_audit': split_audit, 'fold_support': support,
                   'candidates': candidates, 'selected': selected,
                   'selection_before_diagnostic_scoring': True}
    selection_path = out / 'development_selection.json'
    selection_path.write_text(json.dumps(declaration, indent=2), encoding='utf-8')
    diagnostic_results = {}
    for role, candidate in [('control', candidates[0]), ('challenger', selected)]:
        role_dir = out / role
        role_dir.mkdir()
        pooled = pd.concat(oof[candidate['model']], ignore_index=True)
        calibrator, calibration = b.fit_calibrator(pooled[b.TARGET], pooled.raw_probability)
        artifact = {'member': fit_member(candidate['model'], train), 'calibrator': calibrator,
                    'calibration': calibration, 'selected': candidate,
                    'training_services': len(train), 'training_positives': int(train[b.TARGET].sum()),
                    'purpose': 'exploratory_old2026_diagnostic_not_for_cloud_deployment',
                    'protocol_sha256': declaration['protocol_sha256'],
                    'source_sha256': protocol['source_sha256']}
        model_path = role_dir / 'model.joblib'
        joblib.dump(artifact, model_path)
        raw = c.predict_raw([artifact['member']], diagnostic)
        probability = b.apply_calibrator(calibrator, raw)
        predictor_only = source.drop(columns=[b.TARGET], errors='ignore')
        predictor_only = predictor_only.loc[pd.to_datetime(predictor_only.anchor_date).ge('2026-01-01')]
        replay = predict_artifact(joblib.load(model_path), predictor_only)
        if not np.allclose(probability, replay.probability, atol=1e-12, rtol=0):
            raise ValueError('Serialized predictor-only replay differs')
        private = diagnostic[c.KEYS + [b.TARGET]].assign(probability=probability,
                    reviewed=review_mask(raw, diagnostic.service_number.eq(1), candidate['first_review_reserve']))
        private.to_csv(role_dir / 'diagnostic_predictions_private.csv', index=False)
        diagnostic_results[role] = {'contract': candidate['name'],
                                    **b.score(diagnostic[b.TARGET], probability),
                                    'review': review_metrics(diagnostic, raw, candidate['first_review_reserve']),
                                    'artifact_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
                                    'replay_max_difference': float(np.max(np.abs(probability - replay.probability)))}
    result = {'status': 'exploratory_only_frozen_cloud_model_unchanged',
              'source_sha256': protocol['source_sha256'],
              'protocol_sha256': declaration['protocol_sha256'],
              'selection_sha256': hashlib.sha256(selection_path.read_bytes()).hexdigest(),
              'selection': selected, 'development': candidates, 'fold_support': support,
              'development_services': len(train), 'diagnostic_services': len(diagnostic),
              'diagnostic_positives': int(diagnostic[b.TARGET].sum()),
              'diagnostic': diagnostic_results, 'limits': protocol['limits']}
    (out / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'selected': selected['name'], 'diagnostic': diagnostic_results}, indent=2))


if __name__ == '__main__':
    main()
