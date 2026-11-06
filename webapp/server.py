"""Private management website; run with python -m webapp.server.

Only fixed aggregate queries and saved evaluation results are exposed. The
pest-return collector and separate weekly planning job own their prediction logs.
"""
from __future__ import annotations
from urllib.parse import unquote
import mimetypes
import argparse
import html
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs

from webapp import data, storage
from webapp.geography import radius_result

ROOT=Path(__file__).resolve().parents[1]
STATIC=Path(__file__).parent/'static'
REPORT='https://datastudio.google.com/embed/reporting/590914e8-066b-4671-a130-7a62a3af435a/page/NCy8F'


def dashboard_url():
    """The business dashboard staff are sent to. Looker Studio by default; set
    CP2_DASHBOARD_URL to another https address (for example Metabase) to switch."""
    url=os.environ.get('CP2_DASHBOARD_URL','').strip()
    return url if url.startswith('https://') else REPORT


def google_calendar_url():
    """Embed address for the teams' Google Calendars, or None when not configured.

    CP2_GOOGLE_CALENDAR_IDS is a comma-separated list of calendar IDs. The embed only
    shows events to a viewer whose own Google account already has access to them."""
    import re
    from urllib.parse import quote
    ids=[i.strip() for i in os.environ.get('CP2_GOOGLE_CALENDAR_IDS','').split(',') if i.strip()]
    ids=[i for i in ids if re.fullmatch(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+',i)][:10]
    if not ids:return None
    return ('https://calendar.google.com/calendar/embed?ctz=Asia%2FKuala_Lumpur&mode=WEEK&showPrint=0&showTitle=0'
            +''.join('&src='+quote(i,safe='') for i in ids))


def dashboard_asset_origin():
    origin=os.environ.get('CP2_DASHBOARD_ASSET_ORIGIN','https://cp2-dashboard-thevesh20-3384s-projects.vercel.app').rstrip('/')
    # This source can execute scripts in the authenticated page: never accept
    # an arbitrary URL, query parameter, wildcard, or request-controlled origin.
    return origin if origin=='https://cp2-dashboard-thevesh20-3384s-projects.vercel.app' else ''

def public_area(folder):
    p=Path(folder)/'area_evaluation.json'
    if not p.exists(): return {'status':'not_prepared','districts':[],'message':'Prepare saved historical area evaluation first.'}
    result=json.loads(p.read_text(encoding='utf-8'))
    # Internal paths and hashes remain in the local audit receipt.
    result.pop('provenance',None)
    result['districts']=[r if r['services']>=5 else {'district':r['district'],'services':r['services'],
        'status':'insufficient_services','note':'Fewer than five evaluated services; outcome metrics withheld.'} for r in result['districts']]
    return result

class Portal:
    def __init__(self,folder):
        self.folder=Path(folder)
        self.token=os.environ.get('CP2_PORTAL_TOKEN','')
        self.username=os.environ.get('CP2_PORTAL_USERNAME','admin')
        # Cloud Run can replace an instance between requests. Keep sessions
        # valid across restarts, but invalidate them when the staff code rotates.
        self.signing_key=(hmac.new(self.token.encode(),b'cp2-portal-session-v1',hashlib.sha256).digest()
            if self.token else secrets.token_bytes(32))
        self.last_refresh_error=None;self.refresh_lock=threading.Lock()
        self.login_attempts=[];self.login_lock=threading.Lock()
        self.last_storage_check=0
        from webapp.action_log import Store
        self.action_store=Store(self.folder)
    def session(self):
        expiry=str(int(time.time())+8*3600)
        sig=hmac.new(self.signing_key,expiry.encode(),hashlib.sha256).hexdigest()
        return expiry+'.'+sig
    def authenticated(self,cookie,assertion=None):
        if os.environ.get('CP2_AUTH_MODE')=='iap':
            return self.iap_authenticated(assertion)
        for part in (cookie or '').split(';'):
            if part.strip().startswith('cp2_session='):
                try:
                    expiry,sig=part.strip().split('=',1)[1].split('.',1)
                    expected=hmac.new(self.signing_key,expiry.encode(),hashlib.sha256).hexdigest()
                    return int(expiry)>time.time() and hmac.compare_digest(sig,expected)
                except (ValueError,TypeError):return False
        return False
    def iap_email(self,assertion):
        """The verified Google account email behind an IAP assertion, or None."""
        claims=self.iap_claims(assertion)
        return claims.get('email') if claims else None
    def iap_authenticated(self,assertion):
        return self.iap_claims(assertion) is not None
    def iap_claims(self,assertion):
        if not assertion:return None
        audience=os.environ.get('CP2_IAP_AUDIENCE','')
        if not audience:return None
        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import id_token
            import requests
            from cachecontrol import CacheControl
            # Cache Google's public certificates, never user assertions or identity data.
            with self.login_lock:
                if not hasattr(self,'iap_request'):
                    self.iap_request=Request(session=CacheControl(requests.Session()))
                claims=id_token.verify_token(assertion,self.iap_request,audience=audience,
                    certs_url='https://www.gstatic.com/iap/verify/public_key')
            ok=claims.get('iss')=='https://cloud.google.com/iap' and bool(claims.get('sub'))
            return claims if ok else None
        except Exception:
            return None
    def state(self):
        uri=os.environ.get('CP2_PORTAL_GCS_URI')
        if uri and (not self.last_storage_check or time.monotonic()-self.last_storage_check>300):
            with self.refresh_lock:
                try:storage.pull(uri,self.folder);self.last_refresh_error=None
                except Exception as exc:self.last_refresh_error=type(exc).__name__
                self.last_storage_check=time.monotonic()
        snapshot=data.load_snapshot(self.folder)
        registry=json.loads((ROOT/'config/cp2_model_current.json').read_text())
        return {'snapshot':snapshot,'totals':data.totals(snapshot),'areas':public_area(self.folder),
            'model':registry,'dashboard_url':dashboard_url(),'dashboard_embed':dashboard_url()==REPORT,'google_calendar_url':google_calendar_url(),'system':{
                'website':'running','auth_mode':os.environ.get('CP2_AUTH_MODE','staff_code'),'data_mode':os.environ.get('CP2_DATA_MODE','snapshot'),
                'last_refresh_error':self.last_refresh_error,
                'observed_at_utc':datetime.now(timezone.utc).isoformat(),
                'collector_note':'Independent cloud service. Website availability does not prove collection succeeded.'}}
    def refresh_loop(self):
        if os.environ.get('CP2_DATA_MODE')!='bigquery':return
        delay=max(900,int(os.environ.get('CP2_REFRESH_SECONDS','3600')))
        while True:
            try:
                with self.refresh_lock:data.refresh(self.folder)
                self.last_refresh_error=None
            except Exception as exc:self.last_refresh_error=type(exc).__name__
            time.sleep(delay)

    def business_data(self):
        self.state()  # Refresh if due, retaining last-good files on failure.
        with self.refresh_lock:
            value=json.loads((self.folder/'business_tools_private.json').read_text(encoding='utf-8'))
            snapshot=data.load_snapshot(self.folder)
            if snapshot.get('status')=='connected':
                releases={r.get('release_run_id') for r in snapshot.get('tables',{}).get('freshness',[])}
                if len(releases)!=1 or None in releases or value.get('receipt',{}).get('published_release')!='cp2r_'+next(iter(releases)):
                    raise ValueError('Published source releases differ')
            return value,snapshot

def handler_for(portal):
    class Handler(BaseHTTPRequestHandler):
        server_version='NomobugPortal'
        def log_message(self, *_):pass # No URLs, questions, cookie or source content in access logs.
        def headers_secure(self,csp=None):
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            assets = dashboard_asset_origin() if urlsplit(self.path).path == '/reports' else ''
            extra = ' '+assets if assets else ''
            self.send_header('Content-Security-Policy',csp or f"default-src 'self'; script-src 'self'{extra}; style-src 'self'{extra}; img-src 'self' data:; connect-src 'self'; frame-src 'self' https://datastudio.google.com https://lookerstudio.google.com https://calendar.google.com; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        def respond(self,status,body,ctype='application/json; charset=utf-8',cookie=None,csp=None):
            raw=json.dumps(body,default=data.json_default,allow_nan=False).encode() if isinstance(body,(dict,list)) else body
            self.send_response(status);self.headers_secure(csp);self.send_header('Content-Type',ctype)
            if cookie:self.send_header('Set-Cookie',cookie)
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def host_ok(self):
            host=urlsplit('//'+self.headers.get('Host','')).hostname
            allowed=set(os.environ.get('CP2_ALLOWED_HOSTS','localhost,127.0.0.1').split(','))
            return host in allowed
        def business_data(self):
            try:return portal.business_data()
            except (FileNotFoundError,ValueError,KeyError):
                self.respond(503,{'error':'Business records are unavailable or their release checks failed. Try again after the next refresh.'})
                return None
        def workspace_data(self,week=None):
            loaded=self.business_data()
            if loaded is None:return None
            from webapp import workspace,planning
            value,snapshot=loaded
            try:log,generation=portal.action_store.load();available=True
            except Exception:log,generation,available={'version':1,'records':{}},None,False
            result=workspace.build(value,snapshot,planning.load(portal.folder),log,week=week)
            result.update(action_revision=generation,log_available=available)
            return result
        def dashboard_file(self,path):
            # Evidence dashboard build, rebuilt daily into the mounted bucket folder. Signed-in users only.
            root=Path(os.environ.get('CP2_DASHBOARD_DIR','')).resolve() if os.environ.get('CP2_DASHBOARD_DIR') else None
            if not root or not root.is_dir():return self.respond(503,{'error':'Reports are not available right now'})
            rel=unquote(path[len('/dashboard'):]).lstrip('/')
            for cand in (rel, rel.rstrip('/')+'/index.html' if rel else 'index.html', rel.rstrip('/')+'.html'):
                p=(root/cand).resolve()
                if p.is_file() and (p==root or root in p.parents):break
            else:return self.respond(404,{'error':'Report page not found'})
            mime=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
            if mime.startswith('text/') or mime in ('application/javascript','application/json'):mime+='; charset=utf-8'
            if p.suffix=='.wasm':mime='application/wasm'
            csp=("default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval' blob:; worker-src 'self' blob:; "
                 "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://tile.openstreetmap.org; font-src 'self' data:; "
                 "connect-src 'self' blob: data: https://extensions.duckdb.org; frame-ancestors 'self'; base-uri 'self'; form-action 'self'")
            return self.respond(200,p.read_bytes(),mime,csp=csp)
        def do_GET(self):
            if not self.host_ok():return self.respond(403,{'error':'Host not allowed'})
            path=urlsplit(self.path).path
            if path=='/healthz':return self.respond(200,{'status':'ok'})
            if path=='/nomobug-logo.png':return self.respond(200,(STATIC/'nomobug-logo.png').read_bytes(),'image/png')
            if path=='/tools.js':return self.respond(200,(STATIC/'tools.js').read_bytes(),'application/javascript; charset=utf-8')
            if path in ('/maps.js','/maps.css','/guide.js','/workspace.js','/booking.js','/stages.js','/shell.js'):
                name=path.lstrip('/')
                mime='application/javascript; charset=utf-8' if name.endswith('.js') else 'text/css; charset=utf-8'
                return self.respond(200,(STATIC/name).read_bytes(),mime)
            if path=='/archivo.woff2':return self.respond(200,(STATIC/'archivo.woff2').read_bytes(),'font/woff2')
            if path in ('/wix-madefor-display.woff2','/wix-madefor-text.woff2'):return self.respond(200,(STATIC/path.lstrip('/')).read_bytes(),'font/woff2')
            if path=='/chivo-mono.woff2':return self.respond(200,(STATIC/'chivo-mono.woff2').read_bytes(),'font/woff2')
            if path in ('/','/app.js','/style.css','/instrument-sans.woff2'):
                name={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/instrument-sans.woff2':'instrument-sans.woff2'}[path]
                mime={'/':'text/html; charset=utf-8','/app.js':'application/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8','/instrument-sans.woff2':'font/woff2'}[path]
                return self.respond(200,(STATIC/name).read_bytes(),mime)
            if not portal.authenticated(self.headers.get('Cookie'),self.headers.get('X-Goog-IAP-JWT-Assertion')):
                if path=='/maps':
                    self.send_response(302);self.headers_secure();self.send_header('Location','/');self.send_header('Content-Length','0');self.end_headers();return
                return self.respond(401,{'error':'Sign in to the staff portal'})
            if path=='/dashboard' or path.startswith('/dashboard/'):return self.dashboard_file(path)
            if path=='/reports':
                origin=dashboard_asset_origin()
                if not origin:return self.respond(503,{'error':'Reporting assets are not configured'})
                body=(STATIC/'reports.html').read_text(encoding='utf-8').replace('__ASSETS__',html.escape(origin,quote=True))
                return self.respond(200,body.encode(),'text/html; charset=utf-8')
            if path=='/api/reporting':
                loaded=self.business_data()
                if loaded is None:return
                from webapp.reporting import build
                value,snapshot=loaded
                return self.respond(200,build(value,snapshot))
            if path=='/api/return-risk':
                loaded=self.business_data()
                if loaded is None:return
                from webapp import return_risk,predictions
                try:
                    requested_calls=parse_qs(urlsplit(self.path).query).get('calls',['all'])[0]
                    calls=10000 if requested_calls=='all' else max(0,min(60,int(requested_calls)))
                except ValueError:return self.respond(400,{'error':'Calls must be a whole number from 0 to 60'})
                try:log,generation=portal.action_store.load();available=True
                except Exception:log,generation,available=None,None,False
                try:
                    result=return_risk.live(portal.folder,loaded[0],predictions.today(),calls,log)
                    result.update(revision=generation,log_available=available)
                    return self.respond(200,result)
                except (ValueError,KeyError,TypeError):return self.respond(503,{'error':'Return-risk scores could not be built from the current release.'})
            if path=='/api/workspace':
                try:result=self.workspace_data(parse_qs(urlsplit(self.path).query).get('week',[None])[0])
                except ValueError:return self.respond(400,{'error':'Choose the current week or next week'})
                if result is not None:return self.respond(200,result)
                return
            if path=='/api/booking':
                portal.state()
                from webapp import booking
                try:return self.respond(200,booking.overview(booking.load(portal.folder)))
                except (ValueError,KeyError,TypeError):return self.respond(503,{'error':'The booking schedule needs checking'})
            if path=='/maps':return self.respond(200,(STATIC/'maps.html').read_bytes(),'text/html; charset=utf-8')
            if path=='/api/spatial':
                loaded=self.business_data()
                if loaded is None:return
                try:
                    from webapp.spatial import payload
                    business,snapshot=loaded
                    evaluated=json.loads((portal.folder/'area_rows_private.json').read_text())
                    boundaries=json.loads((portal.folder/'district_boundaries_public.json').read_text())
                    return self.respond(200,payload(business,snapshot,evaluated,boundaries))
                except (FileNotFoundError,ValueError,KeyError,TypeError):
                    return self.respond(503,{'error':'Map sources are unavailable. The last reporting release remains intact.'})
            if path=='/api/access':
                from webapp import access
                who=portal.iap_email(self.headers.get('X-Goog-IAP-JWT-Assertion'))
                if not access.is_admin(who):return self.respond(403,{'error':'Only the owner account can manage access'})
                try:return self.respond(200,{'members':access.members(),'owners':sorted(access.admins()),'you':who})
                except Exception as e:return self.respond(503,{'error':str(e)})
            if path=='/api/state':return self.respond(200,portal.state())
            if path=='/api/analytics':
                loaded=self.business_data()
                if loaded is None:return
                value,snapshot=loaded
                try:
                    from webapp import analytics,predictions,planning
                    from webapp.followup import review_queue
                    contracts=[{'name':c['name'],**k} for c in value['customers'] for k in c.get('contracts',[])]
                    as_of=predictions.today()
                    try:repeat=predictions.repeat_ranking(value['customers'])
                    except (FileNotFoundError,ValueError,KeyError):repeat={'customers':[],'eligible_customers':0}
                    work=self.workspace_data() or {}
                    models=Path(__file__).parent/'models'
                    return self.respond(200,analytics.build(value,snapshot,planning.load(portal.folder),repeat,
                        json.loads((models/'return30_evidence.json').read_text()),json.loads((models/'return_research_best.json').read_text()),
                        review_queue(contracts,as_of),work,as_of))
                except (ValueError,KeyError,TypeError):
                    return self.respond(503,{'error':'Analytics could not be built from the current release.'})
            if path in ('/api/planning','/api/payment-followup'):
                loaded=self.business_data()
                if loaded is None:return
                value,snapshot=loaded
                from webapp import predictions
                if path=='/api/planning':
                    calendar_dates=[r.get('extracted_at_utc') for r in snapshot.get('tables',{}).get('freshness',[]) if r.get('source_name')=='calendar' and r.get('extracted_at_utc')]
                    observed=min(datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kuala_Lumpur')).date() for v in calendar_dates) if calendar_dates else None
                    forecast=predictions.booking_forecast(value['records'],observed_through=observed) if observed else {'status':'source_freshness_missing','message':'Calendar freshness must be available before forecasting.'}
                    try:repeat=predictions.repeat_ranking(value['customers'])
                    except (FileNotFoundError,ValueError,KeyError):
                        return self.respond(503,{'error':'The repeat-purchase model is unavailable. Customer search and payment tools remain available.'})
                    from webapp import planning
                    return self.respond(200,{'bookings':forecast,'planning':planning.load(portal.folder),
                        'research_best':json.loads((Path(__file__).parent/'models/return_research_best.json').read_text()),
                        'return_evidence':json.loads((Path(__file__).parent/'models/return30_evidence.json').read_text()),
                        'repeat_purchase':repeat,'receipt':value['receipt']})
                contracts=[]
                for customer in value['customers']:
                    for contract in customer.get('contracts',[]):
                        contracts.append({'name':customer['name'],**contract})
                contracts.sort(key=lambda c:(c.get('next_scheduled_reminder_date') is None,str(c.get('next_scheduled_reminder_date') or ''),c['name']))
                from webapp.followup import review_queue
                from webapp.predictions import today
                return self.respond(200,{'contracts':contracts,'review_queue':review_queue(contracts,today()),'receipt':value['receipt'],
                    'notice':'Sales recorded amounts and staff reminder dates only. A past date does not mean overdue, paid or sent.'})
            if path=='/api/business':
                loaded=self.business_data()
                if loaded is None:return
                value,_=loaded
                from webapp.business import aggregate,validate_period
                q=parse_qs(urlsplit(self.path).query)
                start=q.get('start',[''])[0];end=q.get('end',['9999-12-31'])[0]
                try:validate_period(start,end)
                except ValueError:return self.respond(400,{'error':'Use valid dates, with From on or before To.'})
                records=value['records']
                selected={**records,'sales':[r for r in records['sales'] if r['date'] and start<=r['date']<=end],
                    'appointments':[r for r in records['appointments'] if start<=r['date']<=end]}
                report=aggregate(selected)
                districts={}
                for r in report['sales']:
                    d=districts.setdefault(r['district'],{'district':r['district'],'sales_rm':0,'sale_rows':0,'appointments':0})
                    d['sales_rm']+=r['sales_rm'];d['sale_rows']+=r['sale_rows']
                for r in selected['appointments']:
                    d=districts.setdefault(r['district'],{'district':r['district'],'sales_rm':0,'sale_rows':0,'appointments':0})
                    d['appointments']+=1
                return self.respond(200,{'districts':sorted(districts.values(),key=lambda r:r['sales_rm'],reverse=True),
                    'receipt':value['receipt'],'period':{'start':start,'end':end},
                    'unknown_date_sales':sum(not r['date'] for r in records['sales'])})
            if path=='/api/assistant/status':return self.respond(410,{'error':'The AI assistant has been removed'})
            if path=='/api/area/boundaries':
                p=portal.folder/'district_boundaries_public.json'
                if not p.exists():return self.respond(503,{'error':'District boundaries not prepared'})
                return self.respond(200,json.loads(p.read_text()))
            if path=='/api/area/radius':
                try:
                    q=parse_qs(urlsplit(self.path).query)
                    vals=[float(q[k][0]) for k in ('lat','lon','km')]
                    rows=json.loads((portal.folder/'area_rows_private.json').read_text())
                    return self.respond(200,radius_result(rows,*vals))
                except FileNotFoundError:return self.respond(503,{'error':'Historical area evaluation not prepared'})
                except (ValueError,KeyError,IndexError):return self.respond(400,{'error':'Choose a valid Malaysian centre and radius from 1 to 50 km'})
            return self.respond(404,{'error':'Not found'})
        def do_POST(self):
            if not self.host_ok():return self.respond(403,{'error':'Host not allowed'})
            origin=self.headers.get('Origin','')
            if urlsplit(origin).netloc!=self.headers.get('Host') or urlsplit(origin).scheme not in ('http','https'):
                return self.respond(403,{'error':'Same-origin request required'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<1 or size>8192:raise ValueError()
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict):raise ValueError()
            except (ValueError,json.JSONDecodeError):return self.respond(400,{'error':'Invalid request'})
            path=urlsplit(self.path).path
            if path=='/api/access':
                from webapp import access
                if not portal.authenticated(self.headers.get('Cookie'),self.headers.get('X-Goog-IAP-JWT-Assertion')):
                    return self.respond(401,{'error':'Sign in to the staff portal'})
                who=portal.iap_email(self.headers.get('X-Goog-IAP-JWT-Assertion'))
                if not access.is_admin(who):return self.respond(403,{'error':'Only the owner account can manage access'})
                try:return self.respond(200,{'members':access.change(str(payload.get('action','')),str(payload.get('email','')),who)})
                except ValueError as e:return self.respond(400,{'error':str(e)})
                except Exception as e:return self.respond(503,{'error':str(e)})
            if path=='/api/login':
                with portal.login_lock:
                    portal.login_attempts=[t for t in portal.login_attempts if time.monotonic()-t<60]
                    if len(portal.login_attempts)>=20:return self.respond(429,{'error':'Too many sign-in attempts. Try again in a minute.'})
                    portal.login_attempts.append(time.monotonic())
                # Username + password sign-in. Locally (no staff code configured) the
                # development credentials are admin / admin; a configured staff code
                # becomes the password. Remote hosting still refuses short codes (see main).
                supplied=payload.get('password',payload.get('token',''))
                username=payload.get('username',portal.username if 'token' in payload else None)
                expected=portal.token or 'admin'
                if not isinstance(supplied,str) or not isinstance(username,str) or \
                   not (hmac.compare_digest(username.strip().casefold(),portal.username.casefold()) & hmac.compare_digest(supplied,expected)):
                    return self.respond(401,{'error':'Incorrect username or password'})
                cookie='cp2_session='+portal.session()+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'
                if os.environ.get('CP2_COOKIE_SECURE')=='1':cookie+='; Secure'
                return self.respond(200,{'status':'signed_in'},cookie=cookie)
            if not portal.authenticated(self.headers.get('Cookie'),self.headers.get('X-Goog-IAP-JWT-Assertion')):return self.respond(401,{'error':'Sign in required'})
            if path=='/api/booking/options':
                portal.state()
                from webapp import booking
                try:return self.respond(200,booking.options(booking.load(portal.folder),payload))
                except (ValueError,KeyError,TypeError):return self.respond(400,{'error':'Check the area, date, working hours, duration and confirmed teams. Refresh if the appointment to move has changed.'})
            if path in ('/api/workspace/actions','/api/workspace/assist'):
                try:work=self.workspace_data(payload.get('week'))
                except ValueError:return self.respond(400,{'error':'Choose the current week or next week'})
                if work is None:return
                from webapp import workspace
                from webapp.action_log import Conflict
                try:
                    if path.endswith('/assist'):return self.respond(200,workspace.brief(work,payload.get('intent')))
                    if not work['log_available']:return self.respond(503,{'error':'Progress storage is unavailable. Source records are unchanged.'})
                    if payload.get('kind')=='capacity':
                        decision=workspace.capacity_decision(work,payload.get('capacity_hours'),payload.get('buffer_hours',0))
                        key='capacity:'+work['week_start']
                        change={k:decision[k] for k in ('capacity_hours','buffer_hours')}
                        change.update(week_start=work['week_start'],source_release=work['release'],
                            forecast_origin=(work['planning'].get('live',{}).get('latest') or {}).get('origin') if work['current_forecasts'] else None,
                            planning_protocol_sha256=work['planning'].get('evidence',{}).get('protocol_sha256'),decision_at_save=decision)
                    else:
                        task=next((r for r in work['tasks'] if r['id']==payload.get('id')),None)
                        if task is None or task['evidence_hash']!=payload.get('evidence_hash'):
                            return self.respond(409,{'error':'The source facts changed. Refresh this item before saving.'})
                        status=payload.get('status');note=payload.get('note','')
                        if status not in ('open','reviewed','waiting','contacted') or not isinstance(note,str) or len(note)>400:
                            raise ValueError('Choose a review status and a note of at most 400 characters')
                        key=task['id'];change={'status':status,'note':note.strip(),'evidence_hash':task['evidence_hash'],'source_release':work['release']}
                    actor='local-staff'
                    if os.environ.get('CP2_AUTH_MODE')=='iap':
                        # The assertion has already passed signature, issuer and audience validation above.
                        encoded=self.headers['X-Goog-IAP-JWT-Assertion'].split('.')[1]
                        claims=json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)))
                        actor='staff-'+hashlib.sha256(claims['sub'].encode()).hexdigest()[:16]
                    portal.action_store.update(key,change,payload.get('revision'),actor)
                    return self.respond(200,{'status':'saved','scope':'Internal workspace only; source records and message delivery unchanged'})
                except Conflict as exc:return self.respond(409,{'error':str(exc)})
                except ValueError as exc:return self.respond(400,{'error':str(exc)})
                except Exception:return self.respond(503,{'error':'Could not save workspace progress. Source records are unchanged.'})
            if path=='/api/return-risk/outcome':
                if self.business_data() is None:return
                from webapp import return_risk,predictions
                from webapp.action_log import Conflict
                try:
                    key,change=return_risk.record(portal.folder,payload.get('sale_id'),payload.get('serviced',''),
                        payload.get('status'),payload.get('note',''),predictions.today(),payload.get('minutes'))
                    actor='local-staff'
                    if os.environ.get('CP2_AUTH_MODE')=='iap':
                        encoded=self.headers['X-Goog-IAP-JWT-Assertion'].split('.')[1]
                        claims=json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)))
                        actor='staff-'+hashlib.sha256(claims['sub'].encode()).hexdigest()[:16]
                    portal.action_store.update(key,change,payload.get('revision'),actor)
                    return self.respond(200,{'status':'saved','scope':'Internal check-in log only; source records unchanged'})
                except Conflict as exc:return self.respond(409,{'error':str(exc)})
                except FileNotFoundError:return self.respond(503,{'error':'Live scoring is not connected yet'})
                except ValueError as exc:return self.respond(400,{'error':str(exc)})
                except Exception:return self.respond(503,{'error':'Could not save the check-in. Source records are unchanged.'})
            if path=='/api/logout':return self.respond(200,{'status':'signed_out'},cookie='cp2_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if path=='/api/business/radius':
                loaded=self.business_data()
                if loaded is None:return
                try:
                    from webapp.business import radius
                    value,_=loaded
                    result=radius(value['records'],*(float(payload[k]) for k in ('lat','lon','km')),start=payload.get('start',''),end=payload.get('end','9999-12-31'))
                    return self.respond(200,result)
                except FileNotFoundError:return self.respond(503,{'error':'Business analytics unavailable'})
                except (ValueError,TypeError,KeyError):return self.respond(400,{'error':'Choose a valid Malaysian centre and radius from 1 to 50 km'})
            if path=='/api/customers':
                loaded=self.business_data()
                if loaded is None:return
                value,_=loaded
                search=payload.get('q','')
                if not isinstance(search,str):return self.respond(400,{'error':'Invalid search'})
                search=search.casefold().strip()[:120]
                customers=value['customers']
                if search: customers=[c for c in customers if search in c['name'].casefold() or any(search in str(s['sale_id']).casefold() for s in c['sales'])]
                # Filter by relationship and choose the order; the summary describes every matching group.
                kind=payload.get('relationship','all')
                keep={'all':lambda c:True,'repeat':lambda c:bool(c.get('repeat_customer')),
                      'single':lambda c:not c.get('repeat_customer') and c.get('identity_status')!='needs_review',
                      'review':lambda c:c.get('identity_status')=='needs_review'}.get(kind)
                if keep is None:return self.respond(400,{'error':'Choose a valid customer group'})
                customers=[c for c in customers if keep(c)]
                order={'sales':(lambda c:-c['sales_rm']),'programmes':(lambda c:(-c.get('purchase_count',0),-c['sales_rm'])),
                       'name':(lambda c:c['name'].casefold())}.get(payload.get('sort','sales'))
                if order is None:return self.respond(400,{'error':'Choose a valid order'})
                customers=sorted(customers,key=order)
                summary={'groups':len(customers),'sales_rm':round(sum(c['sales_rm'] for c in customers),2),
                         'repeat':sum(1 for c in customers if c.get('repeat_customer')),
                         'needs_review':sum(1 for c in customers if c.get('identity_status')=='needs_review')}
                return self.respond(200,{'customers':customers[:50],'matching_groups':len(customers),'summary':summary,'receipt':value['receipt']})
            if path=='/api/assistant':return self.respond(410,{'error':'The AI assistant has been removed'})
            return self.respond(404,{'error':'Not found'})
    return Handler

def main():
    p=argparse.ArgumentParser();p.add_argument('--host',default=os.environ.get('CP2_HOST','127.0.0.1'))
    p.add_argument('--port',type=int,default=int(os.environ.get('PORT','8088')))
    p.add_argument('--data',default=os.environ.get('CP2_PORTAL_DATA','outputs/portal'));args=p.parse_args()
    if os.environ.get('CP2_AUTH_MODE')=='iap' and not os.environ.get('CP2_IAP_AUDIENCE'):
        raise SystemExit('IAP mode requires the protected service audience')
    if args.host not in ('localhost','127.0.0.1') and os.environ.get('CP2_AUTH_MODE')!='iap' and len(os.environ.get('CP2_PORTAL_TOKEN',''))<24:
        raise SystemExit('A staff access code of at least 24 characters is required for remote hosting')
    portal=Portal(args.data)
    threading.Thread(target=portal.refresh_loop,daemon=True).start()
    server=ThreadingHTTPServer((args.host,args.port),handler_for(portal))
    print(f'Nomobug portal listening on {args.host}:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
