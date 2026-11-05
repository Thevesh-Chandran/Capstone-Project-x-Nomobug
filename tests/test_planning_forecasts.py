"""Forecast receipts must reject late/mismatched evidence; UI cannot invent results."""
import copy,json
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scripts.cp2_planning_job import due_origin,timely,evaluate,event_frame,fit_forecasts
from webapp import planning

TZ=ZoneInfo('Asia/Kuala_Lumpur')
ROOT=Path(__file__).resolve().parents[1]

def receipt():
    return {'protocol_sha256':'abc','origin':'2026-10-26T00:00:00+08:00',
      'source_started_at':'2026-10-25T23:50:00+08:00','issued_at':'2026-10-25T23:52:00+08:00',
      'forecasts':[{'id':'booking_entries_h2','target':'booking_entries','prediction':10,'baseline':11,'window_end':'2026-11-09T00:00:00+08:00'}]}

@pytest.mark.parametrize('when,valid',[('2026-10-25T23:50:00+08:00',True),('2026-10-26T00:01:00+08:00',False),('2026-10-21T23:50:00+08:00',False),('2026-10-25T23:20:00+08:00',False)])
def test_only_preweek_window_can_enrol(when,valid):assert bool(due_origin(datetime.fromisoformat(when))) is valid

def test_server_commit_time_not_client_timestamp_decides_timeliness():
    r=receipt()
    assert timely(r,'2026-10-25T23:53:00+08:00','abc')
    assert not timely(r,'2026-10-26T00:00:01+08:00','abc')
    assert not timely(r,'2026-10-25T23:53:00+08:00','changed')
    r['source_started_at']='2026-10-25T06:00:00+08:00'
    assert not timely(r,'2026-10-25T23:53:00+08:00','abc')

def sample_events():
    base={'calendar_id':'test','status':'confirmed','summary':'GPC 1/3 Example',
      'start_raw':'2026-10-26T09:00:00+08:00','end_raw':'2026-10-26T10:30:00+08:00',
      'created_raw':'2026-10-20T00:00:00Z','updated_raw':'2026-10-20T00:00:00Z','is_all_day':False}
    cancelled={**base,'event_id':'cancelled','summary':'CANCELLED GPC 1/3 Example'}
    sunday={**base,'event_id':'sunday','start_raw':'2026-11-01T09:00:00+08:00','end_raw':'2026-11-01T10:30:00+08:00'}
    return [{**base,'event_id':'a'},cancelled,sunday]

def test_outcomes_exclude_cancelled_but_not_all_sundays_and_wait_for_revision_buffer():
    r=receipt();events=sample_events();created='2026-10-25T23:53:00+08:00'
    assert evaluate(r,created,events,datetime.fromisoformat('2026-11-10T00:00:00+08:00'),'abc')==[]
    result=evaluate(r,created,events,datetime.fromisoformat('2026-11-12T00:00:00+08:00'),'abc')
    assert result[0]['actual']==2
    with pytest.raises(ValueError):evaluate(r,'2026-10-26T01:00:00+08:00',events,datetime.fromisoformat('2026-11-12T00:00:00+08:00'),'abc')

def test_portal_rejects_protocol_mismatch_without_hiding_research(tmp_path):
    (tmp_path/'planning_forecast.json').write_text(json.dumps({'version':'planning_v1','protocol_sha256':'tampered','updated_at':'2026-10-21T00:00:00Z'}))
    value=planning.load(tmp_path)
    assert len(value['evidence']['models'])==2
    assert value['live']['status']=='not_connected'
    assert value['live']['forecasts']==[]

@pytest.mark.skipif(not (ROOT/'outputs/reporting_release/20261014042133f459ce/calendar_private.json').exists(),reason='Private pinned replay source is not distributed to CI')
def test_engine_replays_selected_research_predictions_on_same_source():
    from scripts import planning_engine as engine
    from scripts import research_management_forecasts_20261021_v2 as research
    data,_=research.events();weather,holidays=research.context()
    # Engine source classification and all feature values must reconcile, not
    # merely accept similarly shaped synthetic rows.
    raw=json.loads(research.SOURCE.read_text(encoding='utf-8'))['records']
    reproduced=event_frame(raw)
    reproduced=reproduced[reproduced.start.lt(research.END)]
    assert reproduced[['calendar_id','event_id']].values.tolist()==data[['calendar_id','event_id']].values.tolist()
    a=engine.matrix(data,'booking_entries',2,weather,holidays,research.START,research.END)
    b=research.matrix(data,'booking_entries',2,weather,holidays)
    pd.testing.assert_frame_equal(a,b)
    protocol=json.loads((ROOT/'config/cp2_planning_v1.json').read_text(encoding='utf-8'))
    for spec in protocol['targets']:
        matrix=engine.matrix(data,spec['target'],spec['horizon_weeks'],weather,holidays,research.START,research.END)
        row=matrix[matrix.origin.eq(pd.Timestamp('2026-07-06'))].iloc[0]
        got,_=engine.forecast(matrix,row,spec['selected'],spec['horizon_weeks'])
        expected=pd.read_csv(research.OUT/(spec['task']+'_assessment.csv')).iloc[0].selected
        assert got==pytest.approx(expected,abs=1e-9)

def test_later_added_appointment_cannot_change_earlier_features():
    from scripts import planning_engine as engine
    origin=pd.Timestamp('2024-09-02')
    rows=[]
    for i,day in enumerate(pd.date_range('2024-01-01','2024-09-09',freq='W-MON')):
        row={**sample_events()[0],'event_id':str(i),'start_raw':day.strftime('%Y-%m-%dT09:00:00+08:00'),
             'end_raw':day.strftime('%Y-%m-%dT10:30:00+08:00'),'created_raw':'2023-12-01T00:00:00Z','updated_raw':'2023-12-01T00:00:00Z'}
        rows.append(row)
    later={**rows[-2],'event_id':'later','created_raw':'2024-09-03T00:00:00Z','updated_raw':'2024-09-03T00:00:00Z'}
    weather=pd.DataFrame({'precipitation_sum':1.,'temperature_2m_mean':27.,'relative_humidity_2m_mean':80.},index=pd.date_range('2024-01-01','2024-09-30'))
    def row(values):
        frame=engine.matrix(event_frame(values),'booking_entries',2,weather,pd.DatetimeIndex([]),pd.Timestamp('2024-05-06'),pd.Timestamp('2024-09-16'))
        return frame[frame.origin.eq(origin)].iloc[0]
    before,after=row(rows),row(rows+[later])
    assert after.actual==before.actual+1
    fields=engine.feature_columns(pd.DataFrame([before]),'activity_calendar_weather')
    pd.testing.assert_series_equal(before[fields],after[fields])

def test_weekly_workflow_never_backfills_and_evaluates_each_horizon_once(monkeypatch):
    from scripts import cp2_planning_job as job,load_calendar_bronze as calendar
    import sys
    clock=[datetime.fromisoformat('2026-10-25T23:50:00+08:00')]
    class MemoryStore:
        def __init__(self):self.objects={};self.metadata={}
        def read(self,key):return self.objects.get(key),self.metadata.get(key)
        def put(self,key,raw,immutable=True,**kwargs):
            if immutable and key in self.objects:
                assert self.objects[key]==raw,'Attempt to rewrite immutable evidence'
            else:
                self.objects[key]=raw;self.metadata[key]={'timeCreated':clock[0].isoformat()}
            return self.metadata[key]
        def keys(self,prefix):return [k for k in self.objects if k.startswith(prefix)]
    private,public=MemoryStore(),MemoryStore()
    monkeypatch.setattr(job,'Store',lambda uri:private if uri=='gs://private/v1' else public)
    monkeypatch.setenv('CP2_PLANNING_GCS_URI','gs://private/v1');monkeypatch.setenv('CP2_PORTAL_GCS_URI','gs://public/current')
    monkeypatch.setattr(job,'utcnow',lambda:clock[0]);monkeypatch.setattr(sys,'argv',['job'])
    monkeypatch.setattr(calendar,'_targets',lambda path:[{}]*6)
    monkeypatch.setattr(calendar,'_fetch',lambda *args:sample_events())
    monkeypatch.setattr(job,'weather',lambda end:({'test_weather':True},None))
    def fit(records,w,protocol,origin,captured):
        values=[];artifacts={}
        for spec in protocol['targets']:
            name=spec['task']+'.joblib';raw=spec['task'].encode();artifacts[name]=raw
            values.append({'id':spec['task'],'target':spec['target'],'prediction':15,'baseline':20,'already_booked':2,
                'window_end':(origin+timedelta(weeks=spec['horizon_weeks'])).isoformat(),'model_file':name,'model_sha256':job.sha(raw),'training_windows':30})
        return values,artifacts
    monkeypatch.setattr(job,'fit_forecasts',fit)
    job.main()
    original=private.objects['predictions/2026-10-26.json']
    assert json.loads(public.objects['planning_forecast.json'])['coverage']['timely_windows']==1
    clock[0]=datetime.fromisoformat('2026-11-05T00:00:00+08:00');job.main()
    assert private.objects['predictions/2026-10-26.json']==original
    assert 'predictions/2026-11-02.json' not in private.objects
    assert 'misses/2026-11-02.json' in private.objects
    assert set(private.keys('outcomes/'))=={'outcomes/2026-10-26/booked_hours_h1.json'}
    first_outcome=private.objects['outcomes/2026-10-26/booked_hours_h1.json']
    clock[0]=datetime.fromisoformat('2026-11-13T00:00:00+08:00');job.main()
    assert len(private.keys('outcomes/'))==2
    assert private.objects['outcomes/2026-10-26/booked_hours_h1.json']==first_outcome
    last_good=public.objects['planning_forecast.json']
    private.objects['models/2026-10-26/booked_hours_h1.joblib']=b'altered'
    with pytest.raises(ValueError,match='model hash changed'):job.main()
    assert public.objects['planning_forecast.json']==last_good
