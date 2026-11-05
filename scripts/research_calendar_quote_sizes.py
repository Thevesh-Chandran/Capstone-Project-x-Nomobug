"""Test explicit Calendar premises measurements against commercial price estimates.
Uses a pinned private snapshot; never treats later notes as quote-time evidence.
"""
from pathlib import Path
import hashlib,html,json,re
import numpy as np
import pandas as pd
from sklearn.base import clone
from threadpoolctl import threadpool_limits
from scripts import research_quote_estimate as q
ROOT=q.ROOT
OUT=ROOT/'outputs/model_validation/20261030_calendar_quote_sizes'
UNIT=r'(?:sq\s*\.?\s*f(?:ee)?t|sqft|sqf|sqt|square\s*(?:feet|foot|fit)|sf|sq\s*\.?\s*m(?:et(?:er|re)s?)?|sqm|square\s*met(?:er|re)s?|kaki\s*persegi)'
AREA=re.compile(r'(?<![\d.,])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*('+UNIT+r')\b',re.I)
def extract(text):
    text=html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'(?i)<(?:br\s*/?|/p|/div|/li)>','\n',text or '')))
    values=[]
    for m in AREA.finditer(text):
        value=float(m[1].replace(',',''));unit=re.sub(r'[\s.]','',m[2].lower())
        if 'meter' in unit or 'metre' in unit or unit in ('sqm',):value*=10.7639104167
        if 20<=value<=1000000:values.append(round(value,2))
    values=sorted(set(values))
    # Only an explicit size/floor-count field, never an address's floor ordinal.
    floors=[]
    for line in text.splitlines():
        if re.search(r'(?:saiz|size|keluasan|number of floors|bilangan tingkat)',line,re.I):
            floors.extend(int(m[1]) for m in re.finditer(r'\b(\d{1,2})\s*(?:floors|storeys|stories|tingkat)\b',line,re.I))
    floors=sorted(set(floors))
    return {'area_sqft':values[0] if len(values)==1 else np.nan,'area_values':len(values),'floors_mentioned':floors[0] if len(floors)==1 else np.nan}
def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')
def main():
    import joblib
    source=OUT/'calendar_private.json'
    frame=pd.read_csv(ROOT/'outputs/model_validation/20261030_commercial_quote/labelled_commercial_quotes_private.csv',parse_dates=['date'])
    dates=dict(zip(frame.sale_id,frame.date));records=[]
    for row in json.loads(source.read_text(encoding='utf-8')):
        sid=row.get('sale_id');day=dates.get(sid)
        cutoff=day.tz_localize('Asia/Kuala_Lumpur')+pd.Timedelta(days=1) if day is not None else pd.NaT
        created=pd.to_datetime(row.get('created_raw'),utc=True,errors='coerce');updated=pd.to_datetime(row.get('updated_raw'),utc=True,errors='coerce')
        timely=bool(pd.notna(cutoff) and pd.notna(created) and pd.notna(updated) and created<cutoff and updated<cutoff)
        records.append({'event_id':row['event_id'],'sale_id':sid,'match_status':row['match_status'],'known_by_sale_day_end':timely,**extract(row.get('description'))})
    events=pd.DataFrame(records);events.to_csv(OUT/'extracted_sizes_private.csv',index=False)
    linked=events[events.sale_id.isin(dates)&~events.match_status.isin(['ambiguous_sales','unmatched','low_address','payment_link_only'])]
    eligible=linked[linked.known_by_sale_day_end]
    for feature in ['area_sqft','floors_mentioned']:
        consistent={}
        for sid,group in eligible.groupby('sale_id'):
            values=group[feature].dropna().unique()
            # Disagreeing dimensions remain unknown; no averaging across premises.
            if len(values)==1 and (feature!='area_sqft' or not group.area_values.gt(1).any()):consistent[sid]=values[0]
        frame[feature]=frame.sale_id.map(consistent)
    frame.to_csv(OUT/'labelled_quote_sizes_private.csv',index=False)
    train,valid,test,split=q.partition(frame)
    coverage={'snapshot_calendar_rows':len(events),'events_with_one_explicit_area':int(events.area_sqft.notna().sum()),'commercial_study_sales':len(frame),'commercial_sales_with_linked_area':linked[linked.area_sqft.notna()].sale_id.nunique(),'commercial_sales_with_consistent_timestamp_eligible_area':int(frame.area_sqft.notna().sum()),'commercial_sales_with_eligible_floor_count':int(frame.floors_mentioned.notna().sum()),'partitions':{n:{'rows':len(d),'known_area':int(d.area_sqft.notna().sum()),'known_floors':int(d.floors_mentioned.notna().sum())} for n,d in [('training',train),('validation',valid),('assessment',test)]}}
    save('coverage.json',coverage)
    bundle=joblib.load(ROOT/'outputs/model_validation/20261030_commercial_quote/experimental_model.joblib')
    base=bundle['features'];variants={'Original commercial model':base,'Add Calendar area':base+['area_sqft'],'Add Calendar area and floors':base+['area_sqft','floors_mentioned']}
    save('protocol_before_training.json',{'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'variants':variants,'split':split,'fixed_model':'Previously selected gradient boosting, log price per session; same settings; numeric median imputation','selection':'Lowest validation MAE; assessment only after selection','limitations':['Adaptive historical follow-up on inspected periods','Sale-day-end timestamp is a permissive screen, not proof that details were known before quotation','No later descriptions, unitless dimensions, address floor ordinals or conflicting areas used','No production or frozen model changes']})
    models={};validation=[]
    with threadpool_limits(limits=1):
        for name,features in variants.items():
            model=clone(bundle['pipeline'])
            pre=model.estimator.regressor.steps[0][1]
            transformers=[]
            for label,transformer,cols in pre.transformers:
                cols=list(cols)
                if label=='numbers':cols+= [c for c in features if c not in base]
                transformers.append((label,transformer,cols))
            pre.set_params(transformers=transformers)
            model.fit(train[features],train.target_rm)
            validation.append({'candidate':name,**q.measures(valid.target_rm,model.predict(valid[features]))})
            models[name]=(model,features)
        selected=min(validation,key=lambda r:r['mae_rm'])['candidate'];save('selected_before_assessment.json',{'selected':selected,'validation':validation})
        assessment=[];fit=pd.concat([train,valid])
        for name,(model,features) in models.items():
            model.fit(fit[features],fit.target_rm);pred=model.predict(test[features])
            assessment.append({'candidate':name,**q.measures(test.target_rm,pred)})
    save('results.json',{'selected_on_validation':selected,'validation':validation,'assessment':assessment,'deployed':False,'interpretation':'Exploratory size enrichment comparison; timestamp and missingness limitations apply'})
    print(json.dumps({'coverage':coverage,'selected':selected,'assessment':assessment},indent=2))
if __name__=='__main__':main()
