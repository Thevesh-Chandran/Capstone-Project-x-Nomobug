from datetime import date
from copy import deepcopy
from types import SimpleNamespace
import pytest
from google.auth.exceptions import RefreshError
import pandas as pd
from scripts import refresh_callback_validation as r
from scripts import load_calendar_bronze as loader


def row(identifier,index):
    result={field:None for field in loader.FIELDS}
    result.update(calendar_id='approved',event_id=identifier,calendar_event_row=index,
        is_all_day=False,status='confirmed',summary='service',description='old')
    return result


def snapshot(records):
    return {'metadata':{'window_start':'2000-01-01','window_end':'2026-09-27',
        'calendar_count':1,'extracted_at':'2026-09-27T06:00:00+00:00'},'records':records}


def test_maturity_uses_last_complete_local_day():
    assert r.complete_through(snapshot([])['metadata'])==date(2026,9,26)
    metadata=snapshot([])['metadata'];metadata['extracted_at']='2026-09-26T23:59:00+00:00'
    assert r.complete_through(metadata)==date(2026,9,26)
    metadata['window_end']='2026-09-20'
    assert r.complete_through(metadata)==date(2026,9,20)


def test_naive_source_extraction_time_is_rejected():
    metadata=snapshot([])['metadata'];metadata['extracted_at']='2026-09-27T06:00:00'
    with pytest.raises(ValueError,match='timezone'):r.complete_through(metadata)


def test_delta_preserves_review_ids_and_invalidates_changed_geocodes():
    old=snapshot([row('reviewed',10),row('removed',20)])
    changed=row('reviewed',1);changed['description']='new address'
    new=snapshot([changed,row('new',2)])
    delta,replaced,invalid,summary=r.source_delta(old,new)
    mapping={item['event_id']:item['calendar_event_row'] for item in delta}
    assert mapping=={'reviewed':10,'new':21}
    assert set(replaced)=={10,20};assert invalid==[10]
    assert summary['new_event_ids']==1 and summary['absent_event_ids']==1
    assert old['records'][0]['description']=='old'


def test_ordinal_changes_are_not_source_changes():
    old=snapshot([row('a',10),row('b',20)])
    new=snapshot([row('b',1),row('a',2)])
    assert r.source_delta(old,new)[0]==[]


def test_duplicate_or_different_source_inventory_rejected():
    old=snapshot([row('a',1)])
    with pytest.raises(ValueError,match='Duplicate'):r.source_delta(old,snapshot([row('a',1),row('a',2)]))
    changed=deepcopy(old);changed['records'][0]['calendar_id']='unapproved'
    with pytest.raises(ValueError,match='inventory'):r.source_delta(old,changed)


def test_expired_access_reports_recovery_without_traceback(monkeypatch):
    def failed(_):raise RefreshError('expired private grant')
    credential=SimpleNamespace(valid=False,expired=True,refresh_token=True,refresh=failed)
    monkeypatch.setattr(loader.Credentials,'from_authorized_user_file',lambda *args:credential)
    with pytest.raises(SystemExit,match='renew_google_access.py'):loader._credentials()


def test_replay_tolerates_only_machine_float_noise_not_label_or_history_changes():
    a=pd.DataFrame({'population':['p'],'sales_record_id':['s'],'anchor_date':['2026-08-15'],
        'rain_trend':[0.],'count':[2],'target':[True]})
    z=a.copy();z['rain_trend']=8.88e-16
    assert r.compare_replay(a,z)['floating_variations']['rain_trend']==8.88e-16
    z['count']=3
    with pytest.raises(ValueError,match='count features'):r.compare_replay(a,z)
    z=a.copy();z['rain_trend']=1e-5
    with pytest.raises(ValueError,match='numeric features'):r.compare_replay(a,z)
    z=a.copy();z['target']=False
    with pytest.raises(ValueError,match='labels'):r.compare_replay(a,z)
