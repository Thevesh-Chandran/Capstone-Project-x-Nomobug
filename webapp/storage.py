"""Private runtime snapshot delivery; no warehouse grants on the web identity."""
import json
import os
from pathlib import Path
from urllib.parse import quote,urlsplit

FILES=('area_evaluation.json','area_rows_private.json','district_boundaries_public.json','business_snapshot.json')

def location(uri):
    parsed=urlsplit(uri)
    if parsed.scheme!='gs' or not parsed.netloc or parsed.query or parsed.fragment:raise ValueError('Expected a private gs://bucket/prefix location')
    return parsed.netloc,parsed.path.strip('/')

def authorized_session():
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    credentials,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    return AuthorizedSession(credentials)

def pull(uri,folder,session=None):
    bucket,prefix=location(uri);session=session or authorized_session();pending={}
    for name in FILES:
        obj='/'.join(filter(None,[prefix,name]))
        r=session.get(f'https://storage.googleapis.com/storage/v1/b/{quote(bucket,safe="")}/o/{quote(obj,safe="")}?alt=media',timeout=30)
        r.raise_for_status()
        if len(r.content)>20*1024*1024:raise ValueError('Snapshot too large')
        json.loads(r.content);pending[name]=r.content
    # Optional rollout file; an older release keeps its existing core snapshots.
    name = 'business_tools_private.json'
    obj='/'.join(filter(None,[prefix,name]))
    r=session.get(f'https://storage.googleapis.com/storage/v1/b/{quote(bucket,safe="")}/o/{quote(obj,safe="")}?alt=media',timeout=30)
    if r.status_code != 404:
        r.raise_for_status()
        if len(r.content)>20*1024*1024:raise ValueError('Snapshot too large')
        json.loads(r.content);pending[name]=r.content
    # Reporting publishes these two objects separately. Reject a transient
    # mixed release before replacing any last-good local file.
    if 'business_tools_private.json' in pending:
        snapshot=json.loads(pending['business_snapshot.json'])
        tools=json.loads(pending['business_tools_private.json'])
        if snapshot.get('status')=='connected':
            releases={r.get('release_run_id') for r in snapshot.get('tables',{}).get('freshness',[])}
            if (len(releases)!=1 or None in releases
                    or tools.get('receipt',{}).get('published_release')!='cp2r_'+next(iter(releases))):
                raise ValueError('Published source releases differ')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    for name,raw in pending.items():
        temp=folder/(name+'.next');temp.write_bytes(raw);os.replace(temp,folder/name)
    # Planning has its own protocol, schedule and source snapshot. Its failure
    # must not block or roll back the independently reconciled business release.
    try:
        name='planning_forecast.json';obj='/'.join(filter(None,[prefix,name]))
        r=session.get(f'https://storage.googleapis.com/storage/v1/b/{quote(bucket,safe="")}/o/{quote(obj,safe="")}?alt=media',timeout=15)
        if r.status_code!=404:
            r.raise_for_status()
            if len(r.content)>500_000:raise ValueError('Planning snapshot too large')
            value=json.loads(r.content)
            from webapp.planning import EVIDENCE
            expected=json.loads(EVIDENCE.read_text(encoding='utf-8'))
            if value.get('protocol_sha256')!=expected['protocol_sha256'] or value.get('version')!='planning_v1':raise ValueError('Planning protocol mismatch')
            temp=folder/(name+'.next');temp.write_bytes(r.content);os.replace(temp,folder/name)
    except (OSError,ValueError,KeyError,__import__('requests').RequestException):
        pass  # Keep last-good planning file; its own timestamp exposes staleness.
    # Booking availability has its own complete Calendar extraction and freshness.
    # It never extends model outcomes or implies financial Gold was published.
    try:
        name='booking_schedule_private.json';obj='/'.join(filter(None,[prefix,name]))
        r=session.get(f'https://storage.googleapis.com/storage/v1/b/{quote(bucket,safe="")}/o/{quote(obj,safe="")}?alt=media',timeout=15)
        if r.status_code!=404:
            r.raise_for_status()
            if len(r.content)>2*1024*1024:raise ValueError('Booking schedule too large')
            value=json.loads(r.content)
            from webapp.booking import availability
            if availability(value) in ('invalid','incomplete','missing'):raise ValueError('Invalid booking schedule')
            temp=folder/(name+'.next');temp.write_bytes(r.content);os.replace(temp,folder/name)
    except (OSError,ValueError,KeyError,__import__('requests').RequestException):
        pass  # Retain last-good schedule; stale schedules cannot yield options.

    # Return-visit risk predictors: recent recorded services with pre-visit features only.
    # Rejected if any outcome column is present, so a label can never leak into live scores.
    try:
        name='return_risk_predictors.json';obj='/'.join(filter(None,[prefix,name]))
        r=session.get(f'https://storage.googleapis.com/storage/v1/b/{quote(bucket,safe="")}/o/{quote(obj,safe="")}?alt=media',timeout=15)
        if r.status_code!=404:
            r.raise_for_status()
            if len(r.content)>5*1024*1024:raise ValueError('Return-risk predictors too large')
            from webapp.return_risk import validate_predictors
            validate_predictors(json.loads(r.content))
            temp=folder/(name+'.next');temp.write_bytes(r.content);os.replace(temp,folder/name)
    except (OSError,ValueError,KeyError,__import__('requests').RequestException):
        pass  # Keep last-good predictors; the page shows their date.

    # Monthly accuracy check of the return-visit model (small JSON, optional).
    try:
        name='return_risk_monitor.json';obj='/'.join(filter(None,[prefix,name]))
        r=session.get(f'https://storage.googleapis.com/storage/v1/b/{quote(bucket,safe="")}/o/{quote(obj,safe="")}?alt=media',timeout=15)
        if r.status_code!=404:
            r.raise_for_status()
            if len(r.content)>256*1024:raise ValueError('Return-risk monitor too large')
            from webapp.return_risk import validate_monitor
            validate_monitor(json.loads(r.content))
            temp=folder/(name+'.next');temp.write_bytes(r.content);os.replace(temp,folder/name)
    except (OSError,ValueError,KeyError,__import__('requests').RequestException):
        pass  # Keep the last good check.

def publish_business(uri,folder,session=None,name='business_snapshot.json'):
    if name not in ('business_snapshot.json','business_tools_private.json','booking_schedule_private.json','return_risk_predictors.json','return_risk_monitor.json'):raise ValueError('Unapproved runtime snapshot')
    bucket,prefix=location(uri);session=session or authorized_session()
    filename=name
    name='/'.join(filter(None,[prefix,name]))
    base=f'https://storage.googleapis.com/storage/v1/b/{quote(bucket,safe="")}/o/{quote(name,safe="")}'
    previous=session.get(base,timeout=30)
    if previous.status_code==404:generation='0'
    else:previous.raise_for_status();generation=previous.json()['generation']
    url=f'https://storage.googleapis.com/upload/storage/v1/b/{quote(bucket,safe="")}/o'
    r=session.post(url,params={'uploadType':'media','name':name,'ifGenerationMatch':generation},
        data=(Path(folder)/filename).read_bytes(),headers={'Content-Type':'application/json'},timeout=60)
    r.raise_for_status()
    return {'generation':r.json()['generation']}
