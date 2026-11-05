import copy
import json
from datetime import datetime
import pytest
from webapp import booking

NOW=datetime.fromisoformat('2026-10-30T08:00:00+08:00')

def snapshot(events=None):
    return {'version':'booking_v1','captured_at':NOW.isoformat(),'window_start':'2026-10-30','window_end':'2026-11-28',
            'source_snapshot_id':'a'*64,'calendar_names':[t['calendar_name'] for t in booking.policy()['teams']],
            'events':events or []}

def event(team='ace',start='10:00',end='11:00',key='b'):
    return {'key':key*64,'team_id':team,'start':'2026-11-02T'+start+':00+08:00',
            'end':'2026-11-02T'+end+':00+08:00','label':'Fixture appointment','reschedulable':True}

def request(**changes):
    return {'area':'kl','date':'2026-11-02','visit_type':'treatment','duration_minutes':'60',
            'travel_buffer_minutes':'0','work_start':'09:00','work_end':'12:00',
            'available_teams':['ace'],'staff_confirmed':True,**changes}

def test_options_do_not_overlap_fixed_bookings_or_mutate_them():
    source=snapshot([event()]);before=copy.deepcopy(source)
    r=booking.options(source,request(),NOW)
    assert [o['start'][11:16] for o in r['options']]==['09:00','11:00']
    assert all(o['coverage']=='usual_area' and not o['travel_verified'] for o in r['options'])
    assert source==before

def test_staff_travel_allowance_blocks_both_sides_of_existing_work():
    assert booking.options(snapshot([event()]),request(travel_buffer_minutes='15'),NOW)['status']=='no_fit'

def test_cross_area_and_backup_when_usual_team_is_full():
    source=snapshot([event(start='09:00',end='18:00')])
    r=booking.options(source,request(available_teams=['ace','charlie','replacement']),NOW)
    assert not any(o['team_id']=='ace' for o in r['options'])
    assert r['options'][0]['team_id']=='charlie' and r['options'][-1]['team_id']=='replacement'
    assert {o['coverage'] for o in r['options']}=={'cross_area','backup'}

def test_dash_is_usual_team_for_cyberjaya_despite_selangor_region():
    r=booking.options(snapshot(),request(area='cyberjaya',available_teams=['charlie','dash']),NOW)
    assert r['options'][0]['team_id']=='dash' and r['options'][0]['coverage']=='usual_area'

def test_sales_cannot_treat_and_beast_cannot_receive_new_work():
    r=booking.options(snapshot(),request(available_teams=['sales','beast','ace']),NOW)
    assert {o['team_id'] for o in r['options']}=={'ace'}
    assert set(r['excluded_teams'])=={'sales','beast'}
    r=booking.options(snapshot(),request(visit_type='consultation',available_teams=['ace','sales']),NOW)
    assert {o['team_id'] for o in r['options']}=={'sales'}

def test_replacement_putrajaya_not_inferred_from_kl_selangor_confirmation():
    r=booking.options(snapshot(),request(area='putrajaya',available_teams=['replacement']),NOW)
    assert not r['options'] and r['excluded_teams']==['replacement']

def test_rescheduling_excludes_only_the_selected_appointment():
    source=snapshot([event(start='09:00',end='10:00'),event(start='10:00',end='12:00',key='c')])
    r=booking.options(source,request(reschedule_key='b'*64),NOW)
    assert [o['start'][11:16] for o in r['options']]==['09:00']
    with pytest.raises(ValueError):booking.options(source,request(reschedule_key='d'*64),NOW)
    source['events'][0]['reschedulable']=False
    with pytest.raises(ValueError):booking.options(source,request(reschedule_key='b'*64),NOW)

@pytest.mark.parametrize('kind',['missing','stale','incomplete','invalid'])
def test_untrusted_schedules_never_yield_free_slots(kind):
    s=snapshot()
    if kind=='missing':s=None
    if kind=='stale':s['captured_at']='2026-10-27T00:00:00+08:00'
    if kind=='incomplete':s['calendar_names'].pop()
    if kind=='invalid':s['events']=[event(start='11:00',end='10:00')]
    r=booking.options(s,request(),NOW)
    assert r['status']==kind and not r['options']

@pytest.mark.parametrize('change',[{'date':'2026-10-29'},{'date':'2026-12-01'},
    {'duration_minutes':'0'},{'duration_minutes':'60.5'},{'travel_buffer_minutes':'-1'},
    {'available_teams':[]},{'work_end':'08:00'},{'staff_confirmed':False}])
def test_invalid_or_unconfirmed_scenarios_rejected(change):
    with pytest.raises(ValueError):booking.options(snapshot(),request(**change),NOW)

def test_export_cancels_holds_only_and_preserves_real_sunday_and_all_day_blocks():
    def raw(key,title,status='confirmed',start='2026-11-01T09:00:00+08:00',end='2026-11-01T10:00:00+08:00'):
        return {'calendar_name':'TEAM ACE (Izzat)','calendar_id':'fixture','event_id':key,
                'summary':title,'status':status,'start_raw':start,'end_raw':end}
    source={'metadata':{'calendar_count':6,'extracted_at':NOW.isoformat(),'snapshot_id':'a'*64,
                       'window_start':'2026-10-30','window_end':'2026-11-28'},
            'records':[raw('1','GPC 2/3 Sunday'),raw('2','CANCELLED GPC'),raw('3','HOLD awaiting date'),
                       raw('4','Deleted','cancelled'),raw('5','Staff leave',start='2026-11-02',end='2026-11-03')]}
    exported=booking.export_snapshot(source,[],lambda e,r:False)
    assert len(exported['events'])==2
    assert booking.options(exported,request(),NOW)['status']=='no_fit'

def test_booking_api_requires_auth_and_same_origin_and_does_not_write_sources(tmp_path,monkeypatch):
    import threading,requests
    from http.server import ThreadingHTTPServer
    from webapp.server import Portal,handler_for
    monkeypatch.setenv('CP2_AUTH_MODE','staff_code');monkeypatch.setenv('CP2_PORTAL_TOKEN','fixture-access')
    monkeypatch.delenv('CP2_PORTAL_GCS_URI',raising=False)
    p=tmp_path/'booking_schedule_private.json';raw=json.dumps(snapshot());p.write_text(raw)
    portal=Portal(tmp_path);server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(portal))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_port);headers={'Cookie':'cp2_session='+portal.session(),'Origin':base}
    monkeypatch.setattr(booking,'availability',lambda s,now=None:'ready')
    original_options=booking.options  # pin the clock to the fixture time so the test does not expire
    monkeypatch.setattr(booking,'options',lambda s,r,now=None:original_options(s,r,now or NOW))
    try:
        assert requests.get(base+'/api/booking',timeout=3).status_code==401
        assert requests.get(base+'/api/booking',headers=headers,timeout=3).json()['teams']
        assert requests.post(base+'/api/booking/options',json=request(),headers={'Cookie':headers['Cookie']},timeout=3).status_code==403
        value=requests.post(base+'/api/booking/options',json=request(),headers=headers,timeout=3)
        assert value.status_code==200 and value.json()['status']=='options'
        assert p.read_text()==raw and not (tmp_path/'workspace_actions.json').exists()
    finally:server.shutdown();server.server_close()


def test_reschedule_does_not_offer_a_past_or_started_appointment():
    for now in ['2026-11-02T09:00:00+08:00','2026-11-02T09:30:00+08:00','2026-11-02T11:00:00+08:00']:
        source=snapshot([event(start='09:00',end='10:00')]);source['captured_at']=now
        with pytest.raises(ValueError,match='future appointment'):
            booking.options(source,request(reschedule_key='b'*64),datetime.fromisoformat(now))

@pytest.mark.parametrize('change',[{'window_start':'not-a-date'},{'window_end':'2026-10-01'}, {'calendar_names':['TEAM ACE (Izzat)']*6}])
def test_invalid_snapshot_period_or_inventory_does_not_imply_free_time(change):
    value=snapshot();value.update(change)
    assert booking.options(value,request(),NOW)['status'] in ('invalid','incomplete')

@pytest.mark.parametrize('change',[{'label':42},{'reschedulable':'true'}])
def test_malformed_event_metadata_is_rejected(change):
    row=event();row.update(change)
    assert booking.options(snapshot([row]),request(),NOW)['status']=='invalid'


def test_malformed_team_value_is_rejected_cleanly():
    with pytest.raises(ValueError):booking.options(snapshot(),request(available_teams=[{}]),NOW)


def test_visual_calendar_can_request_all_valid_starts_not_only_first_three():
    s=snapshot()
    short=booking.options(s,request(),NOW)
    full=booking.options(s,request(all_slots=True),NOW)
    assert len(short['options'])==3 and len(full['options'])==9
    assert full['options'][-1]['start'][11:16]=='11:00'
    assert len({(r['team_id'],r['start']) for r in full['options']})==9
