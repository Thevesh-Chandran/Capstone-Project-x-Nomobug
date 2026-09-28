"""Private, recoverable Google sources -> features -> fixed CP2 model workflow.

No Google source edits, permanent warehouse writes, model fitting or automatic
provider fallback. Only validated runs update the local last-success pointer.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import sys
import time
import uuid
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'outputs/cp2-v2/live_pipeline'
LOCAL = ZoneInfo('Asia/Kuala_Lumpur')
MAX_SOURCE_AGE_SECONDS = 300
STAGES = ['sources', 'weather', 'features', 'predictions', 'prospective']


def utcnow():
    return datetime.now(timezone.utc)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def private(path):
    result = Path(path).resolve()
    if not result.is_relative_to((ROOT/'outputs').resolve()):
        raise ValueError('Pipeline customer data must stay inside ignored outputs')
    return result


@contextlib.contextmanager
def pipeline_lock(base):
    """OS lock releases on process death; the lock file need not be deleted."""
    base.mkdir(parents=True, exist_ok=True)
    with (base/'.lock').open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Another CP2 pipeline process holds the run lock') from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def source_stage(run_dir):
    from dotenv import load_dotenv
    try:
        from scripts import load_calendar_bronze as calendar
        from scripts import operational_bronze_core as core
        from scripts import operational_source_contracts as contracts
        from scripts.prospects_source_contract import EXPECTED_HEADERS
    except ModuleNotFoundError:
        import load_calendar_bronze as calendar
        import operational_bronze_core as core
        import operational_source_contracts as contracts
        from prospects_source_contract import EXPECTED_HEADERS
    load_dotenv(ROOT/'.env')
    # The approved extractor checks live workbook titles, headers and pagination.
    # Its profiling output is suppressed; only aggregate receipts are published.
    with contextlib.redirect_stdout(io.StringIO()):
        source = runpy.run_path(str(ROOT/'scripts/profile_b2b_sales_payments.py'),
            init_globals={'include_all_approved_tabs': True})
    snapshots = {}
    for tab, frame in source['frames'].items():
        headers = EXPECTED_HEADERS if tab == '2026' else contracts.HEADERS[tab]
        prefix = 'prospects_2026' if tab == '2026' else contracts.PREFIXES[tab]
        # SALES A4 is an unused decorative cell, observed changing from a
        # number to free text. It is not a mapped field. Preserve its actual
        # value privately; every other positional header remains strict.
        headers = list(headers)
        header_variations = []
        if tab == 'SALES':
            actual = ' '.join(source['header_maps'][tab]['source_column_001'].split())
            if actual != headers[0]:
                headers[0] = actual
                header_variations.append('source_column_001')
        snapshot = core.prepare_snapshot(tab, frame, source['header_maps'][tab],
            source['source_lineage'][tab], headers, prefix)
        snapshot['metadata']['nonsemantic_header_variations'] = header_variations
        snapshot['schema'] = [field.to_api_repr() for field in snapshot['schema']]
        snapshots[tab] = snapshot
    if set(snapshots) != set(contracts.HEADERS) | {'2026'}:
        raise ValueError('Approved Sheets tab inventory is incomplete')
    targets = calendar._targets(calendar._local_path(os.getenv('NOMOBUG_GOOGLE_METADATA'),
        'data/profiles/google_source_metadata.json'))
    day = utcnow().astimezone(LOCAL).date()
    events = calendar._fetch(targets, calendar.DEFAULT_START, day)
    snapshot = calendar._snapshot(events, targets, calendar.DEFAULT_START, day)
    snapshot.pop('schema')
    snapshot['source_calendar_ids'] = [target['id'] for target in targets]
    atomic_json(run_dir/'sheets_private.json', {'snapshots': snapshots})
    atomic_json(run_dir/'calendar_private.json', snapshot)
    timestamps = [x['metadata']['extracted_at'] for x in snapshots.values()]
    timestamps.append(snapshot['metadata']['extracted_at'])
    parsed_timestamps = [datetime.fromisoformat(value.replace('Z', '+00:00')) for value in timestamps]
    receipt = {'source': 'Google Calendar + Google Sheets', 'calendar_count': 6,
        'calendar_rows': len(events), 'sheet_tabs': len(snapshots),
        'sheet_rows': {tab: len(x['records']) for tab, x in snapshots.items()},
        'extracted_at_utc': max(parsed_timestamps).isoformat(), 'earliest_extraction_at_utc': min(parsed_timestamps).isoformat(),
        'complete_calendar_inventory': True, 'calendar_coverage_start': '2000-01-01',
        'calendar_coverage_end_requested': day.isoformat(),
        'complete_outcomes_through': (day-timedelta(days=1)).isoformat(),
        'calendar_sha256': digest(run_dir/'calendar_private.json'),
        'sheets_sha256': digest(run_dir/'sheets_private.json')}
    receipt['snapshot_sha256'] = hashlib.sha256((receipt['calendar_sha256']+
        receipt['sheets_sha256']).encode()).hexdigest()
    atomic_json(run_dir/'source_receipt.json', receipt)
    return receipt


def weather_stage(run_dir):
    try:
        from scripts.callback_live_weather import refresh
    except ModuleNotFoundError:
        from callback_live_weather import refresh
    day = utcnow().astimezone(LOCAL).date()
    cache = BASE/'weather_cache'/day.isoformat()
    if (cache/'weather_receipt.json').exists():
        receipt = read(cache/'weather_receipt.json')
        if digest(cache/'weather_private.json') != receipt['input_sha256']:
            raise ValueError('Weather cache integrity changed')
    else:
        # Partial fetches are kept inside the run. Cache is published only complete.
        attempt_dir = run_dir/('weather_attempt_'+uuid.uuid4().hex[:8])
        receipt = refresh(attempt_dir, day)
        cache.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(attempt_dir/'weather_private.json', cache/'weather_private.json')
        atomic_json(cache/'weather_receipt.json', receipt)
    shutil.copyfile(cache/'weather_private.json', run_dir/'weather_private.json')
    atomic_json(run_dir/'weather_receipt.json', receipt)
    return receipt


def feature_stage(run_dir):
    try:
        from scripts.callback_live_features import derive
    except ModuleNotFoundError:
        from callback_live_features import derive
    result = derive(read(run_dir/'calendar_private.json'),
        read(run_dir/'sheets_private.json')['snapshots'], run_dir/'features',
        weather_records=read(run_dir/'weather_private.json'), now=utcnow())
    atomic_json(run_dir/'feature_receipt.json', result)
    return result


def prediction_stage(run_dir):
    try:
        from scripts import cp2_model as model
        from scripts import freeze_callback_prospective as prospective
    except ModuleNotFoundError:
        import cp2_model as model
        import freeze_callback_prospective as prospective
    _, bundle = model.current_bundle()
    path = run_dir/'features/predictors/dataset_input.json'
    rows = prospective.b.load_dataset_input(path)
    if rows.empty:
        atomic_json(run_dir/'predictions_receipt.json', {'scored_services': 0})
        return {'scored_services': 0}
    staged = run_dir/('scores_'+uuid.uuid4().hex+'.csv')
    result = model.predict(bundle, path, staged)
    os.replace(staged, run_dir/'scores_private.csv')
    result.pop('output', None)
    result['scores_sha256'] = digest(run_dir/'scores_private.csv')
    atomic_json(run_dir/'predictions_receipt.json', result)
    return result


def event_keys_for_anchors(run_dir, frame, *, mapping=False):
    if frame.empty:
        return {} if mapping else []
    old = read(ROOT/'outputs/cp2-v2/source_refresh_20260927/old_calendar_private.json')
    old_ids = {(row['calendar_id'], row['event_id']): row['calendar_event_row']
               for row in old['records']}
    calendar_rows = {}
    for row in read(run_dir/'calendar_private.json')['records']:
        identity = (row['calendar_id'], row['event_id'])
        encoded = json.dumps(identity, separators=(',', ':')).encode()
        stable_id = old_ids.get(identity, -int(hashlib.sha256(encoded).hexdigest()[:15], 16)-1)
        if stable_id in calendar_rows:
            raise ValueError('Current Calendar identity or stable ID duplicated')
        calendar_rows[stable_id] = row
    keys = {}
    for _, anchor in frame.iterrows():
        original = calendar_rows.get(int(anchor['anchor_event_row']))
        if original is None:
            raise ValueError('Scored anchor has no current Calendar event identity')
        identity = '|'.join([str(original['calendar_id']),str(original['event_id']),
                             str(original['start_raw']),str(original['end_raw'])])
        keys[int(anchor['anchor_event_row'])] = hashlib.sha256(identity.encode()).hexdigest()
    if len(keys) != len(frame) or len(set(keys.values())) != len(frame):
        raise ValueError('Multiple scored anchors share one Calendar event identity')
    return keys if mapping else sorted(keys.values())


def recheck_calendar_events(run_dir, selected):
    """Confirm selected Calendar records have not changed since pre-end fetch."""
    try:
        from scripts import load_calendar_bronze as calendar
    except ModuleNotFoundError:
        import load_calendar_bronze as calendar
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    targets = calendar._targets(calendar._local_path(os.getenv('NOMOBUG_GOOGLE_METADATA'),
        'data/profiles/google_source_metadata.json'))
    today = utcnow().astimezone(LOCAL).date()
    latest = {(row['calendar_id'],row['event_id']):row
              for row in calendar._fetch(targets, today, today)}
    if len(latest) < len(selected):
        raise ValueError('Post-end Calendar recheck inventory incomplete')
    raw = read(run_dir/'calendar_private.json')
    by_identity = {(row['calendar_id'],row['event_id']):row for row in raw['records']}
    old = read(ROOT/'outputs/cp2-v2/source_refresh_20260927/old_calendar_private.json')
    old_ids = {(row['calendar_id'],row['event_id']): row['calendar_event_row']
               for row in old['records']}
    by_row = {}
    for identity,row in by_identity.items():
        encoded = json.dumps(identity, separators=(',', ':')).encode()
        stable_id = old_ids.get(identity, -int(hashlib.sha256(encoded).hexdigest()[:15],16)-1)
        by_row[stable_id] = identity
    for _,anchor in selected.iterrows():
        identity = by_row.get(int(anchor['anchor_event_row']))
        prior = by_identity.get(identity)
        current = latest.get(identity)
        if not prior or not current or any(prior.get(field) != current.get(field)
                for field in calendar.FIELDS if field != 'calendar_event_row'):
            raise ValueError('Calendar service changed between feature snapshot and post-end verification')
    return {'verified_event_count':len(selected), 'rechecked_at_utc':utcnow().isoformat(),
            'calendar_inventory_count':len(latest)}


def prospective_stage(run_dir):
    import pandas as pd
    try:
        from scripts import cp2_model as model
        from scripts import freeze_callback_prospective as prospective
    except ModuleNotFoundError:
        import cp2_model as model
        import freeze_callback_prospective as prospective
    _, bundle = model.current_bundle()
    manifest, _ = prospective.load_bundle(bundle)
    existing_input = run_dir/'prospective_input/dataset_input.json'
    existing_receipt = run_dir/'prospective_source_receipt.json'
    if existing_receipt.exists():
        # A retry reuses immutable original inputs; never manufactures a new
        # prediction timestamp for an already committed record.
        result = prospective.score(bundle, existing_input, BASE/'prospective_logs',
            source_receipt=read(existing_receipt))
        result['logged_event_keys'] = event_keys_for_anchors(run_dir,
            prospective.b.load_dataset_input(existing_input))
        atomic_json(run_dir/'prospective_receipt.json', result)
        return result
    frame = prospective.b.load_dataset_input(run_dir/'features/predictors/dataset_input.json')
    now = utcnow()
    receipt = read(run_dir/'source_receipt.json')
    if (now-prospective.timestamp(receipt['extracted_at_utc'])).total_seconds() > MAX_SOURCE_AGE_SECONDS:
        raise ValueError('Source snapshot older than five minutes; begin a fresh run')
    result = {'logged_rows': 0, 'outcomes_available': False, 'cohort_start': manifest['cohort_start'],
        'cohort_end': manifest['cohort_end'], 'earliest_final_evaluation_date': manifest['earliest_final_evaluation_date']}
    if frame.empty:
        result['reason'] = 'no_matched_paid_service_anchors'
    else:
        start = pd.to_datetime(frame['service_start_at'], utc=True)
        finish = pd.to_datetime(frame['service_end_at'], utc=True)
        anchors = pd.to_datetime(frame['anchor_date']).dt.normalize()
        cohort = anchors.between(pd.Timestamp(manifest['cohort_start']), pd.Timestamp(manifest['cohort_end']))
        target_start = (anchors+pd.Timedelta(days=1)).dt.tz_localize(LOCAL).dt.tz_convert('UTC')
        eligible = cohort & finish.le(now) & finish.ge(now-timedelta(seconds=240)) & start.le(finish) & target_start.gt(now)
        result.update(cohort_anchors_in_refresh=int(cohort.sum()), eligible_now=int(eligible.sum()),
            past_cohort_anchors_outside_logging_gate=int((cohort & finish.le(now) & ~eligible).sum()))
        selected = frame.loc[eligible].copy()
        event_key_by_row = event_keys_for_anchors(run_dir, selected, mapping=True)
        keys_for_selected = sorted(event_key_by_row.values())
        recheck = recheck_calendar_events(run_dir, selected) if not selected.empty else None
        already = []
        bundle_sha = digest(bundle/'bundle.json')
        for index, row in selected.iterrows():
            canonical = [str(row['population']), str(row['sales_record_id']),
                pd.Timestamp(row['anchor_date']).strftime('%Y-%m-%dT00:00:00.000')]
            key = '|'.join(canonical)
            path = BASE/'prospective_logs'/(hashlib.sha256(key.encode()).hexdigest()+'.json')
            if path.exists():
                prior = read(path)
                bound = prior.get('source_receipt', {}).get('calendar_event_keys_by_prediction_key', {})
                if (prior.get('record_sha256') != prospective.record_digest(prior)
                        or prior.get('bundle_sha256') != bundle_sha
                        or bound.get(key) != event_key_by_row[int(row['anchor_event_row'])]):
                    raise ValueError('Prior prospective log integrity or model differs')
                already.append(index)
        result['already_logged_rows'] = len(already)
        selected = selected.drop(index=already)
        if not selected.empty:
            now = utcnow()
            selected['prediction_at'] = now.isoformat()
            source_time = prospective.timestamp(receipt['extracted_at_utc'])
            weather_time = prospective.timestamp(read(run_dir/'weather_receipt.json')['extracted_at_utc'])
            selected['feature_snapshot_at'] = max(source_time, weather_time).isoformat()
            prospective.b.persist_dataset_input(selected, run_dir/'prospective_input')
            input_path = run_dir/'prospective_input/dataset_input.json'
            evidence = dict(receipt, feature_input_sha256=digest(input_path),
                prediction_generated_at_utc=now.isoformat(), run_id=run_dir.name)
            evidence['post_end_calendar_recheck'] = recheck
            evidence['calendar_event_keys_by_prediction_key'] = {
                '|'.join([str(row['population']),str(row['sales_record_id']),
                    pd.Timestamp(row['anchor_date']).strftime('%Y-%m-%dT00:00:00.000')]):
                event_key_by_row[int(row['anchor_event_row'])] for _,row in selected.iterrows()}
            atomic_json(run_dir/'prospective_source_receipt.json', evidence)
            result.update(prospective.score(bundle, input_path, BASE/'prospective_logs', source_receipt=evidence))
        else:
            result['reason'] = 'no_service_inside_frozen_prospective_time_gate'
        result['logged_event_keys'] = keys_for_selected
    atomic_json(run_dir/'prospective_receipt.json', result)
    return result


def stage_callbacks():
    return dict(zip(STAGES, [source_stage, weather_stage, feature_stage, prediction_stage, prospective_stage]))


def artifacts(run_dir):
    return {str(path.relative_to(run_dir)): digest(path) for path in run_dir.rglob('*')
            if path.is_file() and path.name != 'run.json' and not path.name.endswith('.tmp')}


def publish_success(base, run_dir, state):
    """Idempotent publication; an older resumed run never replaces a newer one."""
    pointer = base/'last_success.json'
    latest = read(pointer) if pointer.exists() else None
    if latest and latest['run_id'] != state['run_id'] and datetime.fromisoformat(
            latest['finished_at_utc']) > datetime.fromisoformat(state['finished_at_utc']):
        return
    atomic_json(pointer, {'run_id': state['run_id'],
        'finished_at_utc': state['finished_at_utc'], 'run_manifest_sha256': digest(run_dir/'run.json'),
        'scored_services': state['stages']['predictions']['receipt'].get('scored_services', 0),
        'prospectively_logged': state['stages']['prospective']['receipt'].get('logged_rows', 0)})
    atomic_json(base/'last_attempt.json', {'run_id': state['run_id'], 'status': 'succeeded'})


def run(*, resume=None, callbacks=None, base=None, wait_until=None):
    base = private(base or BASE)
    callbacks = callbacks or stage_callbacks()
    with pipeline_lock(base):
        if resume:
            if not re.fullmatch(r'[A-Za-z0-9_-]+', resume):
                raise ValueError('Invalid run ID')
            run_dir = base/'runs'/resume
            state = read(run_dir/'run.json')
            for relative, expected in state.get('artifact_hashes', {}).items():
                if digest(run_dir/relative) != expected:
                    raise ValueError('Completed-stage artifact changed; resume refused')
            if state['status'] == 'succeeded':
                publish_success(base, run_dir, state)
                return state
            state['attempts'] += 1
        else:
            run_id = utcnow().strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
            run_dir = base/'runs'/run_id
            state = {'version': 1, 'run_id': run_id, 'started_at_utc': utcnow().isoformat(),
                'status': 'running', 'attempts': 1, 'stages': {}, 'artifact_hashes': {}}
        atomic_json(run_dir/'run.json', state)
        current = None
        try:
            for current in STAGES:
                if state['stages'].get(current, {}).get('status') == 'succeeded':
                    continue
                started = utcnow()
                state['status'] = 'running'
                state['stages'][current] = {'status': 'running', 'started_at_utc': started.isoformat()}
                atomic_json(run_dir/'run.json', state)
                if current == 'features' and wait_until is not None:
                    # The Calendar-only trigger can start source/weather work
                    # before a scheduled end, then derive only after that end.
                    target = datetime.fromisoformat(str(wait_until).replace('Z', '+00:00'))
                    if target.tzinfo is None or (target-utcnow()).total_seconds() > 180:
                        raise ValueError('Expected service end must be within three minutes')
                    while (target-utcnow()).total_seconds() > 0:
                        time.sleep(min(10, max(.05, (target-utcnow()).total_seconds())))
                result = callbacks[current](run_dir)
                state['stages'][current] = {'status': 'succeeded', 'started_at_utc': started.isoformat(),
                    'finished_at_utc': utcnow().isoformat(), 'receipt': result}
                state['artifact_hashes'] = artifacts(run_dir)
                atomic_json(run_dir/'run.json', state)
                print(json.dumps({'run_id': state['run_id'], 'completed_stage': current}), flush=True)
            state['status'] = 'succeeded'
            state['finished_at_utc'] = utcnow().isoformat()
            atomic_json(run_dir/'run.json', state)
            publish_success(base, run_dir, state)
            return state
        except (Exception, SystemExit) as error:
            state['status'] = 'failed'
            state['failed_stage'] = current
            state['finished_at_utc'] = utcnow().isoformat()
            state['error_type'] = type(error).__name__
            # Never put API bodies, source values or credentials in public output.
            state['stages'][current]['status'] = 'failed'
            state['artifact_hashes'] = artifacts(run_dir)
            atomic_json(run_dir/'run.json', state)
            atomic_json(base/'last_attempt.json', {'run_id': state['run_id'], 'status': 'failed',
                'failed_stage': current, 'error_type': type(error).__name__})
            print(json.dumps({'run_id': state['run_id'], 'status': 'failed', 'failed_stage': current,
                'error_type': type(error).__name__, 'last_success_preserved': True}), flush=True)
            raise


def status(base=None):
    base = private(base or BASE)
    result = {'last_success': read(base/'last_success.json') if (base/'last_success.json').exists() else None,
        'last_attempt': read(base/'last_attempt.json') if (base/'last_attempt.json').exists() else None,
        'prospective_logs': len(list((base/'prospective_logs').glob('*.json'))),
        'execution': 'local; Google source reads and temporary warehouse transformations'}
    if result['last_success']:
        last = result['last_success']
        if digest(base/'runs'/last['run_id']/'run.json') != last['run_manifest_sha256']:
            raise ValueError('Last successful manifest integrity changed')
        state = read(base/'runs'/last['run_id']/'run.json')
        for relative, expected in state['artifact_hashes'].items():
            if digest(base/'runs'/last['run_id']/relative) != expected:
                raise ValueError('Last successful artifact integrity changed')
    return result


def final_evaluation():
    """After full cohort maturity, refresh source-derived labels and score once."""
    try:
        from scripts import cp2_model as model
        from scripts import freeze_callback_prospective as prospective
    except ModuleNotFoundError:
        import cp2_model as model
        import freeze_callback_prospective as prospective
    _, bundle = model.current_bundle()
    manifest, _ = prospective.load_bundle(bundle)
    if utcnow().astimezone(LOCAL).date() < datetime.fromisoformat(
            manifest['earliest_final_evaluation_date']).date():
        raise ValueError('Future cohort 30-day outcomes are not complete yet')
    if (bundle/'prospective_evaluation.json').exists():
        raise ValueError('One-time final future evaluation already recorded')
    state = run()
    run_dir = BASE/'runs'/state['run_id']
    mature_input = run_dir/'features/mature_labels/dataset_input.json'
    source = read(run_dir/'source_receipt.json')
    features = read(run_dir/'feature_receipt.json')
    if source['complete_outcomes_through'] != features['complete_outcomes_through']:
        raise ValueError('Complete Calendar day watermarks differ')
    evidence = dict(source, feature_input_sha256=digest(mature_input),
        source_extraction_min_at_utc=source['earliest_extraction_at_utc'],
        source_extraction_max_at_utc=source['extracted_at_utc'])
    path = run_dir/'prospective_labels_private.json'
    prepared = prospective.prepare_labels(bundle, mature_input, evidence, path)
    evaluated = prospective.evaluate(bundle, path, BASE/'prospective_logs')
    return {'cohort_anchors': prepared['complete_cohort_anchors'],
        'source_run_id': state['run_id'], 'evaluation_rows': evaluated['rows'],
        'result_path': str(bundle/'prospective_evaluation.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['run', 'resume', 'status', 'final-evaluation'])
    parser.add_argument('--run-id')
    args = parser.parse_args()
    if args.mode == 'status':
        result = status()
    elif args.mode == 'final-evaluation':
        result = final_evaluation()
    else:
        if args.mode == 'resume' and not args.run_id:
            parser.error('resume requires --run-id')
        try:
            state = run(resume=args.run_id if args.mode == 'resume' else None)
        except (Exception, SystemExit):
            raise SystemExit('Pipeline failed; inspect private run.json. Last successful publication remains available.') from None
        result = {'run_id': state['run_id'], 'status': state['status'],
                  'stages': {name: value['receipt'] for name, value in state['stages'].items()}}
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
