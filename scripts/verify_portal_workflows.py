"""Exercise authenticated website APIs against privately downloaded real data."""
import json
import os
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
from webapp.server import Portal,handler_for


def run(folder,output):
    os.environ['CP2_PORTAL_TOKEN']='local-acceptance-fixture-not-production'
    os.environ.pop('CP2_PORTAL_GCS_URI',None)
    portal=Portal(folder);source,snapshot=portal.business_data()
    server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(portal))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_port);checks=[]
    def get(path,payload=None,authenticated=True):
        headers={'Cookie':'cp2_session='+portal.session()} if authenticated else {}
        if payload is not None:headers.update(Origin=base,**{'Content-Type':'application/json'})
        req=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
        with urllib.request.urlopen(req) as response:return json.load(response)
    try:
        try:get('/api/payment-followup',authenticated=False)
        except urllib.error.HTTPError as error:assert error.code==401
        else:raise AssertionError('Unauthenticated private access was accepted')
        checks.append('private endpoints require staff session')
        try:get('/api/spatial',authenticated=False)
        except urllib.error.HTTPError as error:assert error.code==401
        else:raise AssertionError('Unauthenticated map records were exposed')
        maps=get('/api/spatial')
        assert maps['source']['published_release']==source['receipt']['published_release']
        assert maps['sales_total']==len(source['records']['sales'])
        assert all(row['score'] in (0,1) and row['threshold']==.5 for row in maps['model'])
        assert not any(key in row for row in maps['sales'] for key in ('name','phone','email','address'))
        checks.append('staff-only maps reconcile to the release without raw risk probabilities or contacts')
        linked=get('/api/customers',{'q':'CUST1412'})
        assert linked['matching_groups']==1
        programme={s['sale_id']:s['programme_id'] for s in linked['customers'][0]['sales']}
        assert programme['CUST1412']==programme['CUST1569']
        checks.append('verified 4+20 programme remains linked in customer search')
        assert get('/api/customers',{'q':'NO_SUCH_CUSTOMER_ACCEPTANCE_987'})['matching_groups']==0
        checks.append('no-match customer search returns an explicit zero count')
        payments=get('/api/payment-followup')
        expected=[contract for c in source['customers'] for contract in c.get('contracts',[])]
        assert len(payments['contracts'])==len(expected)
        for field in ('sales_total_recorded_paid_rm','sales_remaining_balance_rm'):
            assert sum(c[field] for c in payments['contracts'] if c.get(field) is not None)==sum(c[field] for c in expected if c.get(field) is not None)
        checks.append('payment contract counts and known amounts reconcile to the exact release')
        area=get('/api/business?start=2026-01-01&end=2026-12-31')
        expected_sales=[r for r in source['records']['sales'] if r['date'] and '2026-01-01'<=r['date']<='2026-12-31']
        assert sum(r['sale_rows'] for r in area['districts'])==len(expected_sales)
        assert abs(sum(r['sales_rm'] for r in area['districts'])-sum(r['sales_rm'] or 0 for r in expected_sales))<.01
        small=get('/api/business/radius',{'lat':3.0738,'lon':101.5183,'km':5,'start':'2026-01-01','end':'2026-12-31'})
        large=get('/api/business/radius',{'lat':3.0738,'lon':101.5183,'km':20,'start':'2026-01-01','end':'2026-12-31'})
        assert large['sale_rows']>=small['sale_rows'] and large['appointments']>=small['appointments']
        checks.append('date-filtered area totals reconcile; radius change preserves geographic inclusion')
        try:get('/api/business?start=2026-02-30&end=2026-01-01')
        except urllib.error.HTTPError as error:assert error.code==400
        else:raise AssertionError('Invalid period accepted')
        checks.append('invalid date periods are rejected')
        plan=get('/api/planning');assert plan['bookings']['status']=='experimental'
        assert not any('_score' in r or 'probability' in r for r in plan['repeat_purchase']['customers'])
        checks.append('planning tools load without exposing individual probabilities')
        result={'status':'passed','source_release':source['receipt']['published_release'],
            'snapshot_fetched_at_utc':snapshot['fetched_at_utc'],'checks':checks,
            'payment_contracts':len(expected),'searched_linked_programme':True,
            'radius_5km_sales_rows':small['sale_rows'],'radius_20km_sales_rows':large['sale_rows']}
        Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8');return result
    finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();print(json.dumps(run(args.folder,args.output)))
