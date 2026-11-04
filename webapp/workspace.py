"""Decision support from published facts; no source edits or customer messaging."""
from datetime import datetime,timedelta,date
from zoneinfo import ZoneInfo
import hashlib,json,math,re

MY=ZoneInfo('Asia/Kuala_Lumpur')
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()
def number(value):
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (ValueError,TypeError):return None

def build(business,snapshot,planning,log=None,now=None,week=None):
    from webapp.followup import review_queue
    now=now or datetime.now(MY);today=now.astimezone(MY).date()
    current_monday=today-timedelta(days=today.weekday());next_monday=current_monday+timedelta(days=7)
    live=planning.get('live',{});origin=(live.get('latest') or {}).get('origin','')[:10]
    allowed=(current_monday.isoformat(),next_monday.isoformat())
    if week is not None and week not in allowed:raise ValueError('Choose the current week or next week')
    default=origin if origin in allowed and not live.get('stale') else next_monday.isoformat()
    first=planning.get('evidence',{}).get('first_origin')
    if not origin and first==current_monday.isoformat():default=first
    start=date.fromisoformat(week or default)
    records=(log or {}).get('records',{})
    contracts=[{'name':c['name'],**r} for c in business['customers'] for r in c.get('contracts',[])]
    queue=review_queue(contracts,today);tasks=[]
    counts={**queue['counts'],'source_upcoming':queue['counts']['upcoming'],'status':0}
    for row in queue['tasks']:
        row=dict(row)
        status_note=bool(re.search(r'\b(cancelled|canceled|relocat\w*)\b',str(row.get('name','')),re.I))
        if status_note:
            counts[row['review_kind']]-=1;counts['status']+=1
            row.update(review_kind='status',review_reason='Cancellation or relocation note · confirm contract status',
                       review_action='Confirm whether the contract and payment arrangement are still active before preparing a reminder.')
        key=digest([row.get('sales_record_id'),row['review_kind'],row.get('next_scheduled_reminder_date')])
        evidence=digest({k:row.get(k) for k in ('sales_record_id','review_kind','next_scheduled_reminder_date','sales_remaining_balance_rm','sales_total_recorded_paid_rm')})
        saved=records.get(key,{})
        changed=bool(saved and saved.get('evidence_hash')!=evidence)
        status='open' if changed else saved.get('status','open')
        draft=(f"Hi {row['name']}, this is Nomobug. We're checking the payment arrangement for {row.get('sales_record_id') or 'your package'}. "
               "Could you confirm the next agreed payment date and let us know if you've already paid? Thank you.")
        tasks.append({**row,'id':key,'evidence_hash':evidence,'status':status,'source_changed':changed,
                      'note':saved.get('note',''),'updated_at':saved.get('updated_at'),'draft':None if status_note else draft})
    freshness=snapshot.get('tables',{}).get('freshness',[])
    relevant=[r.get('extracted_at_utc') for r in freshness if r.get('source_name') in ('sales','recurring_payments','calendar')]
    oldest=min(relevant) if len(relevant)==3 and all(relevant) else None
    stale=True if not oldest else now-datetime.fromisoformat(oldest.replace('Z','+00:00'))>timedelta(hours=36)
    upcoming=snapshot.get('tables',{}).get('upcoming')
    calendar=[r for r in (upcoming or []) if max(today,start).isoformat()<=str(r['service_date'])<(start+timedelta(days=7)).isoformat()]
    # Never apply last week's forecast to the next planning week.
    forecasts=live.get('forecasts',[]) if origin==start.isoformat() and not live.get('stale') else []
    capacity=records.get('capacity:'+start.isoformat(),{}).get('capacity_hours')
    settings={'capacity_hours':capacity,'buffer_hours':records.get('capacity:'+start.isoformat(),{}).get('buffer_hours',0)}
    result={'today':today.isoformat(),'week_start':start.isoformat(),'week_end':(start+timedelta(days=6)).isoformat(),
            'week_options':[{'start':current_monday.isoformat(),'label':'Current week'},{'start':next_monday.isoformat(),'label':'Next week'}],
            'release':business['receipt'].get('published_release'),'source_updated':oldest,'source_stale':stale,
            'tasks':tasks,'counts':{**counts,'open':sum(r['status']=='open' for r in tasks),
                'reviewed':sum(r['status']!='open' for r in tasks),'total':len(tasks)},
            'schedule':{'available':upcoming is not None,'rows':calendar,'coverage_start':max(today,start).isoformat(),
                'bookings':sum(int(r['scheduled_event_rows']) for r in calendar) if upcoming is not None else None,
                'updated_at':min((str(r['extracted_at']) for r in upcoming),default=None) if upcoming is not None else None},
            'planning':planning,'current_forecasts':forecasts,'settings':settings,
            'notice':queue['notice'],'log_available':True}
    result['plan_summary']=planning_summary(result)
    return result

def planning_summary(work):
    """Describe the next planning decision without inventing team capacity."""
    settings=work['settings'];capacity=settings.get('capacity_hours')
    forecast=next((r for r in work['current_forecasts'] if r['id']=='booked_hours_h1'),None)
    if work['source_stale']:
        status,title,action='check_sources','Check source freshness','Refresh the source records before using a forecast to change the plan.'
    elif not forecast:
        status,title,action='waiting','Confirm existing bookings','No verified appointment-hours forecast is available for this week. Use the recorded bookings while waiting.'
    elif capacity is None:
        status,title,action='enter_capacity','Compare demand with your available hours','Enter the full-week appointment hours the teams can offer. The system cannot infer spare capacity from booking counts.'
    else:
        decision=capacity_decision(work,capacity,settings.get('buffer_hours',0))
        status=decision['status'];title='Review appointment availability' if status=='shortfall' else 'Demand fits your saved scenario'
        action=decision['message']
    by_day={};by_team={}
    for row in work['schedule']['rows']:
        count=int(row['scheduled_event_rows']);day=str(row['service_date']);team=row['calendar_name']
        by_day[day]=by_day.get(day,0)+count;by_team[team]=by_team.get(team,0)+count
    return {'status':status,'title':title,'action':action,
            'forecast_hours':number(forecast['prediction']) if forecast else None,
            'capacity_hours':capacity,'buffer_hours':settings.get('buffer_hours',0),
            'busiest_days':[{'date':day,'bookings':count} for day,count in sorted(by_day.items(),key=lambda v:(-v[1],v[0]))[:3]],
            'team_bookings':[{'team':team,'bookings':count} for team,count in sorted(by_team.items(),key=lambda v:(-v[1],v[0]))],
            'notice':'Booking concentration is not a staffing shortage. Capacity is staff-entered; forecasts are experimental.'}

def capacity_decision(work,capacity,buffer=0):
    capacity=number(capacity);buffer=number(buffer)
    if capacity is None or not 0<=capacity<=2000 or buffer is None or not 0<=buffer<=500:
        raise ValueError('Enter 0–2,000 appointment hours and a buffer of 0–500 hours')
    forecast=next((r for r in work['current_forecasts'] if r['id']=='booked_hours_h1'),None)
    if not forecast or work['source_stale']:
        return {'status':'waiting_for_verified_forecast','capacity_hours':capacity,'buffer_hours':buffer,
                'message':'Capacity saved as a staff assumption. A fresh forecast for this exact week is needed before comparing demand.'}
    demand=number(forecast['prediction'])
    if demand is None or demand<0:raise ValueError('Invalid forecast')
    total=demand+buffer;gap=total-capacity
    return {'status':'shortfall' if gap>0 else 'within_plan','capacity_hours':capacity,'buffer_hours':buffer,
            'forecast_hours':demand,'planned_demand_hours':round(total,1),'gap_hours':round(abs(gap),1),
            'additional_booking_hours':round(max(0,demand-float(forecast.get('already_booked',0))),1),
            'message':(f'Review an additional {gap:.1f} appointment-slot hours with the team before accepting more work.' if gap>0 else
                       f'{abs(gap):.1f} appointment-slot hours remain against this planning scenario. Keep a buffer for changes.'),
            'notice':'Planning scenario, not a capacity guarantee. Buffer is staff-selected; historical error is not a calibrated prediction interval.'}

def brief(work,intent):
    if intent not in ('brief','plan','payments'):raise ValueError('Choose a supported workspace task')
    c=work['counts'];prefix='The published sources need checking for freshness. ' if work['source_stale'] else ''
    if intent=='plan':
        body=(f"{work['schedule']['bookings']} appointments are recorded for {work['week_start']}–{work['week_end']}. " if work['schedule']['available'] else 'The advance-booking feed is unavailable. ')
        summary=planning_summary(work)
        body+=summary['action']
        if summary['forecast_hours'] is not None:
            body+=f" The saved forecast is {summary['forecast_hours']:.1f} appointment hours for the full week."
        booking_forecast=next((r for r in work['current_forecasts'] if r['id']=='booking_entries_h2'),None)
        if booking_forecast and number(booking_forecast.get('prediction')) is not None:
            body+=f" The separate two-week forecast is {float(booking_forecast['prediction']):.1f} booking entries; it is not a one-week estimate."
        body+=' Booking counts do not show whether individual teams have free slots. No roster has been changed.'
        actions=[{'label':'Build the weekly plan','href':'#plan'}]
    else:
        body=(f"{c['upcoming']} contracts have a reminder date in the next seven days. "
              f"{c['missing']} have a positive recorded balance but no next reminder date, {c['unknown']} have an unknown balance, and {c['status']} have a cancellation or relocation note to clarify. "
              'Open the contract, verify the latest Sales record, then prepare a message if appropriate. A past reminder date does not establish an overdue payment.')
        if intent=='brief':body+=' For staffing, use the weekly planner to compare recorded demand with the hours the team can actually offer.'
        actions=[{'label':'Work through follow-ups','href':'#home'},{'label':'Open weekly planner','href':'#plan'}]
    return {'answer':prefix+body,'actions':actions,'source_release':work['release'],
            'source_updated':work['source_updated'],'provider':'Verified workspace brief',
            'notice':'Built directly from the published records. No customer was contacted and no source record was changed.'}
