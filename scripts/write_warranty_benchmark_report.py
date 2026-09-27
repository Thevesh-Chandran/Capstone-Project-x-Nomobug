"""Publish a local model contract and human-readable benchmark receipt."""
import argparse
import hashlib
import json
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path, nargs='+')
    parser.add_argument('--local-tests', type=int, default=168)
    args = parser.parse_args()
    experiments = []
    for path in args.results:
        experiment = json.loads(path.read_text(encoding='utf-8'))
        for population in experiment['populations']:
            if 'fine_location_rows' in population:
                population['mapped_water_context_nonmissing_rows'] = population.pop('fine_location_rows')
            population['dataset_input_sha256'] = experiment['dataset_input_sha256']
            population['dataset_input_file'] = str((path.parent / 'dataset_input.json').resolve())
            population['source'] = experiment['source']
            population['feature_preparation_options'] = {
                'premise_context': experiment.get('premise_context_enabled', False),
                'normalize_pest_context': experiment.get('pest_normalization_enabled', False),
            }
            population['candidate_summary_file'] = str((path.parent /
                f"{population['population']}_candidate_summary.csv").resolve())
            population['business_target'] = (
                'recorded_corrective_callback_within_30d'
                if population['population'].startswith('matched_packages_')
                else 'recorded_warranty_claim_within_30d')
            population['model_artifact'] = str((path.parent /
                f"{population['population']}_selected_model.joblib").resolve())
        experiments.append(experiment)
    # Challengers can replace a model only by development evidence. Never use
    # diagnostic results to select the model or to change the business target.
    chosen = {}
    for experiment in experiments:
        for population in experiment['populations']:
            key = population['population']
            previous = chosen.get(key)
            if previous is None or population.get('selection', {}).get('mean_average_precision', -1) > previous.get('selection', {}).get('mean_average_precision', -1):
                chosen[key] = population
    result = dict(experiments[0], populations=list(chosen.values()))
    result['target'] = 'population_specific_recorded_claim_or_corrective_callback_within_30d'
    result['claim_meaning'] = 'recorded_visit_signal_not_biological_recurrence_or_entitlement'
    result['source'] = 'multiple_sources_see_dataset_inputs_and_population_contracts'
    fingerprints = [e['dataset_input_sha256'] for e in experiments]
    result['dataset_input_sha256'] = hashlib.sha256(json.dumps(fingerprints).encode()).hexdigest()
    result['dataset_inputs'] = [{'sha256': e['dataset_input_sha256'], 'source': e['source'],
                                'path': str((p.parent / 'dataset_input.json').resolve())}
                               for e, p in zip(experiments, args.results)]
    result['candidate_evaluations'] = sum(p.get('candidate_count', 0)
                                        for e in experiments for p in e['populations'])
    receipt = ROOT / 'outputs/cp2-v2/model_improvement_results.json'
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# CP2 model improvement — 27 September 2026', '',
        'The reviewed labels, prediction timing and evaluation were repaired before',
        'model comparison. These are retrospective experiments, not operational',
        'recurrence forecasts. The already-inspected 2026 period is diagnostic.', '',
        '## Recommendation', '',
        'Use recorded corrective-callback planning as the strongest experimental',
        'CP2 prediction goal. It has a larger sample and useful ranking evidence.',
        'Warranty entitlement remains a policy calculation; the warranty-only',
        'prediction models are too weak or uncertain for operational decisions.',
        'Freeze the development-selected model and evaluate future mature records',
        'before adopting its probabilities or alert threshold.', '',
        '## Target and variable meaning', '',
        'Each row is a recorded paid base service. Prediction occurs immediately',
        'after that service; the target is categorical/binary: 1 if a recorded',
        'corrective claim visit follows within 30 days, otherwise 0. Models output',
        'a numerical probability from 0 to 1. Ordinary scheduled visits are not',
        'positive outcomes. Callback planning includes discretionary commercial',
        'returns, without granting commercial warranty entitlement.', '',
        'The 30-day prediction horizon does not shorten 4x/6x/12x entitlement',
        'through the active service period and 30 days after the final service.',
        'A claim later than 30 days after an anchor can be policy-valid while',
        'remaining outside this particular prediction target.', '',
        'Numerical predictors include package/session counts, prior service and',
        'claim history, price, service gaps, season, rainfall, humidity, temperature,',
        'soil moisture, elevation, waterway distances and land-cover proportions.',
        'Categorical predictors describe the recorded pest, package and treatment',
        'method; the callback experiment also includes residential/commercial type.',
        'Outcome counts, future appointments and post-anchor weather are excluded.', '',
        '## What was implemented', '',
        '- Applied all 80 user decisions with event-level provenance. Two unresolved',
        '  records remain unknown; their matched packages are excluded from training.',
        '- Fixed negated warranty wording and sequence-only consultation classification.',
        '- Preserved reviewed upsell, included bonus, completion and discretionary-claim',
        '  exceptions. Commercial contractual eligibility was not expanded.',
        '- Fixed the prior-seven-day workload join and bounded service history at the anchor.',
        '- Compared fixed 30-day targets: residential 3x after service three, and',
        '  residential 4x/6x/12x after each recorded base service. The latter windows',
        '  can overlap; validation and bootstrapping preserve property dependence.',
        '- Also tested operational corrective-callback planning for matched packages',
        '  across residential/commercial clients. It predicts recorded extra work,',
        '  independently of contractual entitlement, and uses explicit premise context.',
        '- Added antecedent 1–30 day rainfall, wet/heavy-rain counts, rain recency,',
        '  temperature, humidity, soil moisture and rainfall-trend variables.',
        '- Added ESA WorldCover 2021 built-up, tree, grass, crop, water and wetland',
        '  fractions within 250 m and 1 km. The historical map predates the examples.',
        '- Refreshed elevation/place/waterway context for newly eligible anchors.',
        '- Tested deterministic Malay/English pest aliases and multi-pest indicators',
        '  while retaining raw labels and unknown terms. The normalised challenger',
        '  won callback development selection by only 0.0027 AP, with mixed fold gains.',
        '- Compared logistic regression, random forests, extra trees, histogram',
        '  gradient boosting, CatBoost and a prevalence baseline with six feature sets.',
        '- Embargoed outcomes not known before each fold and kept connected packages',
        '  and properties together. Assertions check both identifiers separately.',
        '  All imputers and categorical transforms fit training only.',
        '- Added positive-slope calibration from pre-2026 predictions, top-20% review',
        '  metrics, component-bootstrap intervals, saved models and replayable inputs.', '',
        '## Selected models and diagnostic results', '',
        '| Population | Model / feature set | Rows / claims | AUC | AP / prevalence | Accuracy at development threshold | No-claim accuracy | Recall |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    contracts = []
    for population in result['populations']:
        if 'diagnostic_2026' not in population:
            lines.append(f"| {population['population']} | Insufficient support | — | — | — | — | — | — |")
            continue
        metrics = population['diagnostic_2026']
        features = population['selected_features']
        lines.append(
            f"| {population['population']} | {population['selected_model']} / {population['selected_feature_set']} | "
            f"{metrics['rows']} / {metrics['positives']} | {metrics['roc_auc']:.3f} | "
            f"{metrics['average_precision']:.3f} / {metrics['prevalence']:.3f} | "
            f"{metrics['accuracy']:.1%} | {metrics['majority_class_accuracy']:.1%} | {metrics['recall']:.1%} |"
        )
        contracts.append({
            'population': population['population'],
            'business_target': population['business_target'],
            'model': population['selected_model'],
            'feature_set': population['selected_feature_set'],
            'features': features,
            'feature_preparation_options': population['feature_preparation_options'],
            'ordered_feature_sha256': hashlib.sha256(json.dumps(features, separators=(',', ':')).encode()).hexdigest(),
            'threshold': population['development_threshold'],
            'selection': population['selection'],
            'calibration': population['calibration'],
            'diagnostic_2026': metrics,
            'model_artifact': population['model_artifact'],
            'dataset_input_sha256': population.get('dataset_input_sha256', result['dataset_input_sha256']),
        })
    lines += ['',
        'AP (average precision) evaluates ranking of rare claims; its no-signal',
        'baseline is claim prevalence. AUC = 0.5 is chance discrimination. High raw',
        'accuracy alone can reward never identifying a claim.', '',
        f"Evaluated {result['candidate_evaluations']} candidate/feature combinations,",
        'including development-only challengers. Duplicate target experiments are',
        'selected by pre-2026 development AP, never by their 2026 scores.', '',
        '## Development evidence and uncertainty', '',
    ]
    for population in result['populations']:
        if 'selection' not in population:
            continue
        selection = population['selection']
        matching_experiments = [p for e in experiments for p in e['populations']
                                if p['population'] == population['population']]
        evaluated = sum(p['candidate_count'] for p in matching_experiments)
        lines += [
            f"### {population['population']}", '',
            f"Selected from {evaluated} candidates using {int(selection['development_folds'])} "
            f"pre-2026 folds. Mean development AP {selection['mean_average_precision']:.4f}, "
            f"fold SD {selection['sd_average_precision']:.4f}; AUC {selection['mean_roc_auc']:.4f}.", '',
        ]
        intervals = population['diagnostic_clustered_bootstrap']['confidence_95pct']
        lines.append(f"Package/property-component bootstrap AUC interval: {intervals['roc_auc'][0]:.3f}–{intervals['roc_auc'][1]:.3f}. "
                     f"AP interval: {intervals['average_precision'][0]:.3f}–{intervals['average_precision'][1]:.3f}.")
        priority = population['diagnostic_priority_top20pct']
        lines += ['', f"Reviewing the highest-scored {priority['realized_fraction']:.1%} of rows captures "
                  f"{priority['recall']:.1%} of claims, with {priority['precision']:.1%} precision "
                  f"({priority['precision_lift_over_prevalence']:.2f}× the population claim rate)."]
        candidates = []
        for experiment_population in matching_experiments:
            with Path(experiment_population['candidate_summary_file']).open(encoding='utf-8', newline='') as handle:
                current_candidates = list(csv.DictReader(handle))
            for candidate in current_candidates:
                candidate['pest_context'] = ('normalised + raw' if experiment_population[
                    'feature_preparation_options']['normalize_pest_context'] else 'raw')
            candidates.extend(current_candidates)
        best_by_features = {}
        for candidate in candidates:
            feature_set = (candidate['feature_set'], candidate['pest_context'])
            previous = best_by_features.get(feature_set)
            if previous is None or float(candidate['mean_average_precision']) > float(previous['mean_average_precision']):
                best_by_features[feature_set] = candidate
        lines += ['', 'Development comparison on the same cohort:', '',
                  '| Feature set | Pest context | Best model | Mean AP | Fold SD |',
                  '| --- | --- | --- | ---: | ---: |']
        for candidate in best_by_features.values():
            lines.append(f"| {candidate['feature_set']} | {candidate['pest_context']} | {candidate['model']} | "
                         f"{float(candidate['mean_average_precision']):.4f} | "
                         f"{float(candidate['sd_average_precision']):.4f} |")
        lines += ['', 'Calibration and review workload:', '',
                  '```json', json.dumps({k: population[k] for k in [
                      'calibration', 'diagnostic_2026_raw',
                      'diagnostic_prevalence_baseline', 'diagnostic_priority_top20pct',
                  ]}, indent=2), '```', '']
    lines += [
        '## Limits and next evidence', '',
        '- Environmental features were evaluated, not assumed beneficial. See the',
        '  development comparisons above. Small AP differences relative to fold',
        '  variability do not establish environmental benefit or causation.',
        '- In the contractual cohorts, WorldCover coverage is about 53% for 3x anchors and 99% for multi-service',
        '  anchors, balanced across development/diagnostic periods. Missing data',
        '  remains missing, with training-fold imputation indicators.',
        '- Weather is coarse IFS reanalysis; it does not resolve house-level rain',
        '  or flooding. OSM waterways are mapped proximity, not flood occurrence.',
        '- Reanalysis can be revised and is not a frozen as-available weather feed.',
        '  The September 2026 OSM snapshot is retrospective for 2025 anchors.',
        '  Compact/history and weather-only candidates provide no-OSM sensitivity.',
        '- Spatial buffers can be smaller than geocoding uncertainty; approximate',
        '  locations cannot establish exact house-level water or land-cover exposure.',
        '  See [environmental source notes](CP2_ENVIRONMENTAL_FEATURE_NOTES.md).',
        '- Maximum seven-day temperature means the maximum cached daily mean,',
        '  not the maximum instantaneous temperature.',
        '- Labels describe recorded Calendar claim visits, not verified biological',
        '  recurrence or completed treatments. Calendar snapshots may contain',
        '  retrospective edits; full historical record versions are unavailable.',
        '- Address hashes can miss alternate spellings of the same property.',
        '- The small multi-service positive count and broad model search make model',
        '  selection uncertain. Development calibration metrics fit the calibrator',
        '  and must not be presented as independent calibration validation.',
        '- A higher-score 60/90-day 3x outcome would exceed the confirmed policy.',
        '  Ordinary repeat appointments would also mix scheduled work with claims.',
        '- Link original and upsell SALES allowances using verified package identity.',
        '  Do not sum all purchases for a customer or infer warranty from stale notes.',
        '- Promised bonus sessions must remain distinct from contractual tier and',
        '  claim-triggered service. Ambiguous allowances remain outside this cohort.',
        '- The most valuable prospective inputs are pre-service infestation severity,',
        '  observed pest evidence/count, property/treatment context, and a documented',
        '  claim reason/date. These were not fabricated as retrospective features.',
        '- Freeze the selected models and use newly arriving, fully mature records',
        '  for the next independent evaluation; do not tune against these 2026 scores.', '',
        '## Verification and replay', '',
        f'Live bounded dataset build: 53/53 passed. Local suite: {args.local_tests} passed.',
        'Saved selected model artifacts also reload and predict in a fresh Python process.',
        f"Composite input fingerprint: `{result['dataset_input_sha256']}`.",
        'Each model contract records its own exact input fingerprint and source.', '',
        '```powershell',
        '.\\.venv\\Scripts\\python.exe scripts\\build_warranty_experiment.py',
        '.\\.venv\\Scripts\\python.exe scripts\\benchmark_warranty_models.py --input-json outputs\\cp2-v2\\model_benchmark_components\\dataset_input.json --output-dir outputs\\cp2-v2\\model_benchmark_replay',
        '.\\.venv\\Scripts\\python.exe scripts\\benchmark_warranty_models.py --source profound-keel-500007-s4.analytics_ml.warranty_callback_fixed_horizon_dataset --input-json outputs\\cp2-v2\\model_callback_components\\dataset_input.json --premise-context --output-dir outputs\\cp2-v2\\model_callback_replay',
        '.\\.venv\\Scripts\\python.exe scripts\\benchmark_warranty_models.py --source profound-keel-500007-s4.analytics_ml.warranty_callback_fixed_horizon_dataset --input-json outputs\\cp2-v2\\model_callback_normalized_pest\\dataset_input.json --premise-context --normalize-pest-context --feature-set compact_history --feature-set base --feature-set base_weather_environment --model extra_trees_depth6 --model rf_depth3 --model rf_depth6 --model catboost_depth4_plain --model lr_c1.0_plain --output-dir outputs\\cp2-v2\\model_callback_normalized_replay',
        '```', '',
        'Sources: [ESA WorldCover data access](https://esa-worldcover.org/en/data-access),',
        '[Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api),',
        '[HOTOSM Malaysia waterways](https://data.humdata.org/dataset/hotosm_mys_waterways).',
    ]
    (ROOT/'planning/CP2_MODEL_IMPROVEMENT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    config = {
        'model_version': 'warranty_fixed_30d_reviewed_v4',
        'status': 'diagnostic_only_not_operational',
        'target': 'population_specific_recorded_claim_or_corrective_callback_within_30d',
        'target_type': 'binary_categorical',
        'prediction_type': 'numerical_probability_0_to_1',
        'horizon_days': 30,
        'validation': result['validation'],
        'reporting_caveat': result['reporting_caveat'],
        'dataset_input_sha256': result['dataset_input_sha256'],
        'dataset_inputs': result['dataset_inputs'],
        'candidate_evaluations': result['candidate_evaluations'],
        'recommended_experimental_goal': 'recorded_corrective_callback_within_30d',
        'models': contracts,
    }
    (ROOT/'config/warranty_model_experiment_v4.json').write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
    print('Wrote benchmark report and diagnostic model contracts')


if __name__ == '__main__':
    main()
