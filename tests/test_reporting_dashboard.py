import hashlib
import base64
import json
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer
import http.client

from webapp.reporting import build
from webapp.server import Portal, handler_for, dashboard_asset_origin


def fixture():
    contract={'sales_record_id':'PRIVATE-ID','sale_total_rm':100,'sales_total_recorded_paid_rm':40,'sales_remaining_balance_rm':60,'name':'PRIVATE-NAME','phone':'PRIVATE-PHONE'}
    return {'records':{'sales':[{'date':'2026-01-01','district':'Petaling','pest':'ANT','package':'3X','premise':'RESIDENTIAL','sales_rm':100,'customer_name':'PRIVATE-NAME'}],
                        'appointments':[{'date':'2026-01-02','district':'Petaling','pest':'ANT','warranty_signal':False,'location':{'latitude':3.1,'longitude':101.6}}], 'coverage':{}},
            'customers':[{'name':'PRIVATE-NAME','contracts':[contract,contract]}],
            'receipt':{'published_release':'release-1','coverage':{},'built_at_utc':'2026-01-03T00:00:00Z'}}


def test_aggregate_payload_excludes_identity_and_deduplicates_contracts():
    result=build(fixture(),{'tables':{'payments':[{'billing_arrangement':'Monthly','phone':'PRIVATE-PHONE'}]}})
    encoded=json.dumps(result)
    assert not any(v in encoded for v in ['PRIVATE-NAME','PRIVATE-PHONE','PRIVATE-ID','latitude','longitude','customer_name'])
    assert result['sales'][0]['sales_rm']==100 and result['services'][0]['appointments']==1
    assert result['payment_status']==[{'status':'Partly paid in source','contracts':1}]


def test_missing_paid_amount_is_unknown_not_unpaid():
    value=fixture();value['customers'][0]['contracts'][0]['sales_total_recorded_paid_rm']=None
    assert build(value,{})['payment_status']==[{'status':'Needs checking','contracts':1}]


def test_asset_origin_is_exact_allowlist(monkeypatch):
    for invalid in ['https://evil.example','https://cp2-dashboard-thevesh20-3384s-projects.vercel.app.evil.example',"https://x.example; script-src *"]:
        monkeypatch.setenv('CP2_DASHBOARD_ASSET_ORIGIN',invalid)
        assert dashboard_asset_origin()==''


def test_reports_and_data_require_authentication(tmp_path,monkeypatch):
    monkeypatch.delenv('CP2_AUTH_MODE',raising=False)
    portal=Portal(tmp_path);portal.business_data=lambda:(fixture(),{})
    server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(portal))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        for path in ['/reports','/api/reporting']:
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            conn.request('GET',path);response=conn.getresponse();assert response.status==401;response.read();conn.close()
        conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
        conn.request('GET','/reports',headers={'Cookie':'cp2_session='+portal.session()});response=conn.getresponse()
        assert response.status==200 and "connect-src 'self'" in response.getheader('Content-Security-Policy')
        assert 'cp2-dashboard-thevesh20-3384s-projects.vercel.app' in response.getheader('Content-Security-Policy')
        assert '__ASSETS__' not in response.read().decode();conn.close()
    finally:server.shutdown();server.server_close()


def test_cross_origin_asset_integrity_matches_exact_packaged_files():
    root=Path(__file__).parents[1];template=(root/'webapp/static/reports.html').read_text()
    for filename in ['dashboard.js','dashboard.css']:
        digest=base64.b64encode(hashlib.sha384((root/'frontend/dashboard'/filename).read_bytes()).digest()).decode()
        assert 'sha384-'+digest in template
