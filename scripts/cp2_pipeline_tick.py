"""Cheap Calendar-only two-minute trigger for prospective CP2 scoring.

The full Google Sheets/Calendar/weather/BigQuery pipeline runs only when a
non-cancelled, timed service appointment has just ended. The final model and
source-derived labels are separate; this trigger never backdates a prediction.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

try:
    from scripts import cp2_pipeline as pipeline
    from scripts import load_calendar_bronze as calendar
    from scripts import cp2_model
    from scripts.freeze_callback_prospective import record_digest, timestamp
    from scripts.calendar_appointment_policy import is_confirmed_placeholder
except ModuleNotFoundError:
    import cp2_pipeline as pipeline
    import load_calendar_bronze as calendar
    import cp2_model
    from freeze_callback_prospective import record_digest, timestamp
    from calendar_appointment_policy import is_confirmed_placeholder


def service_window(event):
    """Return a Calendar service window without treating no-warranty as a claim."""
    if (event.get('status') or '').upper() != 'CONFIRMED' or event.get('is_all_day'):
        return None
    if is_confirmed_placeholder(event):
        return None
    title = (event.get('summary') or '').upper()
    if re.search(r'^\s*CANCEL(?:L)?ED\b', title):
        return None
    title = re.sub(r'\b(?:NO|WITHOUT)\s+WARRANTY\b', '', title)
    package_visit = re.search(r'\b(\d{1,2})\s*/\s*(\d{1,2})\b', title)
    if not package_visit:
        return None
    visit_number, package_sessions = map(int, package_visit.groups())
    # Calendar 4/3, 5/3, etc. are extra warranty visits after the paid
    # package's scheduled sessions. Keep them out of the paid-service cohort.
    if visit_number < 1 or package_sessions < 1 or visit_number > package_sessions:
        return None
    if re.search(r'\b(?:WARRANTY|CLAIMS?|CALLBACK|CONSULTATION|INSPECTION|EXTRA|COMPLIMENTARY)\b', title):
        return None
    try:
        finish = timestamp(event['end_raw'])
        start = timestamp(event['start_raw'])
    except (ValueError, KeyError, TypeError):
        return None
    return (start, finish) if start <= finish else None


def timed_service(event, now, protocol=None):
    window = service_window(event)
    if window is None:
        return False
    from scripts.cp2_collection_policy import capture_at
    start, end = window
    finish = capture_at(start, end, protocol)
    offset = (now-finish).total_seconds()
    # Start source/weather preparation shortly before the scheduled end.
    # The full pipeline waits until end before deriving/scoring predictors.
    return -150 <= offset <= 240


def event_key(event):
    identity = '|'.join([str(event['calendar_id']), str(event['event_id']),
                         str(event['start_raw']), str(event['end_raw'])])
    return hashlib.sha256(identity.encode()).hexdigest()


def committed_event_keys(base, bundle):
    """Recover Calendar acknowledgements from validated immutable score logs."""
    result = set()
    bundle_sha = pipeline.digest(bundle/'bundle.json')
    for path in (base/'prospective_logs').glob('*.json'):
        entry = pipeline.read(path)
        if entry.get('bundle_sha256') != bundle_sha:
            continue
        row = entry.get('row', {})
        receipt = entry.get('source_receipt', {})
        key = '|'.join(str(row[field]) for field in
                       ('population', 'sales_record_id', 'anchor_date'))
        bound = receipt.get('calendar_event_keys_by_prediction_key', {}).get(key)
        if (entry.get('schema_version') != 2 or
                entry.get('record_sha256') != record_digest(entry) or
                path.stem != hashlib.sha256(key.encode()).hexdigest() or
                entry.get('label_status') != 'awaiting_calendar_30d_outcome' or
                receipt.get('source') != 'Google Calendar + Google Sheets' or
                not re.fullmatch(r'[a-f0-9]{64}', str(receipt.get('snapshot_sha256', ''))) or
                not re.fullmatch(r'[a-f0-9]{64}', str(receipt.get('feature_input_sha256', ''))) or
                receipt.get('post_end_calendar_recheck', {}).get('verified_event_count', 0) < 1 or
                not isinstance(bound, str) or not re.fullmatch(r'[a-f0-9]{64}', bound)):
            raise ValueError('Existing prospective Calendar event binding is invalid')
        result.add(bound)
    return result


def poll(now=None, *, fetch=None, run=None, base=None):
    base = pipeline.private(base or pipeline.BASE)
    now = timestamp(now or datetime.now(timezone.utc))
    registry, bundle = cp2_model.current_bundle()
    from scripts import cp2_collection_policy as collection
    protocol = collection.load(pipeline.ROOT) if (pipeline.ROOT/'config/cp2_model_current.json').exists() else None
    manifest = json.loads((bundle/'bundle.json').read_text(encoding='utf-8'))
    local_day = now.astimezone(pipeline.LOCAL).date()
    cohort_start = datetime.fromisoformat(manifest['cohort_start']).date()
    cohort_end = datetime.fromisoformat(manifest['cohort_end']).date()
    if protocol:
        cohort_end = max(cohort_end, datetime.fromisoformat(protocol['cohort_end']).date())
    if local_day < cohort_start:
        result = {'checked_at_utc': now.isoformat(), 'status': 'outside_prospective_cohort',
            'calendar_events_checked': 0, 'due_events': 0, 'full_refresh_started': False}
        pipeline.atomic_json(base/'last_tick.json', result)
        return result
    seen_path = base/'watch_events.json'
    history = pipeline.read(seen_path) if seen_path.exists() else {'processed': [], 'unresolved': {}}
    last_poll = history.get('last_poll_at_utc')
    first_day = max(cohort_start, timestamp(last_poll).astimezone(pipeline.LOCAL).date()) if last_poll else cohort_start
    last_day = min(local_day, cohort_end+timedelta(days=1))
    if fetch is None:
        from dotenv import load_dotenv
        import os
        load_dotenv(pipeline.ROOT/'.env')
        targets = calendar._targets(calendar._local_path(os.getenv('NOMOBUG_GOOGLE_METADATA'),
            'data/profiles/google_source_metadata.json'))
        fetch = lambda: calendar._fetch(targets, first_day, last_day)
    events = fetch() if first_day <= last_day else []
    processed = set(history['processed'])
    unresolved = dict(history.get('unresolved', {}))
    unresolved_anchor_dates = dict(history.get('unresolved_anchor_dates', {}))
    missed = dict(history.get('missed', {}))
    missed_anchor_dates = dict(history.get('missed_anchor_dates', {}))
    decisions = dict(history.get('event_decisions', {}))
    capture_times = dict(history.get('capture_times', {}))
    service_ends = dict(history.get('service_ends', {}))
    missed_before = set(missed)
    committed = committed_event_keys(base, bundle)
    processed.update(committed)
    for key in committed:
        unresolved.pop(key, None)
        unresolved_anchor_dates.pop(key, None)
        missed.pop(key, None)
        missed_anchor_dates.pop(key, None)
    due = {}
    for row in events:
        window = service_window(row)
        if window is None:
            continue
        start, finish = window
        capture = collection.capture_at(start, finish, protocol)
        if not cohort_start <= start.astimezone(pipeline.LOCAL).date() <= cohort_end:
            continue
        key = event_key(row)
        capture_times[key] = capture.isoformat()
        service_ends[key] = finish.isoformat()
        if key in committed:
            processed.add(key)
            unresolved.pop(key, None)
            unresolved_anchor_dates.pop(key, None)
            missed.pop(key, None)
            missed_anchor_dates.pop(key, None)
            continue
        if (now-capture).total_seconds() > 300 and key not in processed:
            missed.setdefault(key, finish.isoformat())
            missed_anchor_dates.setdefault(key, start.astimezone(pipeline.LOCAL).date().isoformat())
            unresolved.pop(key, None)
            unresolved_anchor_dates.pop(key, None)
        elif timed_service(row, now, protocol):
            due[key] = capture
    for key, end in due.items():
        if key not in processed:
            unresolved.setdefault(key, end.isoformat())
            matching = next((row for row in events if event_key(row) == key), None)
            if matching is not None:
                unresolved_anchor_dates.setdefault(key, service_window(matching)[0].astimezone(
                    pipeline.LOCAL).date().isoformat())
    for key, ended_at in list(unresolved.items()):
        if now-timestamp(ended_at) > timedelta(minutes=5):
            missed[key] = service_ends.get(key, ended_at)
            anchor = unresolved_anchor_dates.get(key)
            if anchor is not None:
                missed_anchor_dates.setdefault(key, anchor)
            unresolved.pop(key)
            unresolved_anchor_dates.pop(key, None)
    pending = set(due)-processed-set(missed)
    result = {'checked_at_utc': now.isoformat(), 'status': 'idle',
        'calendar_events_checked': len(events), 'due_events': len(due),
        'newly_due_events': len(pending), 'missed_event_windows': len(missed),
        'newly_missed_event_windows': len(set(missed)-missed_before),
        'reconciled_committed_windows': len(missed_before-set(missed)),
        'coverage_status': 'incomplete' if missed else 'complete_so_far',
        'full_refresh_started': bool(pending)}
    cloud_cohort = registry.get('cloud_cohort')
    if isinstance(cloud_cohort, list) and len(cloud_cohort) == 2:
        cloud_start, cloud_end = (datetime.fromisoformat(value).date()
                                  for value in cloud_cohort)
        cloud_missed = sum(cloud_start <= datetime.fromisoformat(
            missed_anchor_dates.get(key) or timestamp(ended_at).astimezone(
                pipeline.LOCAL).date().isoformat()).date() <= cloud_end
            for key, ended_at in missed.items())
        result['cloud_cohort_missed_event_windows'] = cloud_missed
        result['cloud_cohort_coverage_status'] = (
            'incomplete' if cloud_missed else 'complete_so_far')
    fresh_cohort = registry.get('october5_cohort')
    if isinstance(fresh_cohort, list) and len(fresh_cohort) == 2:
        fresh_start, fresh_end = (datetime.fromisoformat(value).date() for value in fresh_cohort)
        fresh_missed = sum(fresh_start <= datetime.fromisoformat(
            missed_anchor_dates.get(key) or timestamp(ended_at).astimezone(
                pipeline.LOCAL).date().isoformat()).date() <= fresh_end
            for key, ended_at in missed.items())
        result['october5_cohort_missed_event_windows'] = fresh_missed
        result['october5_cohort_coverage_status'] = ('not_started' if local_day < fresh_start
            else 'incomplete' if fresh_missed else 'complete_so_far')
    if pending:
        try:
            # Never hold an already-ended service behind a later appointment.
            next_end = min(due[key] for key in pending)
            state = (run or pipeline.run)(wait_until=next_end)
        except (Exception, SystemExit) as error:
            result.update(status='refresh_failed', error_type=type(error).__name__)
            # Pending events remain retryable; failures never become scores.
        else:
            receipt = state['stages']['prospective']['receipt']
            acknowledged = pending & set(receipt.get('logged_event_keys', []))
            decisions.update(receipt.get('event_decisions', {}))
            for key in receipt.get('eligible_anchor_event_keys', []):
                decisions[key] = 'eligible_anchor'
            result.update(status='refresh_succeeded', run_id=state['run_id'],
                prospective_logged_rows=receipt.get('logged_rows', 0),
                already_logged_rows=receipt.get('already_logged_rows', 0))
            processed.update(acknowledged)
            for key in acknowledged:
                unresolved.pop(key, None)
                unresolved_anchor_dates.pop(key, None)
            result['acknowledged_event_keys'] = len(acknowledged)
            if len(acknowledged) < len(pending):
                absent = pending - acknowledged
                result['status'] = ('refresh_completed_with_source_exclusions' if all(
                    decisions.get(key) not in (None, 'eligible_anchor', 'not_in_frozen_predictor_population')
                    for key in absent) else 'refresh_without_complete_prospective_logging')
    # Raw missed candidates remain immutable historical evidence. Never erase
    # them merely because a later snapshot now excludes or cannot match them.
    from collections import Counter
    result['missed_candidate_reason_counts'] = dict(Counter(decisions.get(key, 'not_yet_classified') for key in missed))
    if protocol:
        cohort_keys = [key for key in missed if protocol['cohort_start'] <= missed_anchor_dates.get(key, '') <= protocol['cohort_end']]
        eligible_misses = sum(decisions.get(key) == 'eligible_anchor' for key in cohort_keys)
        unresolved_matches = sum(decisions.get(key) in (None, 'unmatched_or_ambiguous_sale',
            'not_in_frozen_predictor_population', 'missing_sale_date', 'calendar_before_sale_date',
            'package_sequence_mismatch', 'uncertain_package', 'duplicate_paid_session') for key in cohort_keys)
        result.update(october10_cohort_missed_candidate_windows=len(cohort_keys),
            october10_cohort_missed_eligible_windows=eligible_misses,
            october10_cohort_unresolved_candidate_windows=unresolved_matches,
            october10_cohort_coverage_status='not_started' if local_day.isoformat() < protocol['cohort_start'] else
                'incomplete' if eligible_misses else 'requires_source_review' if unresolved_matches else 'complete_so_far')
    pipeline.atomic_json(seen_path, {'processed': sorted(processed), 'unresolved': unresolved,
        'unresolved_anchor_dates': unresolved_anchor_dates,
        'missed': missed, 'missed_anchor_dates': missed_anchor_dates,
        'event_decisions': decisions, 'capture_times':capture_times, 'service_ends':service_ends,
        'last_poll_at_utc': now.isoformat()})
    if registry.get('recovery_cohort_protocol_sha256'):
        from scripts.freeze_callback_prospective import cohort_contract
        recovery=cohort_contract(bundle,manifest,pipeline.ROOT/'config/cp2_recovery_cohort.json')
        keys=[key for key in missed if recovery['cohort_start']<=missed_anchor_dates.get(key,'')<=recovery['cohort_end']]
        eligible=sum(decisions.get(key)=='eligible_anchor' for key in keys)
        unresolved_count=sum(decisions.get(key) in (None,'unmatched_or_ambiguous_sale',
            'not_in_frozen_predictor_population','missing_sale_date','calendar_before_sale_date',
            'package_sequence_mismatch','uncertain_package','duplicate_paid_session') for key in keys)
        result.update(recovery_cohort_missed_candidate_windows=len(keys),
            recovery_cohort_missed_eligible_windows=eligible,
            recovery_cohort_unresolved_candidate_windows=unresolved_count,
            recovery_cohort_coverage_status='not_started' if local_day.isoformat()<recovery['cohort_start']
                else 'incomplete' if eligible else 'requires_source_review' if unresolved_count else 'complete_so_far')
    pipeline.atomic_json(base/'last_tick.json', result)
    return result


def main():
    result = poll()
    print(json.dumps(result, indent=2))
    return 1 if (result['status'] in {'refresh_failed','refresh_without_complete_prospective_logging'}
                 or result.get('newly_missed_event_windows', 0) > 0) else 0


if __name__ == '__main__':
    raise SystemExit(main())
