"""Fixed exploratory model search; preserve v5 and reserve later-period outcomes."""
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

from scripts import benchmark_warranty_models as b
from scripts import compare_callback_candidates_v2 as c
from scripts import compare_first_service_challengers as first
from scripts.compare_callback_blind_spots import folds

PROTOCOL = b.ROOT / 'config/cp2_broad_challenger_v1.json'
ENGINEERED = ['area_return_rate_smoothed', 'log_property_services', 'log_package_services',
              'log_area_services_90d', 'property_claim_recency_30d', 'rain_per_wet_day_14d',
              'recent_rain_share_30d', 'humidity_change_7_vs_30d', 'soil_change_7_vs_30d',
              'temperature_change_7_vs_30d', 'gap_rain_interaction', 'first_property_claim_recency']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False), encoding='utf-8')


def add_features(frame):
    f = frame.copy()
    f['area_return_rate_smoothed'] = (f.prior_area_claims_90d + 1) / (f.prior_area_services_90d + 10)
    for output, source in [('log_property_services', 'prior_property_service_events'),
                           ('log_package_services', 'prior_package_service_events'),
                           ('log_area_services_90d', 'prior_area_services_90d')]:
        f[output] = np.log1p(f[source].clip(lower=0))
    f['property_claim_recency_30d'] = np.exp(-f.days_since_prior_property_claim.clip(lower=0) / 30)
    # Undefined denominators remain missing; no fabricated dry-day or rain measurements.
    f['rain_per_wet_day_14d'] = f.prior_14d_precipitation_mm / f.prior_14d_wet_days_1mm.replace(0, np.nan)
    f['recent_rain_share_30d'] = f.prior_7d_precipitation_mm / f.prior_30d_precipitation_mm.replace(0, np.nan)
    f['humidity_change_7_vs_30d'] = f.prior_7d_relative_humidity_mean_pct - f.prior_30d_relative_humidity_mean_pct
    f['soil_change_7_vs_30d'] = f.prior_7d_soil_moisture_0_to_7cm_mean - f.prior_30d_soil_moisture_0_to_7cm_mean
    f['temperature_change_7_vs_30d'] = f.prior_7d_temperature_mean_c - f.prior_30d_temperature_mean_c
    f['gap_rain_interaction'] = f.days_since_previous_service.clip(0, 365) * f.prior_7d_precipitation_mm
    f['first_property_claim_recency'] = f.anchor_is_first * f.property_claim_recency_30d
    f[ENGINEERED] = f[ENGINEERED].replace([np.inf, -np.inf], np.nan)
    return f


def prepare(source, require_outcomes=True):
    return add_features(c.prepare_input(source, require_outcomes=require_outcomes))


def numeric_contract(name):
    targeted = c.feature_sets()['targeted']
    remove = set(b.ENVIRONMENT_NUMERIC + b.DERIVED_NUMERIC)
    weather_interactions = {'mixed_pest_rain_14d', 'first_service_rain_14d'}
    mapping = {'targeted': targeted, 'engineered': targeted + ENGINEERED,
               'policy': targeted + ['contract_eligible_at_paid_anchor'],
               'landcover': targeted + b.LANDCOVER_NUMERIC,
               'no_environment': [k for k in targeted if k not in remove],
               'history_only': [k for k in targeted if k not in remove | set(b.WEATHER_NUMERIC) | weather_interactions]}
    if name not in mapping:
        raise ValueError('Unknown predeclared feature contract')
    result = mapping[name]
    if len(result) != len(set(result)) or set(result) & {b.TARGET, *c.KEYS, 'address_hash'}:
        raise ValueError('Duplicated or forbidden predictor')
    return result


def pipeline(spec):
    numeric = numeric_contract(spec['features'])
    family = spec['family']
    if family == 'control':
        return c.make_pipeline('et10_leaf5', numeric)
    if family == 'lr':
        return b.make_model(spec['model'], numeric)
    if family == 'cat':
        pipe = b.make_model('catboost_depth3_plain', numeric)
        # CatBoost omits None constructor options but set_params(None) sends
        # JSON null to its native parser. Plain class weighting is the default.
        pipe.named_steps['classifier'].set_params(**{k: v for k, v in spec['params'].items() if v is not None})
        return pipe
    pipe = b.make_model('extra_trees_depth6', numeric)
    if family in {'et', 'stage_expert'}:
        cls = ExtraTreesClassifier(n_estimators=300, class_weight='balanced',
                                   random_state=42, n_jobs=2)
    elif family == 'rf':
        cls = RandomForestClassifier(n_estimators=300, class_weight='balanced_subsample',
                                     random_state=42, n_jobs=2)
    elif family == 'hist':
        cls = HistGradientBoostingClassifier(max_iter=250, learning_rate=.04,
                                             l2_regularization=10, random_state=42,
                                             early_stopping=False)
    else:
        raise ValueError('Unknown predeclared model family')
    cls.set_params(**spec['params'])
    return pipe.set_params(classifier=cls)


def fit(spec, train):
    features = numeric_contract(spec['features']) + list(b.CATEGORICAL)
    pipe = pipeline(spec)
    weights = np.ones(len(train))
    if spec.get('recency_days'):
        age = (train.anchor_date.max() - train.anchor_date).dt.days.to_numpy()
        weights += np.exp(-age / spec['recency_days'])
    with threadpool_limits(limits=2):
        pipe.fit(train[features], train[b.TARGET], classifier__sample_weight=weights)
    member = {'pipeline': pipe, 'features': features, 'name': spec['name'], 'weight': 1.}
    if spec['family'] == 'stage_expert':
        segment = train.loc[train.service_number.eq(1)]
        if len(segment) < 30 or segment[b.TARGET].nunique() != 2:
            raise ValueError('First-service expert requires both classes and sufficient rows')
        expert = pipeline(spec)
        with threadpool_limits(limits=2):
            expert.fit(segment[features], segment[b.TARGET])
        member['first_service_pipeline'] = expert
    return member


def predict_member(member, frame):
    probability = member['pipeline'].predict_proba(frame[member['features']])[:, 1]
    if 'first_service_pipeline' in member:
        mask = frame.service_number.eq(1).to_numpy()
        if mask.any():
            probability[mask] = member['first_service_pipeline'].predict_proba(
                frame.loc[mask, member['features']])[:, 1]
    if not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any():
        raise ValueError('Invalid model probabilities')
    return probability


def predict_members(members, frame):
    weights = np.array([member['weight'] for member in members])
    if not len(weights) or not np.isfinite(weights).all() or (weights <= 0).any() or not np.isclose(weights.sum(), 1):
        raise ValueError('Positive ensemble weights summing to one required')
    return np.average([predict_member(member, frame) for member in members], axis=0, weights=weights)


def select(candidates):
    if not candidates or any(not np.isfinite(x[k]) for x in candidates
                             for k in ('mean_ap', 'mean_review_recall', 'mean_auc')):
        raise ValueError('Complete finite development scores required')
    baseline = next(x for x in candidates if x['name'] == 'v5_control')
    primary_pool = [x for x in candidates if x['mean_review_recall'] >= baseline['mean_review_recall'] - 1e-12]
    priority_pool = [x for x in candidates if x['mean_ap'] >= baseline['mean_ap'] - 1e-12]
    primary = max(primary_pool, key=lambda x: (x['mean_ap'], x['mean_review_recall'], x['mean_auc'], x['name']))
    priority = max(priority_pool, key=lambda x: (x['mean_review_recall'], x['mean_ap'], x['mean_auc'], x['name']))
    if primary['mean_ap'] <= baseline['mean_ap'] + 1e-12:
        primary = baseline
    if priority['mean_review_recall'] <= baseline['mean_review_recall'] + 1e-12:
        priority = baseline
    return {'control': baseline, 'primary': primary, 'priority': priority}


def audit_source(source):
    if source[b.TARGET].isna().any() or not source[b.TARGET].isin([True, False, 0, 1]).all():
        raise ValueError('Complete binary outcomes required')
    if source[c.KEYS].isna().any().any() or source.duplicated(c.KEYS).any():
        raise ValueError('Unique complete source service keys required')
    anchor = pd.to_datetime(source.anchor_date, errors='raise')
    end = pd.to_datetime(source.outcome_end_date, errors='raise')
    if not (end - anchor).dt.days.eq(30).all():
        raise ValueError('Every outcome window must remain 30 days')
    for field in ('service_number', 'package_sessions_recorded'):
        values = pd.to_numeric(source[field], errors='raise')
        if values.isna().any() or not np.isfinite(values).all() or not values.ge(1).all() or not values.mod(1).eq(0).all():
            raise ValueError('Valid paid-service and package counts required')
    if (source.service_number > source.package_sessions_recorded).any():
        raise ValueError('Overrun visit cannot enter paid-service cohort')
    return {'rows': len(source), 'positives': int(source[b.TARGET].sum()),
            'duplicate_keys': 0, 'fixed_30d_windows': True,
            'first_services': int(source.service_number.eq(1).sum()),
            'first_positive_windows': int((source.service_number.eq(1) & source[b.TARGET]).sum()),
            'unknown_premise_rows': int(source.premise_type.isna().sum())}


def specs_for(selection, protocol):
    return [next(x for x in protocol['models'] if x['name'] == name) for name, _ in selection['members']]


def artifact(selection, train, oof, protocol, purpose):
    calibrator, calibration = b.fit_calibrator(oof[b.TARGET], oof.raw_probability)
    threshold = b.select_threshold(oof[b.TARGET], b.apply_calibrator(calibrator, oof.raw_probability))
    members = [fit(spec, train) | {'weight': weight} for spec, (_, weight) in
               zip(specs_for(selection, protocol), selection['members'])]
    return {'members': members, 'calibrator': calibrator, 'threshold': threshold,
            'calibration': calibration, 'selection': selection['name'],
            'training_rows': len(train), 'training_positives': int(train[b.TARGET].sum()),
            'training_max_outcome_end_date': train.outcome_end_date.max().date().isoformat(),
            'purpose': purpose, 'code_sha256': digest(__file__), 'protocol_sha256': digest(PROTOCOL)}


def predict_artifact(model, source):
    if model['code_sha256'] != digest(__file__):
        raise ValueError('Challenger feature/prediction code changed')
    frame = prepare(source, require_outcomes=False)
    return frame[c.KEYS].assign(probability=b.apply_calibrator(model['calibrator'],
                                                             predict_members(model['members'], frame)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    out = first.private_output(args.output_dir)
    if out.exists():
        raise ValueError('Choose a new output directory; preserve previous evidence')
    protocol = json.loads(PROTOCOL.read_text())
    frozen = b.ROOT / 'outputs/cp2-v2/prospective_callback_v2/bundle.json'
    source_path = b.ROOT / protocol['source_relative_path']
    if digest(source_path) != protocol['source_sha256'] or digest(frozen) != protocol['frozen_bundle_sha256']:
        raise ValueError('Source or frozen-bundle hash mismatch')
    source = b.load_dataset_input(source_path)
    source_audit = audit_source(source)
    excluded = source.loc[pd.to_datetime(source.anchor_date).lt(protocol['excluded_anchor_start'])].copy()
    train, diagnostic, split_audit = c.reserved_split(prepare(excluded))
    if not train.anchor_date.lt(protocol['development_anchor_end_exclusive']).all():
        raise ValueError('Development dates escaped protocol')
    out.mkdir(parents=True)
    (out / 'protocol.json').write_bytes(PROTOCOL.read_bytes())
    declarations = [{**spec, 'members': [[spec['name'], 1.]]} for spec in protocol['models']] + protocol['ensembles']
    metrics, oof = {x['name']: [] for x in declarations}, {x['name']: [] for x in declarations}
    fold_audit = []
    for fold, past, valid, audit in folds(train):
        fold_audit.append({'fold': fold, 'training_rows': len(past), 'validation_rows': len(valid), **audit})
        scores = {}
        for spec in protocol['models']:
            started = monotonic()
            member = fit(spec, past)
            scores[spec['name']] = predict_member(member, valid)
            print(f'{fold}: {spec["name"]} fitted in {monotonic() - started:.1f}s', flush=True)
        for declaration in declarations:
            name = declaration['name']
            weights = np.array([weight for _, weight in declaration['members']])
            if not np.isclose(weights.sum(), 1) or (weights <= 0).any():
                raise ValueError('Invalid declared ensemble')
            raw = np.average([scores[member] for member, _ in declaration['members']], axis=0, weights=weights)
            review = first.review_metrics(valid, raw, 0.)
            metrics[name].append({'fold': fold, 'roc_auc': b.score(valid[b.TARGET], raw)['roc_auc'],
                                  'average_precision': b.score(valid[b.TARGET], raw)['average_precision'],
                                  'review': review})
            oof[name].append(valid[b.KEYS + ['validation_group']].assign(raw_probability=raw, fold=fold))
    candidates = [{'name': x['name'], 'members': x['members'], 'folds': metrics[x['name']],
                   'mean_ap': float(np.mean([m['average_precision'] for m in metrics[x['name']]])),
                   'mean_auc': float(np.mean([m['roc_auc'] for m in metrics[x['name']]])),
                   'mean_review_recall': float(np.mean([m['review']['all']['recall'] for m in metrics[x['name']]])),
                   'mean_first_recall': float(np.mean([m['review']['first_service']['recall'] for m in metrics[x['name']]]))}
                  for x in declarations]
    chosen = select(candidates)
    declaration = {'created_at_utc': datetime.now(timezone.utc).isoformat(),
                   'protocol_sha256': digest(PROTOCOL), 'code_sha256': digest(__file__),
                   'source_audit': source_audit, 'split_audit': split_audit, 'fold_audit': fold_audit,
                   'candidates': candidates, 'selected': {role: x['name'] for role, x in chosen.items()},
                   'selection_before_diagnostic_and_new_holdout': True}
    write(out / 'development_selection.json', declaration)
    full = prepare(source)
    historical = c.historical_training(full, protocol['new_retrospective_period']['historical_training_outcomes_end_exclusive'])
    diagnostic_results, historical_artifacts = {}, {}
    for role, selection in chosen.items():
        oof_frame = pd.concat(oof[selection['name']], ignore_index=True)
        role_dir = out / role
        role_dir.mkdir()
        diagnostic_model = artifact(selection, train, oof_frame, protocol, 'exploratory_old2026_diagnostic')
        joblib.dump(diagnostic_model, role_dir / 'diagnostic_model.joblib')
        probability = b.apply_calibrator(diagnostic_model['calibrator'], predict_members(diagnostic_model['members'], diagnostic))
        predictor_source = excluded.loc[pd.to_datetime(excluded.anchor_date).ge('2026-01-01')].drop(columns=[b.TARGET])
        replay = predict_artifact(joblib.load(role_dir / 'diagnostic_model.joblib'), predictor_source)
        if not np.allclose(probability, replay.probability, rtol=0, atol=1e-12):
            raise ValueError('Serialized predictor-only replay differs')
        raw = predict_members(diagnostic_model['members'], diagnostic)
        diagnostic_results[role] = {'selection': selection['name'],
                                    **b.score(diagnostic[b.TARGET], probability, diagnostic_model['threshold']),
                                    'review': first.review_metrics(diagnostic, raw, 0.),
                                    'replay_max_difference': float(np.max(np.abs(probability - replay.probability)))}
        diagnostic[c.KEYS + [b.TARGET]].assign(probability=probability).to_csv(
            role_dir / 'diagnostic_predictions_private.csv', index=False)
        new_model = artifact(selection, historical, oof_frame, protocol, 'later_Aug28_31_validation_not_online_predictions')
        path = role_dir / 'historical_model.joblib'
        joblib.dump(new_model, path)
        historical_artifacts[role] = {'path': str(path.relative_to(b.ROOT)), 'sha256': digest(path),
                                      'training_rows': len(historical),
                                      'max_outcome_end_date': new_model['training_max_outcome_end_date']}
    if digest(frozen) != protocol['frozen_bundle_sha256']:
        raise ValueError('Frozen model changed during experiment')
    result = declaration | {'status': 'exploratory_candidates_only_frozen_v5_unchanged',
                            'selection_sha256': digest(out / 'development_selection.json'),
                            'diagnostic': diagnostic_results, 'historical_artifacts': historical_artifacts,
                            'limits': protocol['limits']}
    write(out / 'results.json', result)
    print(json.dumps({'selected': result['selected'], 'diagnostic': diagnostic_results}, indent=2))


if __name__ == '__main__':
    main()
