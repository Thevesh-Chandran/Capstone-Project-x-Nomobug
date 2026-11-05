"""Prospective timing regressions: no late scores, invented outcomes or erased gaps."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts import cp2_collection_policy as policy
from scripts import cp2_pipeline as pipe, cp2_pipeline_tick as tick
from scripts import freeze_callback_prospective as prospective


def protocol_fixture(root):
    protocol = {'schema_version':1,'name':policy.NAME,'timing_policy':policy.TIMING,
        'target':'recorded_corrective_calendar_callback_within_30d','date_authority':'Calendar',
        'bundle_sha256':'a'*64,'declared_at_utc':'2026-10-09T01:00:00+00:00',
        'cohort_start':'2026-10-10','cohort_end':'2026-10-27'}
    protocol['record_sha256'] = policy.record_digest(protocol)
    raw = json.dumps(protocol).encode()
    config = root/'config';config.mkdir(exist_ok=True)
    (config/'cp2_october10_cohort.json').write_bytes(raw)
    (config/'cp2_model_current.json').write_text(json.dumps({'bundle_sha256':'a'*64,
        'october10_cohort_protocol_sha256':sha256(raw).hexdigest()}))
    return policy.load(root)


def test_protocol_must_be_declared_and_hash_bound(tmp_path):
    protocol_fixture(tmp_path)
    path = tmp_path/'config/cp2_october10_cohort.json'
    path.write_text(path.read_text().replace('23', '24')+' ')
    with pytest.raises(ValueError,match='integrity'):
        policy.load(tmp_path)


def test_extended_october_protocol_admits_last_day_but_not_next_day(tmp_path,monkeypatch):
    from pathlib import Path
    source = Path(__file__).resolve().parents[1]
    root = tmp_path
    monkeypatch.setattr(prospective.b,'ROOT',root)
    config=root/'config';config.mkdir()
    bundle=root/'bundle';bundle.mkdir()
    manifest={'cohort_start':'2026-09-28','cohort_end':'2026-10-27',
        'earliest_final_evaluation_date':'2026-11-27',
        'frozen_at_utc':'2026-09-27T09:00:00+00:00',
        'target':'recorded_corrective_calendar_callback_within_30d'}
    (bundle/'bundle.json').write_text(json.dumps(manifest))
    declared=json.loads((source/'config/cp2_october10_cohort.json').read_text())
    declared['bundle_sha256']=prospective.digest(bundle/'bundle.json')
    declared['record_sha256']=policy.record_digest(declared)
    path=config/'cp2_october10_cohort.json';path.write_text(json.dumps(declared))
    (config/'cp2_model_current.json').write_text(json.dumps({'bundle_sha256':declared['bundle_sha256'],
        'october10_cohort_protocol_sha256':prospective.digest(path)}))
    protocol=policy.load(root)
    contract = prospective.cohort_contract(bundle,manifest,root/'config/cp2_october10_cohort.json')
    assert contract['cohort_end'] == '2026-10-30'
    assert contract['earliest_final_evaluation_date'] == '2026-11-30'
    assert manifest['cohort_end'] == '2026-10-27'  # frozen original is unchanged
    now = policy.timestamp('2026-10-30T15:02:00+08:00')
    frame = pd.DataFrame([{'anchor_date':pd.Timestamp('2026-10-30'),
        'service_start_at':'2026-10-30T13:00:00+08:00','service_end_at':'2026-10-30T15:00:00+08:00',
        'prediction_at':now.isoformat(),'feature_snapshot_at':now.isoformat()}])
    prospective.validate_prediction_times(frame,manifest,now,collection_protocol=protocol)
    with pytest.raises(ValueError,match='outside'):
        prospective.validate_prediction_times(frame,manifest,now)
    next_day = frame.copy()
    next_day['anchor_date'] = pd.Timestamp('2026-10-31')
    with pytest.raises(ValueError,match='outside'):
        prospective.validate_prediction_times(next_day,manifest,now,collection_protocol=protocol)
    for change in ({'cohort_end':'2026-10-31'},{'earliest_final_evaluation_date':'2026-11-29'}):
        changed=declared | change
        changed['record_sha256']=policy.record_digest(changed)
        path.write_text(json.dumps(changed))
        (config/'cp2_model_current.json').write_text(json.dumps({'bundle_sha256':changed['bundle_sha256'],
            'october10_cohort_protocol_sha256':prospective.digest(path)}))
        with pytest.raises(ValueError,match='contract differs'):
            prospective.cohort_contract(bundle,manifest,path)


def test_poll_fetches_services_on_extended_last_day(tmp_path,monkeypatch):
    protocol = protocol_fixture(tmp_path)
    protocol = dict(protocol,cohort_end='2026-10-30')
    monkeypatch.setattr(policy,'load',lambda root:protocol)
    monkeypatch.setattr(pipe,'ROOT',tmp_path)
    bundle=tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    (bundle/'bundle.json').write_text(json.dumps({'cohort_start':'2026-09-28','cohort_end':'2026-10-27'}))
    monkeypatch.setattr(tick.cp2_model,'current_bundle',lambda:({},bundle))
    event={'calendar_id':'c','event_id':'e','status':'confirmed','summary':'GPC 1/3','is_all_day':False,
        'start_raw':'2026-10-30T13:00:00+08:00','end_raw':'2026-10-30T14:00:00+08:00'}
    result=tick.poll(policy.timestamp('2026-10-30T14:01:00+08:00'),fetch=lambda:[event],
        run=lambda **kwargs:{'run_id':'test','stages':{'prospective':{'receipt':{'logged_rows':0,
            'logged_event_keys':[],'eligible_anchor_event_keys':[],
            'event_decisions':{tick.event_key(event):'package_sequence_mismatch'}}}}},
        base=tmp_path/'outputs/live')
    assert result['full_refresh_started'] is True


@pytest.mark.parametrize('start', ['2026-10-10T23:30:00+08:00','2026-10-10T23:55:00+08:00'])
def test_overnight_is_saved_before_outcomes_including_late_start(tmp_path,start):
    protocol = protocol_fixture(tmp_path)
    end = '2026-10-11T01:00:00+08:00'
    capture = policy.capture_at(start,end,protocol)
    assert capture == policy.timestamp('2026-10-10T23:45:00+08:00')
    policy.validate_times(start,end,capture+timedelta(minutes=1),capture+timedelta(minutes=2),protocol)
    with pytest.raises(ValueError,match='five minutes'):
        policy.validate_times(start,end,capture+timedelta(minutes=1),capture+timedelta(minutes=6),protocol)
    with pytest.raises(ValueError,match='five minutes'):
        policy.validate_times(start,end,policy.timestamp('2026-10-11T01:01:00+08:00'),
            policy.timestamp('2026-10-11T01:02:00+08:00'),protocol)


def test_prior_protocol_and_daytime_end_remain_unchanged(tmp_path):
    protocol = protocol_fixture(tmp_path)
    assert policy.capture_at('2026-10-09T23:30:00+08:00','2026-10-10T01:00:00+08:00',protocol) == policy.timestamp('2026-10-10T01:00:00+08:00')
    end = policy.timestamp('2026-10-10T15:00:00+08:00')
    assert policy.capture_at('2026-10-10T13:00:00+08:00',end,protocol) == end


def test_trigger_and_validator_share_new_capture_window(tmp_path,monkeypatch):
    protocol = protocol_fixture(tmp_path)
    start='2026-10-10T23:55:00+08:00';end='2026-10-11T01:00:00+08:00'
    event={'status':'confirmed','summary':'GPC 1/3','is_all_day':False,'start_raw':start,'end_raw':end}
    now=policy.timestamp('2026-10-10T23:44:00+08:00')
    assert tick.timed_service(event,now,protocol)
    assert not tick.timed_service(event,now)
    frame=pd.DataFrame([{'anchor_date':pd.Timestamp('2026-10-10'),'service_start_at':start,
        'service_end_at':end,'feature_snapshot_at':now.isoformat(),
        'prediction_at':(now+timedelta(minutes=2)).isoformat()}])
    manifest={'cohort_start':'2026-09-28','cohort_end':'2026-10-27','frozen_at_utc':'2026-09-27T09:00:00+00:00'}
    prospective.validate_prediction_times(frame,manifest,now+timedelta(minutes=3),collection_protocol=protocol)
    with pytest.raises(ValueError,match='service end'):
        prospective.validate_prediction_times(frame,manifest,now+timedelta(minutes=3))


def test_source_exclusion_is_not_acknowledged_as_prediction_or_erased_miss(tmp_path,monkeypatch):
    monkeypatch.setattr(pipe,'ROOT',tmp_path)
    bundle=tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    (bundle/'bundle.json').write_text(json.dumps({'cohort_start':'2026-09-28','cohort_end':'2026-10-27'}))
    monkeypatch.setattr(tick.cp2_model,'current_bundle',lambda:({},bundle))
    now=policy.timestamp('2026-10-09T14:01:00+08:00')
    event={'calendar_id':'c','event_id':'e','status':'confirmed','summary':'GPC 1/3','is_all_day':False,
        'start_raw':'2026-10-09T13:00:00+08:00','end_raw':'2026-10-09T14:00:00+08:00'}
    key=tick.event_key(event);base=tmp_path/'outputs/live'
    run=lambda **kwargs:{'run_id':'test','stages':{'prospective':{'receipt':{'logged_rows':0,
        'logged_event_keys':[],'eligible_anchor_event_keys':[],
        'event_decisions':{key:'package_sequence_mismatch'}}}}}
    result=tick.poll(now,fetch=lambda:[event],run=run,base=base)
    assert result['status']=='refresh_completed_with_source_exclusions'
    assert pipe.read(base/'watch_events.json')['processed']==[]
    result=tick.poll(now+timedelta(minutes=8),fetch=lambda:[event],base=base)
    assert pipe.read(base/'watch_events.json')['missed'][key]==policy.timestamp(event['end_raw']).isoformat()
    assert result['missed_candidate_reason_counts']=={'package_sequence_mismatch':1}


def test_overnight_candidate_does_not_become_missed_at_actual_end_after_timely_ack(tmp_path,monkeypatch):
    protocol_fixture(tmp_path)
    monkeypatch.setattr(pipe,'ROOT',tmp_path)
    bundle=tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    (bundle/'bundle.json').write_text(json.dumps({'cohort_start':'2026-09-28','cohort_end':'2026-10-27'}))
    monkeypatch.setattr(tick.cp2_model,'current_bundle',lambda:({},bundle))
    now=policy.timestamp('2026-10-10T23:44:00+08:00')
    event={'calendar_id':'c','event_id':'e','status':'confirmed','summary':'GPC 1/3','is_all_day':False,
        'start_raw':'2026-10-10T23:55:00+08:00','end_raw':'2026-10-11T01:00:00+08:00'}
    key=tick.event_key(event);base=tmp_path/'outputs/live'
    run=lambda **kwargs:{'run_id':'test','stages':{'prospective':{'receipt':{'logged_rows':1,
        'logged_event_keys':[key],'eligible_anchor_event_keys':[key]}}}}
    assert tick.poll(now,fetch=lambda:[event],run=run,base=base)['status']=='refresh_succeeded'
    result=tick.poll(policy.timestamp('2026-10-11T01:10:00+08:00'),fetch=lambda:[event],base=base)
    assert result['october10_cohort_missed_eligible_windows']==0
    assert result['october10_cohort_coverage_status']=='complete_so_far'
