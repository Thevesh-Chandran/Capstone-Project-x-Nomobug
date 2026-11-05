"""Exploratory target comparison; immutable copies, mature labels, past-only inputs.

Does not promote a model or modify the prospective experiment. Historical test
periods were previously inspected in other studies, so are NOT pristine holdouts.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil, itertools, warnings
import numpy as np
import pandas as pd
import requests
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, average_precision_score, brier_score_loss, balanced_accuracy_score
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261018_expanded_targets'
SEED=20261018
FEATURES=['log_initial_sales','missing_amount','month_sin','month_cos','package','pest','premise']
WEATHER=['rain_7','rain_28','temperature_28','humidity_28']
EXTRA=['district','initial_sale_rows']
FAMILIES=['logistic','random_forest','extra_trees','boosting']
GROUPS=['basic','purchase_details','purchase_details_weather']
WINDOWS=['all_history','last_365_days']
DEV=[('2024-10-01','2024-12-31'),('2025-01-01','2025-03-31'),('2025-04-01','2025-06-30')]

def save(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,default=str,allow_nan=False),encoding='utf-8')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'protocol.json').exists():return
    sources={
        'customers_private.json':ROOT/'outputs/business_implementation/current/customers_private.json',
        'business_receipt.json':ROOT/'outputs/business_implementation/current/business_receipt.json',
        'weekly_targets.csv':ROOT/'outputs/additional_model_research/20261014/weekly_targets.csv',
        'forecast_source_receipt.json':ROOT/'outputs/additional_model_research/20261014/source_receipt.json'}
    for name,p in sources.items():shutil.copy2(p,OUT/name)
    protected=[ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json',ROOT/'config/cp2_model_current.json']
    save(OUT/'protocol.json',{
        'declared_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),
        'status':'Exploratory; previously inspected historical periods; not a fresh independent test',
        'sources':{name:{'path':str(p.relative_to(ROOT)),'sha256':sha(OUT/name)} for name,p in sources.items()},
        'protected':{str(p.relative_to(ROOT)):sha(p) for p in protected},
        'observed_through':'2026-10-11','repeat_horizons_days':[30,60,90,180],
        'repeat_development':DEV,'repeat_assessment':['2026-01-01','2026-04-14'],
        'repeat_design':'One first recorded paid programme per customer; distinct later programme is outcome; no later programme totals as features. Labels mature strictly before fitting/prediction. Same assessment dates across horizons.',
        'repeat_search':{'families':FAMILIES,'features':GROUPS,'history':WINDOWS,'thresholds':[.05,.1,.15,.2,.3,.4,.5,.6,.7,.8]},
        'selection':'Pooled development F1 with recall >=0.30 and >=10 predicted positives; then precision. If no eligible threshold, use best F1 with failed gate disclosed. Never select by assessment scores.',
        'forecasts':'Next-week bookings, packages, recorded sales; development Jan-June 2026 every second week; assessment July6-Oct5 2026 weekly.',
        'forecast_search':'ridge, extra_trees, boosting; 52 weeks/all history; past activity alone / plus regional weather; compare last week, mean4, mean8, seasonal52.',
        'weather':'ERA5 Kuala Lumpur public city-centre proxy; latest used date strictly before origin minus 7 days. Not customer-specific. Current reanalysis revisions are a limitation.',
        'acceptance':'No production promotion. Classification needs >=20 assessment positives, precision>=0.50, recall>=0.30, F1 and balanced accuracy above trivial baseline; forecast needs MAE improvement >=10% against development-selected baseline and positive block-bootstrap improvement interval.',
        'rejected_targets':'Payment lateness lacks trusted dated settlement labels; formal warranty approval lacks verified claims; profitability lacks costs. Do not predict a value from fields that already reveal it.'})

def weather_data():
    path=OUT/'regional_weather.json'
    if not path.exists():
        params={'latitude':3.139,'longitude':101.6869,'start_date':'2023-01-01','end_date':'2026-10-11',
            'daily':'precipitation_sum,temperature_2m_mean,relative_humidity_2m_mean','timezone':'Asia/Kuala_Lumpur','models':'era5'}
        r=requests.get('https://archive-api.open-meteo.com/v1/archive',params=params,timeout=90)
        r.raise_for_status(); data=r.json(); assert 'daily' in data
        save(path,data);save(OUT/'weather_receipt.json',{'url':r.url,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
            'sha256':sha(path),'documentation':'https://open-meteo.com/en/docs/historical-weather-api','use':'Public regional coordinate only; no customer addresses sent'})
    d=pd.DataFrame(json.loads(path.read_text())['daily']);d.index=pd.to_datetime(d.pop('time'))
    assert d.index.is_unique and d.notna().all().all()
    return d

def weather_features(w,date):
    end=pd.Timestamp(date)-pd.Timedelta(days=7)
    a=w[(w.index>=end-pd.Timedelta(days=28))&(w.index<end)]
    b=a[a.index>=end-pd.Timedelta(days=7)]
    assert len(a)==28 and len(b)==7 and a.index.max()<pd.Timestamp(date)-pd.Timedelta(days=7)
    return dict(zip(WEATHER,[float(b.precipitation_sum.sum()),float(a.precipitation_sum.sum()),float(a.temperature_2m_mean.mean()),float(a.relative_humidity_2m_mean.mean())]))

def repeat_data(customers,horizon,w):
    rows=[];excluded={};end=pd.Timestamp('2026-10-11')
    def skip(reason):excluded[reason]=excluded.get(reason,0)+1
    for c in customers:
        if c['identity_status']=='needs_review':skip('identity_review');continue
        if any(not s.get('date') for s in c['sales']):skip('undated_sale');continue
        sales=[s for s in c['sales'] if pd.Timestamp(s['date'])<=end]
        if not sales:skip('no_observed_sales');continue
        starts={}
        for s in sales:
            key=s['programme_id'];date=pd.Timestamp(s['date']);starts[key]=min(starts.get(key,date),date)
        first=min(starts.values());mature=first+pd.Timedelta(days=horizon)
        if mature>end:skip('immature');continue
        initial=[s for s in sales if pd.Timestamp(s['date'])==first]
        cats=lambda key:' | '.join(sorted({str(s.get(key) or 'Unknown') for s in initial}))
        amount=sum(float(s.get('sales_rm') or 0) for s in initial)
        row={'customer_hash':hashlib.sha256(str(c['customer_key']).encode()).hexdigest(),'first_date':first,'outcome_end':mature,
            'label':int(any(first<d<=mature for d in starts.values())),
            'log_initial_sales':np.log1p(max(0,amount)),'missing_amount':int(any(s.get('sales_rm') is None for s in initial)),
            'month_sin':np.sin(first.month*2*np.pi/12),'month_cos':np.cos(first.month*2*np.pi/12),
            'initial_sale_rows':len(initial),**{k:cats(k) for k in ['package','pest','premise','district']},**weather_features(w,first)}
        rows.append(row)
    d=pd.DataFrame(rows);assert d.customer_hash.is_unique
    return d,excluded

def columns(group):return FEATURES+(EXTRA if group!='basic' else [])+(WEATHER if group.endswith('weather') else [])
def classifier(name,cols):
    cats=[c for c in cols if c in ['package','pest','premise','district']];nums=[c for c in cols if c not in cats]
    pre=ColumnTransformer([('numeric',make_pipeline(SimpleImputer(strategy='median'),StandardScaler()),nums),('category',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cats)])
    if name=='logistic':est=LogisticRegression(C=.1,class_weight='balanced',max_iter=500,random_state=SEED)
    elif name=='random_forest':est=RandomForestClassifier(n_estimators=100,max_depth=5,min_samples_leaf=12,class_weight='balanced',random_state=SEED,n_jobs=2)
    elif name=='extra_trees':est=ExtraTreesClassifier(n_estimators=100,max_depth=5,min_samples_leaf=12,class_weight='balanced',random_state=SEED,n_jobs=2)
    else:est=HistGradientBoostingClassifier(max_iter=80,max_leaf_nodes=7,min_samples_leaf=20,l2_regularization=10,early_stopping=False,random_state=SEED)
    return make_pipeline(pre,est)

def scores(y,p,t):
    y=np.asarray(y);z=np.asarray(p)>=t;tp=int(np.sum((y==1)&z));fp=int(np.sum((y==0)&z));fn=int(np.sum((y==1)&~z));tn=int(np.sum((y==0)&~z))
    return {'n':len(y),'positives':int(y.sum()),'predicted_positive':int(z.sum()),'tp':tp,'fp':fp,'fn':fn,'tn':tn,
        'accuracy':float(accuracy_score(y,z)),'precision':float(precision_score(y,z,zero_division=0)),
        'recall':float(recall_score(y,z,zero_division=0)),'f1':float(f1_score(y,z,zero_division=0)),
        'balanced_accuracy':float(balanced_accuracy_score(y,z)),'average_precision':float(average_precision_score(y,p)),
        'brier':float(brier_score_loss(y,p)),'prevalence':float(y.mean())}

def split_repeat(d,start,end,window):
    a=pd.Timestamp(start);b=pd.Timestamp(end);tr=d[d.outcome_end<a]
    if window=='last_365_days':tr=tr[tr.first_date>=a-pd.Timedelta(days=365)]
    va=d[d.first_date.between(a,b)]
    assert not set(tr.customer_hash)&set(va.customer_hash)
    assert tr.empty or tr.outcome_end.max()<a
    return tr,va

def repeat_study(w):
    customers=json.loads((OUT/'customers_private.json').read_text());all_results=[];leaders=[];audit=[];counts=[]
    for horizon in [30,60,90,180]:
        saved=json.loads((OUT/'repeat_results.json').read_text()) if (OUT/'repeat_results.json').exists() else []
        prior=next((r for r in saved if r['target']==f'repeat_{horizon}'),None)
        if prior:
            all_results.append(prior)
            continue
        d,excluded=repeat_data(customers,horizon,w);audit.append({'horizon':horizon,'eligible':len(d),'excluded':excluded})
        development=[]
        for family,group,window in itertools.product(FAMILIES,GROUPS,WINDOWS):
            col=columns(group);ys=[];ps=[];parts=[]
            for start,end in DEV:
                tr,va=split_repeat(d,start,end,window)
                if len(tr)<50 or tr.label.nunique()<2 or va.label.nunique()<2:continue
                m=classifier(family,col);m.fit(tr[col],tr.label);p=m.predict_proba(va[col])[:,1]
                ys.extend(va.label);ps.extend(p);parts.append({'start':start,'train':len(tr),'validation':len(va),'positive':int(va.label.sum())})
            expected=2 if horizon==180 else 3
            if len(parts)!=expected:raise ValueError(f'Incomplete development folds: {horizon} {parts}')
            for threshold in [.05,.1,.15,.2,.3,.4,.5,.6,.7,.8]:
                s=scores(ys,ps,threshold);development.append({'target':f'repeat_{horizon}','model':family,'inputs':group,'history':window,'threshold':threshold,'folds':parts,**s})
        eligible=[r for r in development if r['recall']>=.3 and r['predicted_positive']>=10]
        selected=max(eligible or development,key=lambda r:(r['f1'],r['precision']))
        save(OUT/f'repeat_{horizon}_selection.json',{'selected_before_assessment':selected,'selection_time':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha(OUT/'protocol.json')})
        leaders.extend(development)
        tr,te=split_repeat(d,'2026-01-01','2026-04-14',selected['history']);col=columns(selected['inputs'])
        m=classifier(selected['model'],col);m.fit(tr[col],tr.label);p=m.predict_proba(te[col])[:,1]
        test=scores(te.label,p,selected['threshold'])
        pd.DataFrame({'actual':te.label.to_numpy(),'probability':p}).to_csv(OUT/f'repeat_{horizon}_assessment.csv',index=False)
        baseline=scores(te.label,np.full(len(te),float(tr.label.mean())),.5)
        always_yes_f1=2*test['prevalence']/(1+test['prevalence'])
        good=test['positives']>=20 and test['precision']>=.5 and test['recall']>=.3 and test['f1']>always_yes_f1 and test['balanced_accuracy']>.5
        rng=np.random.default_rng(SEED);intervals=[]
        for _ in range(1000):
            idx=rng.integers(0,len(te),len(te));y=te.label.to_numpy()[idx];z=p[idx]>=selected['threshold']
            intervals.append([precision_score(y,z,zero_division=0),recall_score(y,z,zero_division=0)])
        ci=np.quantile(intervals,[.025,.975],axis=0).T.tolist()
        result={'target':f'repeat_{horizon}','question':f'Will a customer buy another distinct programme within {horizon} days of their first recorded purchase?',
            'selected':selected,'assessment':test,'training_rows':len(tr),'input_count':len(col),'inputs':col,
            'baseline':baseline,'always_yes_f1':always_yes_f1,'precision_95pct_interval':ci[0],'recall_95pct_interval':ci[1],
            'research_gate_passed':good,'operationally_validated':False}
        all_results.append(result);print('Finished',result['target'],json.dumps(test),flush=True)
        save(OUT/'repeat_results.json',all_results)
    pd.DataFrame(leaders).drop(columns='folds',errors='ignore').to_csv(OUT/'repeat_development_search_resumed.csv',index=False)
    save(OUT/'repeat_data_audit.json',audit)
    return all_results

def regression_metrics(y,p):
    y=np.asarray(y);p=np.asarray(p);e=np.abs(y-p)
    return {'weeks':len(y),'mae':float(e.mean()),'rmse':float(np.sqrt(np.mean((y-p)**2))),'wape':float(e.sum()/y.sum()),'actual_mean':float(y.mean())}

def weekly_matrix(series,w):
    rows=[]
    for i in range(12,len(series)):
        h=series.iloc[:i].to_numpy();origin=series.index[i]
        row={f'lag_{k}':float(h[-k]) for k in [1,2,3,4,8,12]}
        row.update({'average_4':float(h[-4:].mean()),'average_8':float(h[-8:].mean()),'variation_8':float(h[-8:].std()),
            'week_sin':np.sin(origin.isocalendar().week*2*np.pi/52.18),'week_cos':np.cos(origin.isocalendar().week*2*np.pi/52.18),
            'date':origin,'actual':float(series.iloc[i]),**weather_features(w,origin)})
        rows.append(row)
    return pd.DataFrame(rows)

def forecaster(name):
    if name=='ridge':return make_pipeline(StandardScaler(),Ridge(alpha=10))
    if name=='extra_trees':return ExtraTreesRegressor(n_estimators=80,max_depth=4,min_samples_leaf=5,n_jobs=2,random_state=SEED)
    return HistGradientBoostingRegressor(max_iter=60,max_leaf_nodes=7,min_samples_leaf=8,l2_regularization=5,early_stopping=False,random_state=SEED)

def forecast_study(w):
    series=pd.read_csv(OUT/'weekly_targets.csv',index_col=0,parse_dates=True);results=[];search=[];predictions=[]
    for target in series:
        s=series[target].dropna();d=weekly_matrix(s,w);basecols=[c for c in d if c not in ['date','actual']+WEATHER]
        dev=d[d.date.between('2026-01-05','2026-06-29')].iloc[::2];test=d[d.date.between('2026-07-06','2026-10-05')]
        def run(rows,name,window,group):
            out=[];cols=basecols+(WEATHER if group=='weather' else [])
            for _,r in rows.iterrows():
                history=s[s.index<r.date]
                if name=='last_week':p=history.iloc[-1]
                elif name=='mean4':p=history.iloc[-4:].mean()
                elif name=='mean8':p=history.iloc[-8:].mean()
                elif name=='seasonal52':p=history.iloc[-52]
                else:
                    tr=d[d.date<r.date]
                    if window=='52_weeks':tr=tr[tr.date>=r.date-pd.Timedelta(weeks=52)]
                    assert (tr.date+pd.Timedelta(days=7)<=r.date).all()
                    m=forecaster(name);m.fit(tr[cols],tr.actual);p=max(0,float(m.predict(pd.DataFrame([r[cols]]))[0]))
                out.append(float(p))
            return out
        configurations=list(itertools.product(['ridge','extra_trees','boosting'],['all_history','52_weeks'],['activity','weather']))
        configurations += [(n,'all_history','activity') for n in ['last_week','mean4','mean8','seasonal52']]
        board=[]
        for name,window,group in configurations:
            p=run(dev,name,window,group);board.append({'target':target,'model':name,'history':window,'inputs':group,**regression_metrics(dev.actual,p)})
        chosen=min(board,key=lambda r:r['mae']);baseline=min([r for r in board if r['model'] in ['last_week','mean4','mean8','seasonal52']],key=lambda r:r['mae'])
        save(OUT/f'{target}_selection.json',{'selected_before_assessment':chosen,'baseline':baseline,'at_utc':datetime.now(timezone.utc).isoformat()})
        p=run(test,chosen['model'],chosen['history'],chosen['inputs']);b=run(test,baseline['model'],baseline['history'],baseline['inputs'])
        actual=test.actual.to_numpy();diff=np.abs(actual-np.array(b))-np.abs(actual-np.array(p));rng=np.random.default_rng(SEED);boot=[]
        for _ in range(2000):
            idx=np.concatenate([(j+np.arange(2))%len(diff) for j in rng.integers(0,len(diff),size=(len(diff)+1)//2)])[:len(diff)]
            boot.append(float(diff[idx].mean()))
        interval=np.quantile(boot,[.025,.975]).tolist();met=regression_metrics(actual,p);bm=regression_metrics(actual,b)
        improvement=1-met['mae']/bm['mae'];result={'target':target,'selected':chosen,'baseline_selection':baseline,'assessment':met,'baseline_assessment':bm,
            'mae_improvement':improvement,'mae_improvement_95pct_block_interval':interval,'input_count':len(basecols)+(len(WEATHER) if chosen['inputs']=='weather' else 0),
            'research_gate_passed':bool(improvement>=.1 and interval[0]>0),'operationally_validated':False}
        results.append(result);search.extend(board)
        for date,y,a,c in zip(test.date,actual,p,b):predictions.append({'target':target,'date':str(date.date()),'actual':y,'prediction':a,'baseline':c})
        save(OUT/'forecast_results.json',results);print('Finished',target,json.dumps(met),flush=True)
    pd.DataFrame(search).to_csv(OUT/'forecast_development_search.csv',index=False);pd.DataFrame(predictions).to_csv(OUT/'forecast_assessment.csv',index=False)
    return results

def main():
    prepare();w=weather_data()
    with threadpool_limits(limits=2),warnings.catch_warnings(record=True) as logs:
        warnings.simplefilter('always');repeat_study(w);forecast_study(w)
        save(OUT/'warnings.json',sorted(set(str(v.message) for v in logs)))
    protocol=json.loads((OUT/'protocol.json').read_text())
    assert all(sha(ROOT/path)==value for path,value in protocol['protected'].items())
    assert all(sha(OUT/name)==info['sha256'] for name,info in protocol['sources'].items())
    save(OUT/'completion.json',{'completed_at_utc':datetime.now(timezone.utc).isoformat(),'protected_unchanged':True,'source_hashes_verified':True,'script_sha256':sha(__file__)})

if __name__=='__main__':main()
