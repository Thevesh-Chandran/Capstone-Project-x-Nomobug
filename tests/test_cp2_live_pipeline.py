"""Operational recovery and source-boundary regressions, without live APIs."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import pandas as pd

from scripts import callback_live_weather as weather
from scripts import cp2_pipeline as pipe
from scripts import cp2_pipeline_tick as tick


def callbacks(fail=None):
    def stage(name):
        def execute(run_dir):
            if name == fail:
                raise RuntimeError('transient API error with sensitive body')
            (run_dir/f'{name}.txt').write_text(name)
            if name == 'predictions':
                return {'scored_services': 1}
            if name == 'prospective':
                return {'logged_rows': 0}
            return {'rows': 1}
        return execute
    return {name: stage(name) for name in pipe.STAGES}


def test_failed_refresh_preserves_last_success_and_resumes_without_repeating_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, 'ROOT', tmp_path)
    base = tmp_path/'outputs/live'
    first = pipe.run(base=base, callbacks=callbacks())
    published = pipe.read(base/'last_success.json')
    assert published['run_id'] == first['run_id']
    with pytest.raises(RuntimeError):
        pipe.run(base=base, callbacks=callbacks('features'))
    failed = pipe.read(base/'last_attempt.json')
    assert failed['failed_stage'] == 'features'
    assert pipe.read(base/'last_success.json') == published
    invoked = []
    recovery = callbacks()
    for name in ('sources', 'weather'):
        recovery[name] = lambda run_dir, name=name: invoked.append(name)
    second = pipe.run(base=base, callbacks=recovery, resume=failed['run_id'])
    assert second['status'] == 'succeeded' and second['attempts'] == 2
    assert invoked == []
    assert pipe.status(base)['last_success']['run_id'] == failed['run_id']


def test_published_artifact_tampering_is_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, 'ROOT', tmp_path)
    base = tmp_path/'outputs/live'
    state = pipe.run(base=base, callbacks=callbacks())
    (base/'runs'/state['run_id']/'sources.txt').write_text('tampered')
    with pytest.raises(ValueError, match='integrity'):
        pipe.status(base)
    with pytest.raises(ValueError, match='artifact changed'):
        pipe.run(base=base, callbacks=callbacks(), resume=state['run_id'])


def test_customer_artifacts_cannot_be_published_outside_ignored_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='ignored outputs'):
        pipe.run(base=tmp_path/'public', callbacks=callbacks())


def test_weather_response_retains_missing_values_and_rejects_partial_dates():
    location = {'latitude': 3.1, 'longitude': 101.6}
    payload = {'timezone': 'Asia/Kuala_Lumpur', 'daily': {
        'time': ['2026-09-27'],
        'temperature_2m_mean': [None],
        'precipitation_sum': [2.5],
        'rain_sum': [2.5],
        'relative_humidity_2m_mean': [70.0],
        'soil_moisture_0_to_7cm_mean': [0.25],
    }}
    date = datetime(2026, 9, 27).date()
    row = weather.parse_batch(payload, [location], date, date)[0]
    assert row['temperature_2m_mean_c'] is None
    assert row['precipitation_sum_mm'] == 2.5
    with pytest.raises(ValueError, match='dates/timezone'):
        weather.parse_batch(payload, [location], date-timedelta(days=1), date)


def test_trigger_only_follows_just_finished_timed_service():
    now = datetime(2026, 9, 28, 2, 0, tzinfo=timezone.utc)
    service = {'calendar_id': 'a', 'event_id': 'opaque', 'summary': 'GPC 1/3',
        'status': 'confirmed', 'is_all_day': False,
        'start_raw': (now-timedelta(hours=2)).isoformat(),
        'end_raw': (now-timedelta(minutes=2)).isoformat()}
    assert tick.timed_service(service, now)
    assert tick.timed_service(service|{'summary': 'GPC 1/1 NO WARRANTY'}, now)
    assert tick.timed_service(service|{'summary': 'GPC 1/1 WITHOUT WARRANTY'}, now)
    assert not tick.timed_service(service|{'summary': 'GPC 4/3 warranty'}, now)
    assert not tick.timed_service(service|{'status': 'cancelled'}, now)
    assert not tick.timed_service(service|{'end_raw': (now-timedelta(minutes=5)).isoformat()}, now)
    assert tick.timed_service(service|{'end_raw': (now+timedelta(minutes=1)).isoformat()}, now)
    assert not tick.timed_service(service|{'end_raw': (now+timedelta(minutes=3)).isoformat()}, now)


def test_poll_failure_keeps_event_retryable_and_success_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, 'ROOT', tmp_path)
    monkeypatch.setattr(tick.pipeline, 'ROOT', tmp_path)
    bundle = tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    (bundle/'bundle.json').write_text(json.dumps({'cohort_start':'2026-09-28','cohort_end':'2026-10-27'}))
    monkeypatch.setattr(tick.cp2_model, 'current_bundle', lambda: ({}, bundle))
    now = datetime(2026, 9, 28, 2, 0, tzinfo=timezone.utc)
    one = {'calendar_id':'a','event_id':'opaque','summary':'GPC 1/3','status':'confirmed',
        'is_all_day':False,'start_raw':(now-timedelta(hours=2)).isoformat(),
        'end_raw':(now-timedelta(minutes=1)).isoformat()}
    base = tmp_path/'outputs/live'
    def broken(**kwargs):
        raise RuntimeError('temporary')
    failed = tick.poll(now, fetch=lambda:[one], run=broken, base=base)
    assert failed['status'] == 'refresh_failed'
    assert pipe.read(base/'watch_events.json')['processed'] == []
    good = lambda **kwargs: {'run_id':'opaque', 'stages':{'prospective':{'receipt':{
        'logged_rows':1,'logged_event_keys':[tick.event_key(one)]}}}}
    passed = tick.poll(now, fetch=lambda:[one], run=good, base=base)
    assert passed['status'] == 'refresh_succeeded'
    idle = tick.poll(now, fetch=lambda:[one], run=broken, base=base)
    assert idle['status'] == 'idle'


def test_trigger_does_not_mark_unlogged_service_processed(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, 'ROOT', tmp_path)
    bundle = tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    (bundle/'bundle.json').write_text(json.dumps({'cohort_start':'2026-09-28','cohort_end':'2026-10-27'}))
    monkeypatch.setattr(tick.cp2_model, 'current_bundle', lambda: ({}, bundle))
    now = datetime(2026, 9, 28, 2, 0, tzinfo=timezone.utc)
    event = {'calendar_id':'a','event_id':'opaque','summary':'GPC 1/3','status':'confirmed',
        'is_all_day':False,'start_raw':(now-timedelta(hours=2)).isoformat(),
        'end_raw':(now+timedelta(minutes=1)).isoformat()}
    base = tmp_path/'outputs/live'
    missed = lambda **kwargs: {'run_id':'opaque','stages':{'prospective':{'receipt':{'logged_rows':0}}}}
    first = tick.poll(now, fetch=lambda:[event], run=missed, base=base)
    assert first['status'] == 'refresh_without_complete_prospective_logging'
    assert tick.poll(now+timedelta(minutes=2), fetch=lambda:[event], run=missed, base=base)['full_refresh_started']
    final = tick.poll(now+timedelta(minutes=7), fetch=lambda:[], run=missed, base=base)
    assert final['missed_event_windows'] == 1


def test_unrelated_logged_anchor_cannot_acknowledge_another_event(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, 'ROOT', tmp_path)
    bundle = tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    (bundle/'bundle.json').write_text(json.dumps({'cohort_start':'2026-09-28','cohort_end':'2026-10-27'}))
    monkeypatch.setattr(tick.cp2_model, 'current_bundle', lambda: ({}, bundle))
    now=datetime(2026,9,28,2,0,tzinfo=timezone.utc)
    one={'calendar_id':'a','event_id':'due','summary':'GPC 1/3','status':'confirmed',
        'is_all_day':False,'start_raw':(now-timedelta(hours=1)).isoformat(),
        'end_raw':(now-timedelta(minutes=1)).isoformat()}
    unrelated = lambda **kwargs: {'run_id':'other', 'stages':{'prospective':{'receipt':{
        'logged_rows':1,'logged_event_keys':['f'*64]}}}}
    base=tmp_path/'outputs/live'
    result=tick.poll(now,fetch=lambda:[one],run=unrelated,base=base)
    assert result['status']=='refresh_without_complete_prospective_logging'
    assert pipe.read(base/'watch_events.json')['processed']==[]


def test_missed_window_is_recorded_even_if_no_tick_saw_it_due(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, 'ROOT', tmp_path)
    bundle = tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    (bundle/'bundle.json').write_text(json.dumps({'cohort_start':'2026-09-28','cohort_end':'2026-10-27'}))
    monkeypatch.setattr(tick.cp2_model, 'current_bundle', lambda: ({}, bundle))
    now = datetime(2026,9,28,2,0,tzinfo=timezone.utc)
    event = {'calendar_id':'a','event_id':'missed','summary':'GPC 1/1 NO WARRANTY',
        'status':'confirmed','is_all_day':False,
        'start_raw':(now-timedelta(hours=2)).isoformat(),
        'end_raw':(now-timedelta(minutes=20)).isoformat()}
    base=tmp_path/'outputs/live'
    def should_not_run(**kwargs):
        raise AssertionError('A missed appointment cannot become a late prediction')
    first=tick.poll(now,fetch=lambda:[event],run=should_not_run,base=base)
    assert first['status']=='idle' and first['coverage_status']=='incomplete'
    assert first['newly_missed_event_windows']==1 and first['missed_event_windows']==1
    assert tick.event_key(event) in pipe.read(base/'watch_events.json')['missed']
    second=tick.poll(now+timedelta(minutes=2),fetch=lambda:[event],run=should_not_run,base=base)
    assert second['newly_missed_event_windows']==0 and second['missed_event_windows']==1


def test_task_exit_code_distinguishes_new_miss_from_historical_coverage(monkeypatch, capsys):
    result = {'status': 'idle', 'coverage_status': 'incomplete',
              'missed_event_windows': 8, 'newly_missed_event_windows': 0}
    monkeypatch.setattr(tick, 'poll', lambda: result)
    assert tick.main() == 0
    result['newly_missed_event_windows'] = 1
    assert tick.main() == 1
    result.update(status='refresh_failed', newly_missed_event_windows=0)
    assert tick.main() == 1
    capsys.readouterr()


def test_previous_day_gap_is_fetched_for_missed_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, 'ROOT', tmp_path)
    bundle = tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    (bundle/'bundle.json').write_text(json.dumps({'cohort_start':'2026-09-28','cohort_end':'2026-10-27'}))
    monkeypatch.setattr(tick.cp2_model, 'current_bundle', lambda: ({}, bundle))
    base=tmp_path/'outputs/live'
    first=datetime(2026,9,28,2,0,tzinfo=timezone.utc)
    assert tick.poll(first,fetch=lambda:[],base=base)['missed_event_windows']==0
    next_day=first+timedelta(days=1)
    event={'calendar_id':'a','event_id':'yesterday','summary':'GPC 1/3',
        'status':'confirmed','is_all_day':False,
        'start_raw':(first+timedelta(hours=1)).isoformat(),
        'end_raw':(first+timedelta(hours=3)).isoformat()}
    result=tick.poll(next_day,fetch=lambda:[event],base=base)
    assert result['missed_event_windows']==1 and result['newly_missed_event_windows']==1


def test_log_commit_before_watch_update_recovers_exact_event_ack(tmp_path, monkeypatch):
    from scripts.freeze_callback_prospective import record_digest
    monkeypatch.setattr(pipe, 'ROOT', tmp_path)
    bundle=tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    (bundle/'bundle.json').write_text(json.dumps({'cohort_start':'2026-09-28','cohort_end':'2026-10-27'}))
    monkeypatch.setattr(tick.cp2_model, 'current_bundle', lambda: ({}, bundle))
    now=datetime(2026,9,28,2,0,tzinfo=timezone.utc)
    event={'calendar_id':'a','event_id':'committed','summary':'GPC 1/1 NO WARRANTY',
        'status':'confirmed','is_all_day':False,
        'start_raw':(now-timedelta(hours=2)).isoformat(),
        'end_raw':(now-timedelta(minutes=20)).isoformat()}
    base=tmp_path/'outputs/live'
    row={'population':'matched_packages_recorded_callback_30d',
         'sales_record_id':'sale-opaque','anchor_date':'2026-09-28T00:00:00.000'}
    prediction_key='|'.join(str(row[field]) for field in
                            ('population','sales_record_id','anchor_date'))
    entry={'schema_version':2,'bundle_sha256':pipe.digest(bundle/'bundle.json'),
           'row':row,'label_status':'awaiting_calendar_30d_outcome',
           'source_receipt':{'source':'Google Calendar + Google Sheets',
               'snapshot_sha256':'a'*64,'feature_input_sha256':'b'*64,
               'post_end_calendar_recheck':{'verified_event_count':1},
               'calendar_event_keys_by_prediction_key':{
                   prediction_key:tick.event_key(event)}}}
    entry['record_sha256']=record_digest(entry)
    log=base/'prospective_logs'/(hashlib.sha256(prediction_key.encode()).hexdigest()+'.json')
    pipe.atomic_json(log,entry)
    result=tick.poll(now,fetch=lambda:[event],base=base)
    assert result['missed_event_windows']==0 and result['full_refresh_started'] is False
    assert tick.event_key(event) in pipe.read(base/'watch_events.json')['processed']
    # A different Calendar appointment cannot borrow this sale/date log.
    different=dict(event,event_id='not-committed')
    next_result=tick.poll(now+timedelta(minutes=2),fetch=lambda:[different],base=base)
    assert next_result['missed_event_windows']==1


def test_anchor_calendar_identity_binding_and_post_end_change_detection(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, 'ROOT', tmp_path)
    private = tmp_path/'outputs/cp2-v2/source_refresh_20260927'
    private.mkdir(parents=True)
    old = {'records': []}
    pipe.atomic_json(private/'old_calendar_private.json',old)
    run_dir = tmp_path/'outputs/live/runs/test';run_dir.mkdir(parents=True)
    event = {'calendar_id':'calendar','event_id':'one','status':'confirmed',
             'start_raw':'2026-09-28T10:00:00+08:00',
             'end_raw':'2026-09-28T11:00:00+08:00',
             'summary':'GPC 1/3','description':'address','location':''}
    pipe.atomic_json(run_dir/'calendar_private.json',{'records':[event]})
    import hashlib
    stable = -int(hashlib.sha256(json.dumps(('calendar','one'),separators=(',',':')).encode()).hexdigest()[:15],16)-1
    frame = pd.DataFrame([{'anchor_event_row':stable}])
    actual = pipe.event_keys_for_anchors(run_dir,frame)
    assert actual == [tick.event_key(event)]
    changed = dict(event, start_raw='2026-09-28T10:30:00+08:00')
    assert tick.event_key(changed) != actual[0]
    from scripts import load_calendar_bronze as calendar
    monkeypatch.setattr(calendar,'_targets',lambda metadata:[{'id':'calendar'}])
    monkeypatch.setattr(calendar,'_local_path',lambda *args:tmp_path/'not-used')
    monkeypatch.setattr(calendar,'_fetch',lambda *args:[event])
    assert pipe.recheck_calendar_events(run_dir,frame)['verified_event_count']==1
    monkeypatch.setattr(calendar,'_fetch',lambda *args:[changed])
    with pytest.raises(ValueError, match='changed between'):
        pipe.recheck_calendar_events(run_dir,frame)
