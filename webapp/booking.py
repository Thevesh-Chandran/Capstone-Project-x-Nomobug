"""Calendar-fit booking options. No Calendar writes or learned accuracy claims."""
from datetime import datetime, date, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import re

MY = ZoneInfo('Asia/Kuala_Lumpur')
POLICY = Path(__file__).resolve().parents[1] / 'config/cp2_team_coverage.json'

def policy():
    value = json.loads(POLICY.read_text(encoding='utf-8'))
    if value.get('version') != 1 or len(value.get('teams', [])) != 6:
        raise ValueError('Team coverage configuration needs checking')
    return value

def instant(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:raise ValueError('Timezone is required')
    return result.astimezone(MY)

def event_time(value):
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(value)):
        return datetime.combine(date.fromisoformat(value), time.min, MY)
    return instant(value)

def export_snapshot(source, reviews, review_match):
    """Independent, private schedule feed from a fully fetched Calendar snapshot.

    All noncancelled Calendar events block time, including meetings and tentative
    events. Only explicit cancellations/holds and exact reviewed placeholders
    are excluded. No rule excludes a weekday or assumes treatment completion.
    """
    config = policy();teams = {r['calendar_name']:r['id'] for r in config['teams']}
    meta = source['metadata']
    if meta.get('calendar_count') != 6:raise ValueError('All six Calendars must be fetched')
    instant(meta['extracted_at'])
    rows=[];seen=set()
    for e in source['records']:
        if e['calendar_name'] not in teams:raise ValueError('Unexpected Calendar')
        key=hashlib.sha256((e['calendar_id']+'|'+e['event_id']).encode()).hexdigest()
        if key in seen:raise ValueError('Duplicate Calendar event')
        seen.add(key)
        title=str(e.get('summary') or '')
        cancelled=(e.get('status')=='cancelled' or re.search(r'\b(?:CANCELLED|CANCELED)\b',title,re.I))
        held=re.search(r'\b(?:HOLD|PLACEHOLDER|AWAITING\s+(?:CLIENT\s+)?DATE)\b',title,re.I)
        if cancelled or held or review_match(e,reviews):continue
        start,end=event_time(e.get('start_raw')),event_time(e.get('end_raw'))
        if end<=start:raise ValueError('Invalid appointment interval; do not infer a free day')
        rows.append({'key':key,'team_id':teams[e['calendar_name']],
                     'start':start.isoformat(),'end':end.isoformat(),
                     'label':title[:140] or 'Existing Calendar event',
                     'reschedulable':bool(re.match(r'^\s*(?:GPC|TBS|TRBS|TERMITE)\b',title,re.I))})
    return {'version':'booking_v1','captured_at':meta['extracted_at'],
            'window_start':meta['window_start'],'window_end':meta['window_end'],
            'source_snapshot_id':meta['snapshot_id'],
            'calendar_names':sorted(teams),'events':rows,
            'notice':'Independent Calendar schedule, not an approved financial release or proof of attendance.'}

def load(folder):
    path=Path(folder)/'booking_schedule_private.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

def availability(snapshot, now=None):
    now=now or datetime.now(MY)
    if snapshot is None:return 'missing'
    if not isinstance(snapshot,dict):return 'invalid'
    if snapshot.get('version')!='booking_v1':return 'invalid'
    try:
        captured=instant(snapshot['captured_at'])
        expected={t['calendar_name'] for t in policy()['teams']}
        names=snapshot['calendar_names']
        if not isinstance(names,list) or len(names)!=len(expected) or set(names)!=expected:return 'incomplete'
        first=date.fromisoformat(snapshot['window_start']);last=date.fromisoformat(snapshot['window_end'])
        if last<first:return 'invalid'
        if not isinstance(snapshot['events'],list) or len(snapshot['events'])>10000:return 'invalid'
        if not re.fullmatch(r'[0-9a-f]{64}',str(snapshot['source_snapshot_id'])):return 'invalid'
        ids={t['id'] for t in policy()['teams']};seen=set()
        for event in snapshot['events']:
            if not isinstance(event,dict) or event['team_id'] not in ids:return 'invalid'
            if event['key'] in seen or not re.fullmatch(r'[0-9a-f]{64}',event['key']):return 'invalid'
            seen.add(event['key'])
            if not isinstance(event.get('label'),str) or type(event.get('reschedulable')) is not bool:return 'invalid'
            if instant(event['end'])<=instant(event['start']):return 'invalid'
        if captured>now+timedelta(minutes=5):return 'invalid'
        return 'stale' if now-captured>timedelta(hours=36) else 'ready'
    except (KeyError,ValueError,TypeError):return 'invalid'

def overview(snapshot, now=None):
    return {'status':availability(snapshot,now),'captured_at':snapshot.get('captured_at') if snapshot else None,
            'window_start':snapshot.get('window_start') if snapshot else None,
            'window_end':snapshot.get('window_end') if snapshot else None,
            'areas':policy()['booking_areas'],'teams':policy()['teams'],
            'events':snapshot.get('events',[]) if snapshot else [],
            'notice':'Calendar-fit options only. Confirm travel, working hours, breaks and service suitability before booking. Nothing is reserved or moved.'}

def integer(value, lower, upper, label):
    if isinstance(value,bool):raise ValueError(label)
    try:result=int(value)
    except (ValueError,TypeError,OverflowError):raise ValueError(label) from None
    if str(result)!=str(value) or not lower<=result<=upper:raise ValueError(label)
    return result

def options(snapshot, request, now=None):
    now=now or datetime.now(MY);state=availability(snapshot,now)
    if state!='ready':
        return {'status':state,'options':[], 'message':'A fresh, complete Calendar schedule is required. No free slots have been inferred.'}
    area=next((a for a in policy()['booking_areas'] if a['id']==request.get('area')),None)
    if area is None:raise ValueError('Choose a supported area')
    if request.get('visit_type') not in ('treatment','consultation'):raise ValueError('Choose treatment or consultation')
    if request.get('staff_confirmed') is not True:raise ValueError('Confirm working hours, breaks and team suitability')
    day=date.fromisoformat(str(request.get('date')))
    if day<now.astimezone(MY).date() or not date.fromisoformat(snapshot['window_start'])<=day<=date.fromisoformat(snapshot['window_end']):
        raise ValueError('Choose a future date within the captured Calendar period')
    duration=integer(request.get('duration_minutes'),15,480,'Use a duration of 15–480 whole minutes')
    buffer=integer(request.get('travel_buffer_minutes'),0,120,'Use a travel allowance of 0–120 whole minutes')
    try:
        start=datetime.combine(day,time.fromisoformat(request['work_start']),MY)
        end=datetime.combine(day,time.fromisoformat(request['work_end']),MY)
    except (ValueError,KeyError,TypeError):raise ValueError('Enter valid working hours') from None
    if end<=start:raise ValueError('Working end must be after working start')
    approved=request.get('available_teams')
    if not isinstance(approved,list) or not approved or len(approved)>6 or not all(isinstance(t,str) for t in approved) or len(set(approved))!=len(approved):
        raise ValueError('Select the teams whose working hours and service suitability you have checked')
    teams=policy()['teams'];known={t['id'] for t in teams}
    if any(t not in known for t in approved):raise ValueError('Unknown team')
    excluded=request.get('reschedule_key') or None
    if excluded:
        moving=next((e for e in snapshot['events'] if e['key']==excluded and e.get('reschedulable') is True),None)
        if moving is None:raise ValueError('Only a recognised customer appointment can be selected to move')
        if instant(moving['start'])<=now:raise ValueError('Only a future appointment can be selected to reschedule')
    candidates=[];excluded_teams=[]
    for team in teams:
        tid=team['id']
        if tid not in approved:continue
        if not team['active'] or team['visit_type']!=request['visit_type']:
            excluded_teams.append(tid);continue
        if team.get('allowed_regions') and area['region'] not in team['allowed_regions']:
            excluded_teams.append(tid);continue
        role='consultation' if request['visit_type']=='consultation' else 'usual_area' if tid==area['usual'] else 'backup' if team['role']=='backup' else 'cross_area'
        busy=[]
        for event in snapshot['events']:
            if event['team_id']!=tid or event['key']==excluded:continue
            a,b=instant(event['start']),instant(event['end'])
            if b<=a:raise ValueError('Invalid schedule interval')
            busy.append((a-timedelta(minutes=buffer),b+timedelta(minutes=buffer)))
        found=0;cursor=start
        while cursor+timedelta(minutes=duration)<=end:
            finish=cursor+timedelta(minutes=duration)
            if cursor>=now and not any(cursor<b and finish>a for a,b in busy):
                candidates.append({'team_id':tid,'team':team['calendar_name'],'start':cursor.isoformat(),
                    'end':finish.isoformat(),'coverage':role,'travel_buffer_minutes':buffer,
                    'reason':{'usual_area':'Usual team for this area','cross_area':'Cross-area cover','backup':'KL/Selangor backup','consultation':'Consultation team'}[role],
                    'travel_verified':False,'source_snapshot_id':snapshot['source_snapshot_id']})
                found+=1
                if found==3 and request.get('all_slots') is not True:break
            cursor+=timedelta(minutes=15)
    candidates.sort(key=lambda r:({'usual_area':0,'consultation':0,'cross_area':1,'backup':2}[r['coverage']],r['start'],r['team_id']))
    return {'status':'options' if candidates else 'no_fit','options':candidates,
            'captured_at':snapshot['captured_at'],'source_snapshot_id':snapshot['source_snapshot_id'],
            'reschedule_key':excluded,'excluded_teams':excluded_teams,
            'message':'Check the usual team first; cross-area and backup options are listed separately. Travel allowance is your assumption, not a road-time estimate. Nothing is booked or moved.'}
