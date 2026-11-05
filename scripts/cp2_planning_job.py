"""Independent weekly planning forecast logger. Never touches the pest-return test."""
from __future__ import annotations
import argparse,gzip,hashlib,io,json,os,re,uuid
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
import joblib
import numpy as np
import pandas as pd
import requests
from threadpoolctl import threadpool_limits
from scripts import planning_engine as engine
from webapp import storage

ROOT=Path(__file__).resolve().parents[1]
TZ=ZoneInfo('Asia/Kuala_Lumpur')
PROTOCOL=ROOT/'config/cp2_planning_v1.json'

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),default=str,allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def utcnow():return datetime.now(timezone.utc)
def parse(value):return datetime.fromisoformat(value.replace('Z','+00:00'))

def due_origin(now):
    """Only the final 30 minutes of Sunday can produce next Monday's receipt."""
    local=now.astimezone(TZ)
    if local.weekday()!=6 or local.hour!=23 or local.minute<30:return None
    return datetime.combine(local.date()+timedelta(days=1),datetime.min.time(),TZ)

def timely(receipt,created,protocol_hash):
    if receipt.get('protocol_sha256')!=protocol_hash:return False
    origin=parse(receipt['origin']);capture=parse(receipt['source_started_at']);issued=parse(receipt['issued_at'])
    return origin-timedelta(minutes=30)<=capture<=issued<origin and parse(created)<origin

class Store:
    def __init__(self,uri,session=None):
        self.bucket,self.prefix=storage.location(uri);self.session=session or storage.authorized_session()
    def name(self,key):return '/'.join(filter(None,[self.prefix,key]))
    def url(self,key):return f'https://storage.googleapis.com/storage/v1/b/{quote(self.bucket,safe="")}/o/{quote(self.name(key),safe="")}'
    def read(self,key):
        r=self.session.get(self.url(key),timeout=45)
        if r.status_code==404:return None,None
        r.raise_for_status();meta=r.json()
        raw=self.session.get(self.url(key)+'?alt=media',timeout=60);raw.raise_for_status()
        return raw.content,meta
    def put(self,key,raw,immutable=True,content_type='application/json'):
        generation='0'
        if not immutable:
            r=self.session.get(self.url(key),timeout=45)
            if r.status_code!=404:r.raise_for_status();generation=r.json()['generation']
        url=f'https://storage.googleapis.com/upload/storage/v1/b/{quote(self.bucket,safe="")}/o'
        r=self.session.post(url,params={'uploadType':'media','name':self.name(key),'ifGenerationMatch':generation},data=raw,headers={'Content-Type':content_type},timeout=90)
        if r.status_code==412 and immutable:
            old,meta=self.read(key)
            if old==raw:return meta
            raise ValueError('Immutable planning artifact already exists with different content')
        r.raise_for_status();return r.json()
    def keys(self,prefix):
        url=f'https://storage.googleapis.com/storage/v1/b/{quote(self.bucket,safe="")}/o';token=None;items=[]
        while True:
            r=self.session.get(url,params={'prefix':self.name(prefix),'maxResults':1000,'pageToken':token},timeout=45);r.raise_for_status();v=r.json()
            items.extend(x['name'][len(self.prefix)+1:] if self.prefix else x['name'] for x in v.get('items',[]))
            token=v.get('nextPageToken')
            if not token:break
        return items

def event_frame(records):
    raw=pd.DataFrame(records)
    if raw.empty:raise ValueError('Calendar extraction was empty')
    if raw.duplicated(['calendar_id','event_id']).any():raise ValueError('Duplicate source event identities')
    title=raw.summary.fillna('').str.upper()
    cancelled=raw.status.eq('cancelled')|title.str.contains(r'^\s*CANCEL(?:L)?ED\b',regex=True)
    admin=title.str.contains(r'\b(?:CHECK|REVIEW|CALCULATE)\b.*\bCONVERSION\s+RATE\b',regex=True)
    explicit=title.str.replace(r'\b(?:NO|WITHOUT)\s+WARRANTY\b','',regex=True).str.contains(r'\b(?:WARRANTY|CLAIMS?|CALLBACK)\b',regex=True)
    seq=title.str.extract(r'\b(\d{1,2})\s*/\s*(\d{1,2})\b').apply(pd.to_numeric,errors='coerce')
    consultation=title.str.contains(r'\b(?:CONSULTATION|INSPECTION)\b',regex=True)
    extra=title.str.contains(r'\b(?:EXTRA|COMPLIMENTARY|FOLLOW[- ]?UP)\b',regex=True)
    selected=raw.status.eq('confirmed')&~cancelled&~admin&(explicit|(~consultation&((seq[0]>seq[1])|extra|seq[0].notna())))
    data=raw[selected].copy()
    for src,dst in [('start_raw','start'),('end_raw','end'),('created_raw','created'),('updated_raw','updated')]:
        data[dst]=pd.to_datetime(data[src],utc=True,format='mixed',errors='coerce').dt.tz_convert('Asia/Kuala_Lumpur').dt.tz_localize(None)
    data=data[data.start.ge('2023-10-09')].copy()
    if not data[['start','end','created','updated']].notna().all().all():raise ValueError('Missing Calendar timing')
    data['hours']=(data.end-data.start).dt.total_seconds()/3600
    if not data.hours.between(.25,12).all() or data.is_all_day.any():raise ValueError('Unsupported booking duration')
    data['week']=data.start.dt.to_period('W-SUN').dt.start_time
    data['available']=data[['created','updated']].max(axis=1);data['unit']=1.0
    return data

def weather(end):
    params={'latitude':3.139,'longitude':101.6869,'start_date':'2023-01-01','end_date':end.isoformat(),
      'daily':'precipitation_sum,temperature_2m_mean,relative_humidity_2m_mean','timezone':'Asia/Kuala_Lumpur','models':'era5'}
    r=requests.get('https://archive-api.open-meteo.com/v1/archive',params=params,timeout=90);r.raise_for_status()
    payload=r.json();frame=pd.DataFrame(payload['daily']);frame.index=pd.to_datetime(frame.pop('time'))
    if not frame.index.is_unique or not frame.notna().all().all():raise ValueError('Incomplete released regional weather')
    return payload,frame

def fit_forecasts(records,weather_frame,protocol,origin,captured_at):
    data=event_frame(records);orig=pd.Timestamp(origin.astimezone(TZ).replace(tzinfo=None));known=pd.Timestamp(captured_at.astimezone(TZ).replace(tzinfo=None))
    festivals=json.loads((ROOT/'config/cp2_planning_festivals.json').read_text(encoding='utf-8'))
    if str(origin.year) not in festivals:raise ValueError('Reviewed festival calendar missing for forecast year')
    holidays=pd.DatetimeIndex([pd.Timestamp(f'{year}-{day}') for year,days in festivals.items() for day in days])
    results=[];artifacts={}
    for spec in protocol['targets']:
        horizon=spec['horizon_weeks'];matrix=engine.matrix(data,spec['target'],horizon,weather_frame,holidays,'2024-05-06',orig+pd.Timedelta(weeks=horizon))
        row=matrix[matrix.origin.eq(orig)].iloc[0]
        # Do not train on the final still-open ten minutes of the previous week.
        eligible=matrix[(matrix.outcome_end<=known)&(matrix.last_outcome_update<known)]
        tr=engine.train_rows(eligible,orig,spec['selected']['history_weeks'])
        if len(tr)<8:raise ValueError('Too few mature training windows')
        columns=engine.feature_columns(matrix,spec['selected']['features']);model=engine.estimator(spec['selected']['family'])
        scale=max(1,float(tr.late_additions.mean()))
        with threadpool_limits(limits=2):model.fit(tr[columns],tr.late_additions/scale)
        prediction=float(row.visible)+max(0,float(model.predict(pd.DataFrame([row[columns]]))[0])*scale)
        baseline,_=engine.forecast(eligible,row,spec['baseline'],horizon)
        stream=io.BytesIO();joblib.dump({'model':model,'scale':scale,'features':columns},stream);raw=stream.getvalue()
        task=spec['task'];artifacts[task+'.joblib']=raw
        artifacts[task+'_matrix.json']=canonical(matrix.to_dict('records'))
        results.append({'id':task,'target':spec['target'],'horizon_weeks':horizon,'prediction':prediction,'baseline':baseline,
          'already_booked':float(row.visible),'training_windows':len(tr),'input_count':len(columns),'features':{k:float(row[k]) for k in columns},
          'model_sha256':sha(raw),'model_file':task+'.joblib','window_end':(origin+timedelta(weeks=horizon)).isoformat()})
    return results,artifacts

def evaluate(receipt,created,records,extracted_at,protocol_hash):
    if not timely(receipt,created,protocol_hash):raise ValueError('Late, altered or mismatched forecast receipt')
    data=event_frame(records);results=[]
    for task in receipt['forecasts']:
        end=parse(task['window_end'])
        if extracted_at<end+timedelta(days=3):continue
        start=pd.Timestamp(parse(receipt['origin']).astimezone(TZ).replace(tzinfo=None));finish=pd.Timestamp(end.astimezone(TZ).replace(tzinfo=None))
        rows=data[data.start.ge(start)&data.start.lt(finish)]
        actual=float(len(rows)) if task['target']=='booking_entries' else float(rows.hours.sum())
        results.append({'id':task['id'],'actual':actual,'prediction':task['prediction'],'baseline':task['baseline'],
          'absolute_error':abs(task['prediction']-actual),'baseline_absolute_error':abs(task['baseline']-actual)})
    return results

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    protocol_raw=PROTOCOL.read_bytes();protocol=json.loads(protocol_raw);ph=sha(protocol_raw)
    private=Store(os.environ['CP2_PLANNING_GCS_URI']);public=Store(os.environ['CP2_PORTAL_GCS_URI'])
    private.put('protocol.json',protocol_raw)
    from importlib.metadata import version
    implementation={'engine_sha256':sha(Path(engine.__file__).read_bytes()),'job_sha256':sha(Path(__file__).read_bytes()),
      'packages':{name:version(name) for name in ['numpy','pandas','scikit-learn','joblib']}}
    implementation_hash=sha(canonical(implementation))
    # Any later code/dependency change requires a new declared runtime prefix.
    private.put('implementation.json',canonical(implementation))
    started=utcnow();origin=due_origin(started)
    from scripts import load_calendar_bronze as calendar
    targets=calendar._targets(calendar._local_path(os.getenv('NOMOBUG_GOOGLE_METADATA'),'data/profiles/google_source_metadata.json'))
    end=(origin.astimezone(TZ).date() if origin else started.astimezone(TZ).date())+timedelta(days=15)
    records=calendar._fetch(targets,date(2023,10,9),end);captured=utcnow()
    run=uuid.uuid4().hex;source=canonical(records);source_path=f'sources/{run}/calendar.json.gz'
    private.put(source_path,gzip.compress(source),content_type='application/gzip')
    if args.check:
        # A manual check cannot create a late/backdated primary prediction.
        reference=datetime.combine(started.astimezone(TZ).date()-timedelta(days=started.astimezone(TZ).weekday()),datetime.min.time(),TZ)
        wraw,w=weather(reference.date()-timedelta(days=8))
        fit_forecasts(records,w,protocol,reference,reference)
        private.put(f'checks/{run}.json',canonical({'checked_at':utcnow(),'source_sha256':sha(source),'protocol_sha256':ph,'model_fit_check':True}))
    elif origin and origin.date()>=date.fromisoformat(protocol['first_origin']):
        week=origin.date().isoformat();existing,meta=private.read(f'predictions/{week}.json')
        if existing is None:
            wraw,w=weather(origin.date()-timedelta(days=8));predictions,artifacts=fit_forecasts(records,w,protocol,origin,started)
            for name,raw in artifacts.items():private.put(f'models/{week}/{name}',raw,content_type='application/octet-stream')
            private.put(f'sources/{run}/weather.json',canonical(wraw))
            receipt={'version':'planning_v1','protocol_sha256':ph,'implementation_sha256':implementation_hash,'origin':origin.isoformat(),'source_started_at':started.isoformat(),
              'source_completed_at':captured.isoformat(),'issued_at':utcnow().isoformat(),'source_sha256':sha(source),
              'weather_sha256':sha(canonical(wraw)),'source_path':source_path,'forecasts':predictions}
            # Even a job that runs across midnight remains an auditable miss.
            private.put(f'predictions/{week}.json',canonical(receipt))
    receipts=[];outcomes=[]
    for key in sorted(private.keys('predictions/')):
        raw,meta=private.read(key);r=json.loads(raw)
        if not timely(r,meta['timeCreated'],ph):continue
        if r.get('implementation_sha256')!=implementation_hash:raise ValueError('Forecast implementation differs from its declared runtime')
        week=parse(r['origin']).date().isoformat()
        source_raw,source_meta=private.read(r['source_path'])
        if (source_raw is None or sha(gzip.decompress(source_raw))!=r['source_sha256']
                or parse(source_meta['timeCreated'])>=parse(r['origin'])):
            raise ValueError('Saved source evidence changed or was committed too late')
        for task in r['forecasts']:
            model,_=private.read(f"models/{week}/{task['model_file']}")
            if model is None or sha(model)!=task['model_sha256']:raise ValueError('Saved model hash changed')
        receipts.append(r)
        results=evaluate(r,meta['timeCreated'],records,captured,ph)
        # Each horizon is evaluated once when its own outcome is mature.
        for task in r['forecasts']:
            outcome_key=f"outcomes/{week}/{task['id']}.json";old,_=private.read(outcome_key)
            if old:
                prior=json.loads(old)
                if prior.get('protocol_sha256')!=ph or prior.get('prediction_sha256')!=sha(raw):raise ValueError('Outcome evidence no longer matches its immutable prediction')
                outcomes.extend(prior['results']);continue
            matching=[v for v in results if v['id']==task['id']]
            if matching:
                value={'evaluated_at':captured.isoformat(),'protocol_sha256':ph,'prediction_sha256':sha(raw),'outcome_source_sha256':sha(source),'results':matching}
                private.put(outcome_key,canonical(value));outcomes.extend(matching)
    first=date.fromisoformat(protocol['first_origin']);local=utcnow().astimezone(TZ);expected=[];d=first
    while d<=local.date():
        expected.append(d.isoformat());d+=timedelta(weeks=1)
    observed={parse(r['origin']).date().isoformat() for r in receipts};evaluation=[]
    expected=sorted(set(expected)|observed)
    for week in expected:
        deadline=datetime.combine(date.fromisoformat(week),datetime.min.time(),TZ)
        if week not in observed and deadline<=utcnow():
            key=f'misses/{week}.json';prior,_=private.read(key)
            if prior is None:private.put(key,canonical({'week':week,'deadline':datetime.combine(date.fromisoformat(week),datetime.min.time(),TZ).isoformat(),'first_observed_at':utcnow().isoformat(),'reason':'No verified timely receipt; never backfill'}))
    for spec in protocol['targets']:
        rows=[r for r in outcomes if r['id']==spec['task']]
        evaluation.append({'id':spec['task'],'windows':len(rows),'mae':float(np.mean([r['absolute_error'] for r in rows])) if rows else None,
          'baseline_mae':float(np.mean([r['baseline_absolute_error'] for r in rows])) if rows else None,
          'wape':sum(r['absolute_error'] for r in rows)/sum(r['actual'] for r in rows) if rows and sum(r['actual'] for r in rows)>0 else None})
    latest=receipts[-1] if receipts else None
    public_value={'version':'planning_v1','protocol_sha256':ph,'updated_at':utcnow().isoformat(),'status':'collecting' if latest else 'awaiting_first_forecast',
      'first_origin':protocol['first_origin'],'schedule':'Sunday 23:50 · Malaysia time','latest':latest and {k:latest[k] for k in ['origin','issued_at']},
      'forecasts':[{k:t[k] for k in ['id','prediction','baseline','already_booked','window_end','training_windows']} for t in latest['forecasts']] if latest else [],
      'coverage':{'expected_windows':len(expected),'timely_windows':len(observed),'missing_weeks':[x for x in expected if x not in observed]},'evaluation':evaluation}
    public.put('planning_forecast.json',canonical(public_value),immutable=False)
    print(json.dumps({'status':'SOURCE_AND_MODEL_CHECK_PASSED' if args.check else 'PLANNING_TICK_COMPLETE','timely_weeks':len(receipts),'evaluated_windows':len(outcomes)}))

if __name__=='__main__':main()
