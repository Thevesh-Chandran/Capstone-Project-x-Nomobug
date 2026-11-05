"""Refine commercial price research using existing Calendar and Sales snapshots.
No source writes, new downloads, current-model changes or assessment-driven tuning.
"""
from pathlib import Path
from datetime import datetime,timezone
import json,re,html,hashlib
import numpy as np
import pandas as pd
from scripts import research_quote_estimate as q
from scripts.research_calendar_quote_sizes import extract as previous_extract
ROOT=q.ROOT
OUT=ROOT/'outputs/model_validation/20261101_commercial_refinement'
SOURCE=ROOT/'outputs/model_validation/20261030_calendar_quote_sizes/calendar_private.json'

def clean(text):
    return html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'(?i)<(?:br\s*/?|/p|/div|/li)>','\n',text or '')))

def extract_size(text):
    text=clean(text);old=previous_extract(text);values=[]
    if np.isfinite(old['area_sqft']):values.append(old['area_sqft'])
    # Explicit k suffix and explicit-unit length x width in labelled size fields.
    # No feet assumption for unitless 20x70, ranges, or address measurements.
    for line in text.splitlines():
        if not re.search(r'(?:saiz|size|keluasan)',line,re.I):continue
        for m in re.finditer(r'\b(\d+(?:\.\d+)?)\s*k\s*(?:sqft|sq\s*ft|sf)\b',line,re.I):
            values.append(float(m[1])*1000)
        number=r'(\d+(?:\.\d+)?)'
        unit=r"(ft|feet|foot|m|metres?|meters?|['’])"
        pattern=number+r'\s*'+unit+r'?\s*[x×]\s*'+number+r'\s*'+unit
        for m in re.finditer(pattern,line,re.I):
            if re.search(r'[/]|\d\s*-\s*\d',line):continue
            a,u1,b,u2=m.groups();a=float(a);b=float(b)
            feet=lambda u: u is None or u.lower() in ('ft','feet','foot',"'",'’')
            if u1 is not None and feet(u1)!=feet(u2):continue
            area=a*b*(1 if feet(u2) else 10.7639104167)
            if 1<=a<=500 and 1<=b<=500 and 20<=area<=1000000:values.append(round(area,2))
    values=sorted(set(round(v,2) for v in values if 20<=v<=1000000))
    # A prior ambiguous multi-area note must never become a single recovered value.
    area=values[0] if len(values)==1 and old['area_values']<=1 else np.nan
    return {'area_sqft':area,'area_conflict':old['area_values']>1 or len(values)>1,'floors_mentioned':old['floors_mentioned']}

def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,default=str,allow_nan=False),encoding='utf-8')

def prepare():
    f=pd.read_csv(ROOT/'outputs/model_validation/20261030_commercial_quote/labelled_commercial_quotes_private.csv',parse_dates=['date'])
    dates=dict(zip(f.sale_id,f.date));rows=[]
    for r in json.loads(SOURCE.read_text(encoding='utf-8')):
        sid=r.get('sale_id')
        if sid not in dates or r['match_status'] in ('ambiguous_sales','unmatched','low_address','payment_link_only'):continue
        created=pd.to_datetime(r.get('created_raw'),utc=True,errors='coerce');updated=pd.to_datetime(r.get('updated_raw'),utc=True,errors='coerce')
        start=dates[sid].tz_localize('Asia/Kuala_Lumpur');end=start+pd.Timedelta(days=1)
        if pd.isna(created) or pd.isna(updated) or created>=end or updated>=end:continue
        rows.append({'sale_id':sid,'strictly_before_sale_day':bool(created<start and updated<start),**extract_size(r.get('description'))})
    events=pd.DataFrame(rows)
    for col in ['area_sqft','floors_mentioned']:
        result={}
        for sid,g in events.groupby('sale_id'):
            vals=g[col].dropna().unique()
            if len(vals)==1 and (col!='area_sqft' or not g.area_conflict.any()):result[sid]=vals[0]
        f[col]=f.sale_id.map(result)
    f['log_area_sqft']=np.log1p(f.area_sqft)
    f['area_missing']=f.area_sqft.isna().astype(float)
    f['floors_missing']=f.floors_mentioned.isna().astype(float)
    f['log_sessions']=np.log1p(f.sessions)
    f.to_csv(OUT/'labelled_quotes_private.csv',index=False)
    return f,events

def pipeline(frame,features,family):
    from sklearn.compose import ColumnTransformer,TransformedTargetRegressor
    from sklearn.preprocessing import StandardScaler,OneHotEncoder
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.linear_model import Ridge
    from sklearn.ensemble import HistGradientBoostingRegressor,ExtraTreesRegressor
    cats=[c for c in features if not pd.api.types.is_numeric_dtype(frame[c])];nums=[c for c in features if c not in cats]
    pre=ColumnTransformer([('numbers',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler()),nums),('categories',OneHotEncoder(handle_unknown='ignore',min_frequency=5,sparse_output=False),cats)])
    models={'Gradient boosting':HistGradientBoostingRegressor(loss='absolute_error',max_iter=200,max_leaf_nodes=15,min_samples_leaf=10,l2_regularization=10,random_state=20261030),'Ridge':Ridge(alpha=100),'Extra Trees':ExtraTreesRegressor(n_estimators=300,max_depth=12,min_samples_leaf=3,random_state=20261030,n_jobs=1)}
    return q.PerSessionRegressor(TransformedTargetRegressor(regressor=make_pipeline(pre,models[family]),func=np.log1p,inverse_func=np.expm1))

def main():
    from threadpoolctl import threadpool_limits
    from sklearn.base import clone
    OUT.mkdir(exist_ok=True,parents=True)
    if (OUT/'results.json').exists():raise RuntimeError('Study complete; preserve its evidence. No automatic rerun.')
    f,events=prepare();train,val,test,split=q.partition(f)
    base=q.REQUIREMENTS
    variants={'Recorded requirements':base,'Requirements and size':base+['log_area_sqft','area_missing','floors_mentioned','floors_missing'],'Requirements size and business type':base+['log_area_sqft','area_missing','floors_mentioned','floors_missing','business_type']}
    protocol={'declared_at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'split':split,'variants':variants,'families':['Gradient boosting','Ridge','Extra Trees'],'target':'Log price per session, transformed back to total RM','selection':'Lowest validation MAE; tie prefers fewer inputs; no assessment tuning','comparison':'Same customer-disjoint training 213 / validation 75 / assessment 82','limitations':['Adaptive historical research on already inspected months','Description timestamps only screen availability by sale-day end, not exact quotation time','Building size is not automatically confirmed treatment area','Missing area remains unknown; imputation is fitted on training only'],'deployment':False}
    save('protocol_before_training.json',protocol)
    coverage={'commercial_sales':len(f),'consistent_area':int(f.area_sqft.notna().sum()),'floor_count':int(f.floors_mentioned.notna().sum()),'strictly_before_sale_day_area_sales':int(events[events.strictly_before_sale_day & events.area_sqft.notna()].sale_id.nunique()),'partitions':{n:{'rows':len(d),'known_area':int(d.area_sqft.notna().sum()),'known_floors':int(d.floors_mentioned.notna().sum())} for n,d in [('training',train),('validation',val),('assessment',test)]}}
    save('coverage.json',coverage)
    rows=[];models={}
    with threadpool_limits(limits=1):
        for group,features in variants.items():
            for family in protocol['families']:
                name=family+' / '+group;model=pipeline(f,features,family);model.fit(train[features],train.target_rm)
                rows.append({'candidate':name,'inputs':len(features),**q.measures(val.target_rm,model.predict(val[features]))});models[name]=(model,features)
        selected=min(rows,key=lambda r:(r['mae_rm'],r['inputs'],r['candidate']))['candidate']
        save('selected_before_assessment.json',{'selected':selected,'validation':rows})
        comparisons=[];preds={};refit=pd.concat([train,val])
        for name in dict.fromkeys(['Gradient boosting / Recorded requirements',selected]):
            model,features=models[name];model.fit(refit[features],refit.target_rm);pred=model.predict(test[features]);preds[name]=pred
            comparisons.append({'candidate':name,**q.measures(test.target_rm,pred)})
        # A training-only median unit-price lookup checks whether session count alone explains success.
        unit_median=float((refit.target_rm/refit.sessions).median());lookup=test.sessions.to_numpy()*unit_median
        comparisons.append({'candidate':'Median price per session',**q.measures(test.target_rm,lookup)})
        preds['Median price per session']=lookup
        out=test[['sale_id','customer_group','target_rm','area_sqft']].copy()
        for name,pred in preds.items():out[name]=pred
        out.to_csv(OUT/'assessment_predictions_private.csv',index=False)
        baseline=preds['Gradient boosting / Recorded requirements'];chosen=preds[selected]
        groups=test.customer_group.to_numpy();unique=np.unique(groups);rng=np.random.default_rng(20261101);delta=[]
        for _ in range(2000):
            sampled=rng.choice(unique,len(unique),replace=True);idx=np.concatenate([np.flatnonzero(groups==g) for g in sampled]);y=test.target_rm.to_numpy()[idx]
            delta.append(float(np.mean(abs(y-baseline[idx]))-np.mean(abs(y-chosen[idx]))))
        interval=np.quantile(delta,[.025,.975]).tolist()
        result={'selected':selected,'validation':rows,'assessment':comparisons,'bootstrap_MAE_improvement_vs_original_95':interval,'deployed':False,'independent_final_test':False}
        save('results.json',result)
    print(json.dumps({'coverage':coverage,'selected':selected,'assessment':comparisons,'improvement_interval':interval},indent=2))
if __name__=='__main__':main()
