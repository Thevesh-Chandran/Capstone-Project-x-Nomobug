"""Meaningful guards for historical evaluation, data access and auth."""
import json
import math
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
import pytest
from webapp import data
from webapp.geography import contains,district_for,metrics,radius_result,wilson
from webapp.server import Portal,handler_for,public_area

def row(outcome,score=.1,threshold=.5,review=False,lat=3,lon=101,uncertainty=.1):
    return {'outcome':outcome,'score':score,'threshold':threshold,'global_review':review,
        'latitude':lat,'longitude':lon,'uncertainty_km':uncertainty}

def test_subgroup_uses_fixed_threshold_and_original_review():
    r=metrics([row(True,.7,review=True),row(True,.2),row(False,.8),row(False,.1)])
    assert (r['true_positives'],r['missed_cases'],r['false_alerts'])==(1,1,1)
    assert r['accuracy']==.5 and r['always_no_return_accuracy']==.5
    assert r['cases_found_in_global_top20']==1 and r['status']=='small_sample_exploratory'
    assert metrics([row(False)])['recall'] is None
    assert wilson(0,0) is None

def test_polygon_holes_and_uncertain_boundary():
    geom={'type':'Polygon','coordinates':[[[100,2],[102,2],[102,4],[100,4],[100,2]],[[100.2,2.2],[100.4,2.2],[100.4,2.4],[100.2,2.4],[100.2,2.2]]]}
    f={'geometry':geom,'properties':{'state':'S','district':'D'}}
    assert contains(geom,101,3) and not contains(geom,100.3,2.3)
    assert district_for([f],3,101,.1)=='S / D'
    assert district_for([f],3,100.001,1) is None
    assert district_for([f,f],3,101,0) is None

def test_radius_excludes_ambiguous_and_suppresses_small_groups():
    rows=[row(False) for _ in range(6)] + [row(True,lat=3.09,uncertainty=3)]
    r=radius_result(rows,3,101,10)
    assert r['services']==6 and r['ambiguous_boundary_services']==1
    assert radius_result(rows[:2],3,101,10)['status']=='insufficient_services'
    for vals in [(3,101,0),(3,101,51),(math.nan,101,10),(3,0,10)]:
        with pytest.raises(ValueError):radius_result(rows,*vals)

def test_public_area_suppression_and_no_private_paths(tmp_path):
    p=tmp_path/'area_evaluation.json';p.write_text(json.dumps({'provenance':{'secret/path':'hash'},'districts':[
        {'district':'D','services':2,'positive_cases':1,'accuracy':1}]}))
    result=public_area(tmp_path)
    assert 'provenance' not in result and 'positive_cases' not in result['districts'][0]

def test_missing_data_is_unknown_not_zero():
    assert data.totals({'tables':{}})['sales_rm'] is None
    assert data.totals({'tables':{'sales':[{'recorded_package_face_value_rm':None}]}})['sales_rm'] is None
    assert data.totals({'tables':{'sales':[{'recorded_package_face_value_rm':0}]}})['sales_rm']==0

def test_failed_refresh_preserves_snapshot(tmp_path):
    p=tmp_path/'business_snapshot.json';p.write_text('{"status":"last-good"}')
    class Client:
        def query(self,*a,**k):raise RuntimeError('fixture')
    with pytest.raises(RuntimeError):data.refresh(tmp_path,Client())
    assert json.loads(p.read_text())['status']=='last-good'

def test_http_auth_origin_host_and_private_file_guards(tmp_path,monkeypatch):
    monkeypatch.setenv('CP2_PORTAL_TOKEN','test-staff-access-code-long-enough')
    portal=Portal(tmp_path);server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(portal))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urllib.request.urlopen(base+'/healthz') as response:assert response.status==200
        for path in ['/api/state','/area_rows_private.json','/../config/cp2_model_current.json']:
            with pytest.raises(urllib.error.HTTPError) as err:urllib.request.urlopen(base+path)
            assert err.value.code==401
        req=urllib.request.Request(base+'/api/login',data=b'{"token":"test-staff-access-code-long-enough"}',headers={'Content-Type':'application/json'},method='POST')
        with pytest.raises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
        assert err.value.code==403
        req.add_header('Origin',base)
        with urllib.request.urlopen(req) as response:cookie=response.headers['Set-Cookie'].split(';')[0]
        req=urllib.request.Request(base+'/api/state',headers={'Cookie':cookie})
        with urllib.request.urlopen(req) as response:assert json.load(response)['snapshot']['status']=='not_connected'
        req=urllib.request.Request(base+'/api/state',headers={'Host':'evil.example','Cookie':cookie})
        with pytest.raises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
        assert err.value.code==403
        assert not portal.authenticated('cp2_session=0.invalid')
    finally:server.shutdown();server.server_close();thread.join()

def test_staff_session_survives_instance_restart_but_not_code_rotation(tmp_path,monkeypatch):
    monkeypatch.setenv('CP2_PORTAL_TOKEN','test-staff-access-code-long-enough')
    cookie='cp2_session='+Portal(tmp_path).session()
    assert Portal(tmp_path).authenticated(cookie)
    monkeypatch.setenv('CP2_PORTAL_TOKEN','rotated-staff-access-code-long-enough')
    assert not Portal(tmp_path).authenticated(cookie)


def test_customer_search_is_private_post_and_not_aggregate_state(tmp_path,monkeypatch):
    monkeypatch.setenv('CP2_PORTAL_TOKEN','test-staff-access-code-long-enough')
    (tmp_path/'business_tools_private.json').write_text(json.dumps({'receipt':{},'records':{},'customers':[
        {'name':'Private Client','sales_rm':100,'sales':[{'sale_id':'C1'}]}]}))
    portal=Portal(tmp_path)
    server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(portal));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_port)
    try:
        for method,headers in [('GET',{}),('POST',{'Origin':base})]:
            req=urllib.request.Request(base+'/api/customers',data=b'{"q":"Private"}' if method=='POST' else None,headers=headers,method=method)
            with pytest.raises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
            assert err.value.code==401
        cookie='cp2_session='+portal.session()
        req=urllib.request.Request(base+'/api/customers',data=b'{"q":"Private"}',headers={'Origin':base,'Cookie':cookie},method='POST')
        with urllib.request.urlopen(req) as response:assert json.load(response)['matching_groups']==1
        req=urllib.request.Request(base+'/api/state',headers={'Cookie':cookie})
        with urllib.request.urlopen(req) as response:assert 'Private Client' not in response.read().decode()
    finally:server.shutdown();server.server_close();thread.join()

def test_cloud_first_request_loads_snapshot_before_five_minutes(tmp_path,monkeypatch):
    from webapp import server
    calls=[]
    def pull(uri,folder):
        calls.append(uri)
        (folder/'business_snapshot.json').write_text(json.dumps({'status':'connected','tables':{}}))
    monkeypatch.setenv('CP2_PORTAL_GCS_URI','gs://fixture/current')
    monkeypatch.setattr(server.storage,'pull',pull)
    monkeypatch.setattr(server.time,'monotonic',lambda:10)
    portal=Portal(tmp_path)
    assert portal.state()['snapshot']['status']=='connected'
    portal.state()
    assert calls==['gs://fixture/current']


def test_private_business_endpoints_reject_mixed_releases(tmp_path):
    snapshot={'status':'connected','tables':{'freshness':[{'release_run_id':'new'}]}}
    (tmp_path/'business_snapshot.json').write_text(json.dumps(snapshot))
    (tmp_path/'business_tools_private.json').write_text(json.dumps({'receipt':{'published_release':'cp2r_old'}}))
    with pytest.raises(ValueError,match='releases differ'):Portal(tmp_path).business_data()
    (tmp_path/'business_tools_private.json').write_text(json.dumps({'receipt':{'published_release':'cp2r_new'}}))
    assert Portal(tmp_path).business_data()[0]['receipt']['published_release']=='cp2r_new'


def test_return_chart_evidence_matches_archived_candidate():
    root=Path(__file__).resolve().parents[1]
    source=root/'config/warranty_new_holdout_v5.json'
    import hashlib
    saved=json.loads((root/'webapp/models/return30_evidence.json').read_text())
    segment=json.loads(source.read_text())['results']['selected_ap']['segments']['all']
    raw=source.read_bytes();lf=raw.replace(b'\r\n',b'\n')
    # The checkout may store either line ending; the content is the same.
    assert saved['source_sha256'] in {hashlib.sha256(x).hexdigest() for x in (raw,lf,lf.replace(b'\n',b'\r\n'))}
    for key in ('rows','positive_rows','threshold_TP','threshold_FN','threshold_FP'):
        assert saved[key]==segment[key]
    assert saved['threshold_TP']+saved['threshold_FN']==saved['positive_rows']

def test_featured_research_candidate_is_highest_supported_f1():
    import hashlib
    root=Path(__file__).resolve().parents[1]
    source=root/'outputs/model_validation/20261016_target_research/results.json'
    if not source.exists():pytest.skip('private research output is not in the public repository')
    saved=json.loads((root/'webapp/models/return_research_best.json').read_text())
    assert saved['source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    expected=max((r for r in json.loads(source.read_text())['summary'] if r['folds']>=3),key=lambda r:r['pooled_f1'])
    assert saved['candidate']==expected
    assert expected['TP']+expected['FN']==expected['positive_windows']
    assert expected['TP']+expected['FN']+expected['FP']+expected['TN']==expected['services']
