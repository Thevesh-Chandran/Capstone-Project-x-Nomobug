"""Experimental planning tools. No writes to the frozen v5 experiment."""
import json
import math
from collections import Counter
from datetime import date,datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

MODEL=Path(__file__).parent/'models/repeat90_v1.json'


def today():return datetime.now(ZoneInfo('Asia/Kuala_Lumpur')).date()


def booking_forecast(records,as_of=None,observed_through=None):
    as_of=as_of or today();monday=as_of-timedelta(days=as_of.weekday())
    # A Sunday extraction may still omit Sunday evening bookings. Require
    # extraction on/after Monday before treating the preceding week as whole.
    if observed_through is not None and observed_through<monday:
        return {'status':'stale_history','message':'The Calendar snapshot does not cover the last complete week. Refresh the source before forecasting.'}
    days=Counter(r['date'] for r in records.get('appointments',[]))
    weeks=[]
    for i in range(4,0,-1):
        start=monday-timedelta(weeks=i)
        count=sum(days[(start+timedelta(days=j)).isoformat()] for j in range(7))
        weeks.append({'week_start':start.isoformat(),'bookings':count})
    dates=[date.fromisoformat(r['date']) for r in records.get('appointments',[]) if r.get('date')]
    if not dates or min(dates)>monday-timedelta(weeks=4):
        return {'status':'insufficient_history','message':'Four complete recorded weeks are required.'}
    estimate=sum(r['bookings'] for r in weeks)/4
    targets=[]
    for offset in (0,1):
        start=monday+timedelta(weeks=offset)
        targets.append({'week_start':start.isoformat(),'week_end':(start+timedelta(days=6)).isoformat(),
            'estimate':estimate,'currently_booked':sum(days[(start+timedelta(days=j)).isoformat()] for j in range(7)),
            'horizon_from_last_complete_week':offset+1,'week_already_started':as_of>start})
    return {'status':'experimental','method':'Average of previous four complete weeks','as_of_date':as_of.isoformat(),
        'history':weeks,'weeks':targets,'historical_diagnostic_mae':9.3125,'historical_test_weeks':12,
        'notice':'Planning estimate, not completed work or capacity. Booking counts are from the published snapshot, not live availability. Historical error covers one-week forecasts only. The next-week estimate midweek has a longer lead and is not separately validated. These are current estimates, not backdated prospective receipts.'}


def initial_features(sales):
    first=min(s['date'] for s in sales)
    initial=[s for s in sales if s['date']==first];month=date.fromisoformat(first).month
    category=lambda key:' | '.join(sorted(set(str(s.get(key) or 'Unknown') for s in initial)))
    return {'log_initial_sales':math.log1p(max(0,sum(float(s['sales_rm'] or 0) for s in initial))),
        'missing_amount':int(any(s['sales_rm'] is None for s in initial)),
        'month_sin':math.sin(month*2*math.pi/12),'month_cos':math.cos(month*2*math.pi/12),
        'package':category('package'),'pest':category('pest'),'premise':category('premise')}


def rank_score(features,model):
    values=[]
    for i,key in enumerate(model['numeric_features']):
        value=features.get(key)
        if value is None or not math.isfinite(float(value)):value=model['imputer'][i]
        values.append((float(value)-model['mean'][i])/model['scale'][i])
    for key,categories in zip(model['categorical_features'],model['categories']):
        values.extend(float(features.get(key)==category) for category in categories)
    raw=model['baseline']
    for tree in model['trees']:
        index=0
        while not tree[index]['leaf']:
            node=tree[index];value=values[node['feature']]
            index=node['left'] if value<=node['threshold'] else node['right']
        raw+=tree[index]['value']
    return 1/(1+math.exp(-max(-700,min(700,raw))))


def repeat_ranking(customers,as_of=None,model=None):
    as_of=as_of or today();model=model or json.loads(MODEL.read_text(encoding='utf-8'));ranked=[]
    excluded=Counter()
    for customer in customers:
        if customer['identity_status']=='needs_review':excluded['uncertain_identity']+=1;continue
        if any(not s.get('date') for s in customer['sales']):excluded['unknown_purchase_date']+=1;continue
        sales=[s for s in customer['sales'] if s['date']<=as_of.isoformat()]
        if not sales:continue
        first=min(s['date'] for s in sales);age=(as_of-date.fromisoformat(first)).days
        if age<0 or age>90:excluded['outside_90_day_window']+=1;continue
        programmes={s['programme_id'] for s in sales}
        if len(programmes)>1:excluded['already_bought_another_programme']+=1;continue
        features=initial_features(sales)
        ranked.append({'name':customer['name'],'sale_ids':[s['sale_id'] for s in sales],
            'first_recorded_purchase':first,'days_since_purchase':age,'initial_sales_rm':sum(float(s['sales_rm'] or 0) for s in sales if s['date']==first),
            '_score':rank_score(features,model)})
    ranked.sort(key=lambda r:r['_score'],reverse=True)
    for i,row in enumerate(ranked):row.pop('_score');row['rank']=i+1
    return {'status':'experimental','as_of_date':as_of.isoformat(),'eligible_customers':len(ranked),'customers':ranked[:50],
        'excluded':dict(excluded),'evaluation':model['evaluation'],
        'notice':'Pilot priority list, not calibrated purchase probabilities. Historical evaluation scored first-purchase cohorts; this current list excludes known repeat buyers and is not the same evaluation population. No messages are sent.'}
