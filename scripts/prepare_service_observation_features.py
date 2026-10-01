"""Validate structured evidence and prepare private, as-of candidate features.

Offline preparation only: no source writes, frozen-model changes or outcome
relabeling. Missing or late observations remain missing rather than inferred.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METHODS = ('gel_bait', 'spray', 'fogging', 'misting', 'trapping', 'inspection', 'other')
BOOLEAN = {'true': 1, 'false': 0, 'unknown': None}
REASONS = {'corrective_callback', 'paid_scheduled', 'complimentary_bonus',
           'inspection', 'cancelled', 'unknown'}
COUNT_METHODS = {'visual_live_pest', 'trap_capture', 'other', 'unknown'}
FEATURES = ('observation_available', 'evidence_count', 'inspection_minutes',
            'evidence_count_method', 'treatment_completed', 'access_problem') + tuple(
                f'treatment_{method}' for method in METHODS)


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        raise ValueError('A timezone-bearing ISO timestamp is required') from None
    if parsed.utcoffset() is None:
        raise ValueError('A timezone-bearing ISO timestamp is required')
    return parsed.astimezone(timezone.utc)


def number(value):
    if value in ('', 'unknown'):
        return None
    try:
        result = float(value)
    except ValueError:
        raise ValueError('A finite nonnegative number is required') from None
    if not math.isfinite(result) or result < 0:
        raise ValueError('A finite nonnegative number is required')
    return result


def methods(value):
    tokens = value.split('|')
    if value == 'unknown':
        return None
    if len(set(tokens)) != len(tokens) or not set(tokens) <= set(METHODS):
        raise ValueError('Treatment methods must use unique supported codes or unknown')
    return set(tokens)


def require(row, keys):
    if any(not row.get(key, '').strip() for key in keys):
        raise ValueError('Required linkage or provenance field is missing')


def validate_versions(rows, identifier):
    seen = set()
    previous = {}
    for row in rows:
        require(row, [identifier, 'version', 'base_service_reference', 'recorded_at',
                      'available_at', 'source_reference'])
        try:
            version = int(row['version'])
        except ValueError:
            raise ValueError('Version must be a positive integer') from None
        key = (row[identifier], version)
        if version <= 0 or key in seen:
            raise ValueError('Duplicate record version or nonpositive version')
        seen.add(key)
        recorded, available = timestamp(row['recorded_at']), timestamp(row['available_at'])
        if recorded > available:
            raise ValueError('Recording time cannot follow first source availability')
        previous.setdefault(row[identifier], []).append((version, available, row))
    for history in previous.values():
        history.sort(key=lambda x: x[0])
        if [x[0] for x in history] != list(range(1, len(history) + 1)):
            raise ValueError('Full version history starting at one is required')
        if any(later[1] <= earlier[1] for earlier, later in zip(history, history[1:])):
            raise ValueError('Version availability must increase strictly')
        linkage = {tuple(row.get(k, '') for k in ('base_service_reference', 'sales_record_id',
                                                  'property_id')) for _, _, row in history}
        if len(linkage) != 1:
            raise ValueError('Versions cannot silently change service linkage')


def validate_observations(rows):
    validate_versions(rows, 'observation_id')
    service_ids = {}
    for row in rows:
        require(row, ['sales_record_id', 'property_id', 'observed_at', 'reported_pest_types',
                      'initial_severity', 'severity_rubric_id', 'evidence_count_method',
                      'treatment_methods', 'treatment_completed', 'access_problem'])
        if timestamp(row['observed_at']) > timestamp(row['recorded_at']):
            raise ValueError('Observation cannot follow its recording time')
        if row['initial_severity'] not in {'none', 'low', 'medium', 'high', 'unknown'}:
            raise ValueError('Unsupported severity code')
        if row['initial_severity'] != 'unknown' and row['severity_rubric_id'] == 'unknown':
            raise ValueError('Known severity requires a referenced assessment rubric')
        count, effort = number(row.get('evidence_count', '')), number(row.get('inspection_minutes', ''))
        if count is not None and not count.is_integer():
            raise ValueError('Evidence count must be a whole number')
        if row['evidence_count_method'] not in COUNT_METHODS:
            raise ValueError('Unsupported count method')
        if count is not None and (row['evidence_count_method'] == 'unknown' or not effort):
            raise ValueError('Evidence count requires method and positive inspection effort')
        methods(row['treatment_methods'])
        if any(row[k] not in BOOLEAN for k in ('treatment_completed', 'access_problem')):
            raise ValueError('Use true, false or unknown for evidence flags')
        ids = service_ids.setdefault(row['base_service_reference'], set())
        ids.add(row['observation_id'])
        if len(ids) > 1:
            raise ValueError('One observation history per service is required')


def validate_outcomes(rows):
    validate_versions(rows, 'callback_case_id')
    for row in rows:
        require(row, ['callback_visit_reason'])
        if row['callback_visit_reason'] not in REASONS:
            raise ValueError('Unsupported callback reason')
        for field in ('claim_requested_at', 'callback_scheduled_at', 'callback_completed_at'):
            if row.get(field, ''):
                timestamp(row[field])
        if row.get('callback_completed_at', '') and not row.get('callback_event_reference', ''):
            raise ValueError('Completion evidence requires a callback event reference')
        for field in ('claim_requested_at', 'callback_completed_at'):
            if row.get(field, '') and timestamp(row[field]) > timestamp(row['recorded_at']):
                raise ValueError('Actual request/completion cannot follow recording time')


def prepare(anchors, observations):
    validate_observations(observations)
    grouped = {}
    for row in observations:
        grouped.setdefault(row['base_service_reference'], []).append(row)
    result, reasons, seen = [], Counter(), set()
    for anchor in anchors:
        require(anchor, ['base_service_reference', 'sales_record_id', 'property_id', 'prediction_at'])
        service = anchor['base_service_reference']
        if service in seen:
            raise ValueError('Duplicate service anchor')
        seen.add(service)
        deadline = timestamp(anchor['prediction_at'])
        candidates = grouped.get(service, [])
        if any((r['sales_record_id'], r['property_id']) !=
               (anchor['sales_record_id'], anchor['property_id']) for r in candidates):
            raise ValueError('Observation linkage conflicts with service anchor')
        eligible = [r for r in candidates if timestamp(r['available_at']) <= deadline]
        # Actual collector ingestion time is available_at, never a backdated form timestamp.
        latest = max(eligible, key=lambda r: int(r['version'])) if eligible else None
        row = {k: anchor[k] for k in ('base_service_reference', 'prediction_at')}
        row.update(dict.fromkeys(FEATURES))
        row['observation_available'] = int(latest is not None)
        reasons['available' if latest else 'late_only' if candidates else 'missing'] += 1
        if latest:
            row['evidence_count'] = number(latest.get('evidence_count', ''))
            row['inspection_minutes'] = number(latest.get('inspection_minutes', ''))
            row['evidence_count_method'] = latest['evidence_count_method']
            row['treatment_completed'] = BOOLEAN[latest['treatment_completed']]
            row['access_problem'] = BOOLEAN[latest['access_problem']]
            actual_methods = methods(latest['treatment_methods'])
            # A planned method is not evidence of treatment performed.
            if row['treatment_completed'] == 1 and actual_methods is not None:
                for method in METHODS:
                    row[f'treatment_{method}'] = int(method in actual_methods)
        result.append(row)
    return result, dict(reasons)


def read_csv(path, template):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        with (ROOT / 'templates' / template).open(encoding='utf-8', newline='') as schema:
            required = next(csv.reader(schema))
        if reader.fieldnames != required:
            raise ValueError('Input header must match its blank recording template exactly')
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError('CSV row width must match the template')
        return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--anchors-csv', required=True, type=Path)
    parser.add_argument('--observations-csv', required=True, type=Path)
    parser.add_argument('--outcomes-csv', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if not out.is_relative_to((ROOT / 'outputs').resolve()) or out.exists():
        raise ValueError('Choose a new private directory under ignored outputs')
    anchors = read_csv(args.anchors_csv, 'cp2_prediction_anchors_v1.csv')
    observations = read_csv(args.observations_csv, 'cp2_service_observations_v1.csv')
    outcomes = read_csv(args.outcomes_csv, 'cp2_callback_outcomes_v1.csv') if args.outcomes_csv else []
    validate_outcomes(outcomes)
    features, coverage = prepare(anchors, observations)
    anchor_services = {row['base_service_reference'] for row in anchors}
    report = {'status': 'candidate_data_preparation_only_not_deployed',
              'anchors': len(anchors), 'observation_versions': len(observations),
              'outcome_versions': len(outcomes), 'asof_coverage': coverage,
              'unmatched_observation_services': len({row['base_service_reference'] for row in observations}
                                                    - anchor_services),
              'unmatched_outcome_cases': len({row['callback_case_id'] for row in outcomes
                                             if row['base_service_reference'] not in anchor_services}),
              'nonmissing_feature_counts': {k: sum(row[k] is not None for row in features) for k in FEATURES},
              'source_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest()
                               for name, path in [('anchors', args.anchors_csv),
                                                  ('observations', args.observations_csv),
                                                  ('outcomes', args.outcomes_csv)] if path},
              'limits': ['No outcome labels generated or changed.',
                         'Severity excluded pending approved rubric and reliability review.',
                         'No model training, cloud ingestion or independent accuracy claim.']}
    out.mkdir(parents=True)
    with (out / 'candidate_features_private.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['base_service_reference', 'prediction_at', *FEATURES])
        writer.writeheader()
        writer.writerows(features)
    (out / 'quality_summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
