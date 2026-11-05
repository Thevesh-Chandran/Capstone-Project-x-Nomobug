import copy,json
from datetime import datetime
import pytest
from webapp import workspace
from webapp.action_log import Store,Conflict

NOW=datetime.fromisoformat('2026-10-25T12:00:00+08:00')
def inputs():
    business={'receipt':{'published_release':'cp2r_fixture'},'customers':[{'name':'Example Customer','contracts':[
        {'sales_record_id':'SALE1','sales_remaining_balance_rm':100,'sales_total_recorded_paid_rm':200,'next_scheduled_reminder_date':'2026-10-26'},
        {'sales_record_id':'SALE2','sales_remaining_balance_rm':None,'next_scheduled_reminder_date':None},
        {'sales_record_id':'SALE3','sales_remaining_balance_rm':0,'next_scheduled_reminder_date':'2026-10-26'}]}]}
    snap={'tables':{'freshness':[{'source_name':s,'extracted_at_utc':'2026-10-25T00:00:00Z'} for s in ['sales','recurring_payments','calendar']],
          'upcoming':[{'service_date':'2026-10-26','calendar_name':'Team A','scheduled_event_rows':3,'extracted_at':'2026-10-25T00:00:00Z'}]}}
    planning={'evidence':{},'live':{'latest':{'origin':'2026-10-26T00:00:00+08:00'},'forecasts':[{'id':'booked_hours_h1','prediction':20,'already_booked':8}]}}
    return business,snap,planning

def test_recorded_payment_and_review_are_separate():
    b,s,p=inputs();before=copy.deepcopy(b);r=workspace.build(b,s,p,now=NOW)
    assert r['counts']['upcoming']==1 and r['counts']['unknown']==1 and r['counts']['total']==2
    task=r['tasks'][0];log={'records':{task['id']:{'evidence_hash':task['evidence_hash'],'status':'contacted','note':'Customer contacted separately'}}}
    reviewed=workspace.build(b,s,p,log,now=NOW)
    assert reviewed['tasks'][0]['status']=='contacted'
    assert reviewed['tasks'][0]['sales_remaining_balance_rm']==100 and b==before
    assert 'overdue' not in task['draft'] and '100' not in task['draft']

def test_source_change_requires_review_again():
    b,s,p=inputs();r=workspace.build(b,s,p,now=NOW);task=r['tasks'][0]
    log={'records':{task['id']:{'status':'reviewed','evidence_hash':task['evidence_hash']}}}
    b['customers'][0]['contracts'][0]['sales_remaining_balance_rm']=90
    changed=workspace.build(b,s,p,log,now=NOW)['tasks'][0]
    assert changed['source_changed'] and changed['status']=='open'

def test_cancellation_note_becomes_a_status_check_not_a_reminder_draft():
    b,s,p=inputs();b['customers'][0]['name']='Example (Cancelled, relocating)'
    work=workspace.build(b,s,p,now=NOW)
    assert work['counts']['source_upcoming']==1 and work['counts']['upcoming']==0
    assert work['counts']['status']==2
    assert all(t['draft'] is None and t['review_kind']=='status' for t in work['tasks'])
    assert work['tasks'][0]['sales_remaining_balance_rm']==100

def test_capacity_compares_exact_horizon_and_never_guesses_missing_sources():
    b,s,p=inputs();work=workspace.build(b,s,p,now=NOW)
    decision=workspace.capacity_decision(work,15,2)
    assert decision['status']=='shortfall' and decision['gap_hours']==7 and decision['additional_booking_hours']==12
    assert workspace.capacity_decision(work,30)['status']=='within_plan'
    p['live']['latest']['origin']='2026-10-19T00:00:00+08:00'
    work=workspace.build(b,s,p,now=NOW,week='2026-10-26')
    assert not work['current_forecasts']
    assert workspace.capacity_decision(work,15)['status']=='waiting_for_verified_forecast'
    del s['tables']['upcoming'];assert workspace.build(b,s,p,now=NOW)['schedule']['bookings'] is None
    for v in [-1,float('nan'),float('inf'),'invalid',2001]:
        with pytest.raises(ValueError):workspace.capacity_decision(work,v)

def test_stale_sources_do_not_generate_a_capacity_recommendation():
    b,s,p=inputs();work=workspace.build(b,s,p,now=datetime.fromisoformat('2026-10-27T18:00:00+08:00'))
    assert work['source_stale']
    assert workspace.capacity_decision(work,1)['status']=='waiting_for_verified_forecast'

def test_plan_summary_requires_capacity_and_uses_saved_scenario():
    b,s,p=inputs();work=workspace.build(b,s,p,now=NOW)
    assert work['plan_summary']['status']=='enter_capacity'
    assert work['plan_summary']['capacity_hours'] is None
    log={'records':{'capacity:2026-10-26':{'capacity_hours':15,'buffer_hours':2}}}
    saved=workspace.build(b,s,p,log,now=NOW)
    assert saved['plan_summary']['status']=='shortfall'
    assert '7.0' in saved['plan_summary']['action']
    assert '7.0' in workspace.brief(saved,'plan')['answer']
    log['records']['capacity:2026-10-26']['capacity_hours']=30
    assert workspace.build(b,s,p,log,now=NOW)['plan_summary']['status']=='within_plan'

def test_plan_summary_never_substitutes_two_week_bookings_for_weekly_hours():
    b,s,p=inputs();p['live']['forecasts']=[{'id':'bookings_h2','prediction':100,'already_booked':20}]
    work=workspace.build(b,s,p,now=NOW)
    assert work['plan_summary']['status']=='waiting'
    assert work['plan_summary']['forecast_hours'] is None
    assert 'No verified appointment-hours forecast' in workspace.brief(work,'plan')['answer']
    stale=workspace.build(b,s,p,now=datetime.fromisoformat('2026-10-27T18:00:00+08:00'))
    assert stale['plan_summary']['status']=='check_sources'

def test_booking_concentrations_exclude_past_days_and_do_not_imply_shortages():
    b,s,p=inputs()
    s['tables']['upcoming']+=[{'service_date':'2026-10-27','calendar_name':'Team B','scheduled_event_rows':5,'extracted_at':'2026-10-25T00:00:00Z'},
                            {'service_date':'2026-10-28','calendar_name':'Team A','scheduled_event_rows':2,'extracted_at':'2026-10-25T00:00:00Z'}]
    work=workspace.build(b,s,p,now=datetime.fromisoformat('2026-10-27T12:00:00+08:00'))
    assert work['schedule']['bookings']==7
    assert work['plan_summary']['busiest_days'][0]=={'date':'2026-10-27','bookings':5}
    assert 'not a staffing shortage' in work['plan_summary']['notice']

def test_fast_brief_has_evidence_and_real_next_steps():
    b,s,p=inputs();work=workspace.build(b,s,p,now=NOW);r=workspace.brief(work,'brief')
    assert r['source_release']=='cp2r_fixture' and r['actions'][0]['href']=='#home'
    assert '1 contracts' in r['answer'] and 'overdue' in r['answer']
    assert 'No customer was contacted' in r['notice']
    with pytest.raises(ValueError):workspace.brief(work,'invent-anything')

def test_ledger_persists_and_rejects_stale_updates(tmp_path,monkeypatch):
    monkeypatch.delenv('CP2_ACTIONS_GCS_URI',raising=False);monkeypatch.delenv('K_SERVICE',raising=False)
    store=Store(tmp_path);_,rev=store.load();key='a'*64
    _,new=store.update(key,{'status':'reviewed','note':'Source checked'},rev,'staff-example')
    assert Store(tmp_path).load()[0]['records'][key]['note']=='Source checked'
    with pytest.raises(Conflict):store.update(key,{'status':'open'},rev,'another-staff')
    assert store.load()[1]==new
    with pytest.raises(ValueError):store.update('../source',{},new,'staff')
    monkeypatch.setenv('K_SERVICE','hosted')
    with pytest.raises(ValueError,match='Durable'):store.load()

def test_cloud_ledger_uses_generation_precondition(monkeypatch,tmp_path):
    monkeypatch.setenv('CP2_ACTIONS_GCS_URI','gs://private-ledger/workspace')
    class Response:
        status_code=404
    class Session:
        def get(self,*a,**k):return Response()
        def post(self,url,**kw):
            assert kw['params']['ifGenerationMatch']=='0'
            assert kw['params']['name']=='workspace/state.json'
            assert json.loads(kw['data'])['records']['b'*64]['status']=='reviewed'
            class Failed:
                status_code=412
            return Failed()
    monkeypatch.setattr('webapp.storage.authorized_session',lambda:Session())
    with pytest.raises(Conflict):Store(tmp_path).update('b'*64,{'status':'reviewed'},'0','staff')

def test_active_forecast_stays_usable_midweek_and_next_week_is_separate():
    b,s,p=inputs();now=datetime.fromisoformat('2026-10-27T12:00:00+08:00')
    current=workspace.build(b,s,p,now=now)
    assert current['week_start']=='2026-10-26' and current['current_forecasts']
    following=workspace.build(b,s,p,now=now,week='2026-11-02')
    assert following['week_start']=='2026-11-02' and not following['current_forecasts']
    with pytest.raises(ValueError):workspace.build(b,s,p,now=now,week='2027-01-01')

def test_private_api_persists_progress_and_rejects_stale_or_financial_writes(tmp_path,monkeypatch):
    import requests,threading
    from http.server import ThreadingHTTPServer
    from webapp.server import Portal,handler_for
    monkeypatch.setenv('CP2_AUTH_MODE','staff_code');monkeypatch.setenv('CP2_PORTAL_TOKEN','fixture-private-access-code-only')
    monkeypatch.delenv('CP2_ACTIONS_GCS_URI',raising=False);monkeypatch.delenv('K_SERVICE',raising=False)
    b,s,_=inputs();before=copy.deepcopy(b);p=Portal(tmp_path);p.business_data=lambda:(b,s)
    original=workspace.build
    monkeypatch.setattr(workspace,'build',lambda *a,**k:original(*a,**k,now=NOW))
    server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(p));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_port)
    headers={'Origin':base,'Cookie':'cp2_session='+p.session()}
    try:
        assert requests.get(base+'/api/workspace',timeout=3).status_code==401
        r=requests.get(base+'/api/workspace',headers=headers,timeout=3);assert r.status_code==200
        work=r.json();task=work['tasks'][0]
        body={'id':task['id'],'evidence_hash':task['evidence_hash'],'status':'reviewed','note':'Checked the fixture source','revision':work['action_revision']}
        assert requests.post(base+'/api/workspace/actions',json=body,headers=headers,timeout=3).status_code==200
        assert requests.post(base+'/api/workspace/actions',json=body,headers=headers,timeout=3).status_code==409
        saved=requests.get(base+'/api/workspace',headers=headers,timeout=3).json()
        assert saved['tasks'][0]['status']=='reviewed' and saved['tasks'][0]['sales_remaining_balance_rm']==100
        assert requests.post(base+'/api/workspace/actions',json={**body,'status':'paid','revision':saved['action_revision']},headers=headers,timeout=3).status_code==400
        settings={'kind':'capacity','week':'2026-10-26','capacity_hours':0,'buffer_hours':0,'revision':saved['action_revision']}
        assert requests.post(base+'/api/workspace/actions',json=settings,headers=headers,timeout=3).status_code==200
        log,_=p.action_store.load();plan=log['records']['capacity:2026-10-26']
        assert plan['source_release']=='cp2r_fixture' and plan['forecast_origin'] is None
        assert plan['decision_at_save']['status']=='waiting_for_verified_forecast'
        assert requests.post(base+'/api/workspace/actions',json=body,headers={'Cookie':headers['Cookie']},timeout=3).status_code==403
        assert b==before
    finally:server.shutdown();server.server_close()
