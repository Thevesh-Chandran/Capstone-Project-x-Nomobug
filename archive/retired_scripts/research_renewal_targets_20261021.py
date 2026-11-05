"""Exploratory existing-customer repurchase forecasts; past-only monthly anchors.

No actual contract-expiry or completed-service label is inferred from Calendar.
Current confirmed programme memberships collapse linked upsells. The observation
is a customer-month, and future distinct programme starts define the outcome.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, itertools, json, shutil, warnings
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/model_validation/20261021_renewal_targets'
SOURCE = ROOT / 'outputs/business_implementation/current/customers_private.json'
WEATHER_SOURCE = ROOT / 'outputs/model_validation/20261018_expanded_targets/regional_weather.json'
SEED = 20261021
OBSERVED = pd.Timestamp('2026-10-11')
DEV = [('2025-04-01','2025-06-01'),('2025-07-01','2025-09-01'),('2025-10-01','2025-12-01')]
TEST = ('2026-01-01','2026-04-01')
HORIZONS = [30, 90, 180]
POPULATIONS = ['recent_365_days', 'repeat_customer_730_days']
FAMILIES = ['plain_logistic','balanced_logistic','random_forest','extra_trees','boosting','catboost']
NUMERIC = ['prior_programmes','days_since_first','days_since_last','prior_90_days','prior_365_days',
           'past_sales_log','past_mean_sales_log','last_initial_sales_log','mean_gap','median_gap',
           'gap_variation','known_gaps','days_over_median_gap','relative_gap','month_sin','month_cos']
CATEGORICAL = ['last_package','last_pest','last_premise']
WEATHER = ['rain_7','rain_28','temperature_28','humidity_28']
THRESHOLDS = [.005,.01,.02,.03,.05,.075,.1,.15,.2,.25,.3,.4,.5,.6,.7,.8,.9]

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(name, value):
    (OUT / name).write_text(json.dumps(value,indent=2,default=str,allow_nan=False),encoding='utf-8')

def metrics(y,p,t):
    y=np.asarray(y,dtype=int); p=np.asarray(p,dtype=float); z=p>=t
    tp=int(np.sum((y==1)&z)); fp=int(np.sum((y==0)&z)); fn=int(np.sum((y==1)&~z)); tn=int(np.sum((y==0)&~z))
    recall=tp/max(1,tp+fn); specificity=tn/max(1,tn+fp)
    return {'n':len(y),'positives':int(y.sum()),'predicted_positive':int(z.sum()),'tp':tp,'fp':fp,'fn':fn,'tn':tn,
            'accuracy':(tp+tn)/len(y),'precision':tp/max(1,tp+fp),'recall':recall,'f1':2*tp/max(1,2*tp+fp+fn),
            'balanced_accuracy':(recall+specificity)/2,'prevalence':float(y.mean()),
            'average_precision':float(average_precision_score(y,p)),
            'roc_auc':float(roc_auc_score(y,p)) if len(set(y))==2 else None,
            'brier':float(brier_score_loss(y,p))}

def weather_frame():
    w=pd.DataFrame(json.loads((OUT/'regional_weather.json').read_text())['daily'])
    w.index=pd.to_datetime(w.pop('time')); return w

def weather_before(w,origin):
    # Preserve existing weather study's 7-day availability lag.
    end=origin-pd.Timedelta(days=7); a=w[(w.index>=end-pd.Timedelta(days=28))&(w.index<end)]
    b=a[a.index>=end-pd.Timedelta(days=7)]
    assert len(a)==28 and len(b)==7 and a.index.max()<origin-pd.Timedelta(days=7)
    return dict(zip(WEATHER,[float(b.precipitation_sum.sum()),float(a.precipitation_sum.sum()),
                           float(a.temperature_2m_mean.mean()),float(a.relative_humidity_2m_mean.mean())]))

def programme_history(customer):
    groups={}
    for sale in customer['sales']:
        day=pd.Timestamp(sale['date'])
        if day<=OBSERVED: groups.setdefault(sale['programme_id'],[]).append(sale)
    programmes=[]
    for key,sales in groups.items():
        first=min(pd.Timestamp(s['date']) for s in sales)
        initial=[s for s in sales if pd.Timestamp(s['date'])==first]
        # No totals/length from later-linked extensions are used as predictors.
        row={'start':first,'programme_id':key,'initial_amount':sum(float(s.get('sales_rm') or 0) for s in initial)}
        for field in ['package','pest','premise']:
            row[field]=' | '.join(sorted({str(s.get(field) or 'Unknown') for s in initial}))
        programmes.append(row)
    # Simultaneous distinct programmes are a single purchase occasion for cadence.
    occasions=[]
    for day in sorted({r['start'] for r in programmes}):
        same=[r for r in programmes if r['start']==day]
        occasions.append({'start':day,'count':len(same),'initial_amount':sum(r['initial_amount'] for r in same),
                           **{f:' | '.join(sorted({r[f] for r in same})) for f in ['package','pest','premise']}})
    return occasions,len(programmes)

def data():
    customers=json.loads((OUT/'customers_private.json').read_text()); w=weather_frame(); rows=[]
    excluded={'identity_review':0,'undated_sale':0,'no_eligible_purchase':0}; counts=[]
    origins=list(pd.date_range('2024-07-01','2026-04-01',freq='MS'))
    weather={origin:weather_before(w,origin) for origin in origins}
    linked=0
    for c in customers:
        if c['identity_status']=='needs_review': excluded['identity_review']+=1;continue
        if any(not s.get('date') for s in c['sales']):excluded['undated_sale']+=1;continue
        occasions,nprogrammes=programme_history(c)
        if not occasions:excluded['no_eligible_purchase']+=1;continue
        linked+=len([s for s in c['sales'] if pd.Timestamp(s['date'])<=OBSERVED])-nprogrammes
        counts.append(nprogrammes)
        key=hashlib.sha256(c['customer_key'].encode()).hexdigest()
        for origin in origins:
            past=[r for r in occasions if r['start']<origin]
            if not past:continue
            dates=[r['start'] for r in past]; gaps=np.diff(np.array(dates,dtype='datetime64[D]')).astype(int)
            dayslast=int((origin-dates[-1]).days)
            if dayslast>730:continue
            amounts=[max(0,r['initial_amount']) for r in past]
            median=float(np.median(gaps)) if len(gaps) else np.nan
            row={'customer_hash':key,'date':origin,'prior_programmes':sum(r['count'] for r in past),
                 'days_since_first':int((origin-dates[0]).days),'days_since_last':dayslast,
                 'prior_90_days':sum(r['count'] for r in past if r['start']>=origin-pd.Timedelta(days=90)),
                 'prior_365_days':sum(r['count'] for r in past if r['start']>=origin-pd.Timedelta(days=365)),
                 'past_sales_log':float(np.log1p(sum(amounts))),'past_mean_sales_log':float(np.log1p(np.mean(amounts))),
                 'last_initial_sales_log':float(np.log1p(amounts[-1])),
                 'mean_gap':float(np.mean(gaps)) if len(gaps) else np.nan,'median_gap':median,
                 'gap_variation':float(np.std(gaps)) if len(gaps) else np.nan,'known_gaps':len(gaps),
                 'days_over_median_gap':dayslast-median,'relative_gap':dayslast/median if len(gaps) and median>0 else np.nan,
                 'month_sin':float(np.sin(origin.month*2*np.pi/12)),'month_cos':float(np.cos(origin.month*2*np.pi/12)),
                 **{f'last_{f}':past[-1][f] for f in ['package','pest','premise']},**weather[origin]}
            for horizon in HORIZONS:
                end=origin+pd.Timedelta(days=horizon)
                if end>OBSERVED:continue
                label=int(any(origin<=r['start']<end for r in occasions))
                rows.append({**row,'horizon':horizon,'outcome_end':end,'label':label})
    d=pd.DataFrame(rows)
    assert not d.duplicated(['customer_hash','date','horizon']).any()
    save('data_audit.json',{'customers_in_snapshot':len(customers),'eligible_customers':len(counts),'excluded_customers':excluded,
                           'customers_with_repeated_programmes':sum(n>1 for n in counts),'linked_same_programme_sale_rows_collapsed':linked,
                           'monthly_rows_all_horizons':len(d),'month_start_min':str(d.date.min()),'month_start_max':str(d.date.max()),
                           'last_outcome_end':str(d.outcome_end.max()),'future_upsell_totals_used':False,
                           'source_snapshot':'Built 2026-10-14; labels bounded conservatively at 2026-10-11',
                           'renewal_anchor_limitation':'Appointment snapshot lacks customer/programme IDs and confirmed completion; do not infer actual last paid visit or expiry.'})
    return d

def subset(d,horizon,population):
    d=d[d.horizon==horizon]
    if population=='recent_365_days': return d[d.days_since_last<=365].copy()
    return d[(d.prior_programmes>=2)&(d.known_gaps>=1)&(d.days_since_last<=730)].copy()

def partition(d,start,end):
    start=pd.Timestamp(start); end=pd.Timestamp(end)
    tr=d[d.outcome_end<start].copy(); va=d[d.date.between(start,end)].copy()
    assert tr.empty or (tr.outcome_end<start).all()
    assert not set(zip(tr.customer_hash,tr.date))&set(zip(va.customer_hash,va.date))
    return tr,va

def model(family,cols):
    nums=[c for c in cols if c not in CATEGORICAL]
    pre=ColumnTransformer([('num',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True),StandardScaler()),nums),
                           ('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),CATEGORICAL)])
    if family in ['plain_logistic','balanced_logistic']:
        est=LogisticRegression(C=.1,max_iter=600,class_weight='balanced' if family.startswith('balanced') else None,random_state=SEED)
    elif family=='random_forest':est=RandomForestClassifier(n_estimators=100,max_depth=5,min_samples_leaf=15,class_weight='balanced',n_jobs=2,random_state=SEED)
    elif family=='extra_trees':est=ExtraTreesClassifier(n_estimators=100,max_depth=6,min_samples_leaf=15,class_weight='balanced',n_jobs=2,random_state=SEED)
    elif family=='boosting':est=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=7,min_samples_leaf=30,l2_regularization=10,early_stopping=False,random_state=SEED)
    elif family=='catboost':
        from catboost import CatBoostClassifier
        est=CatBoostClassifier(iterations=120,depth=4,learning_rate=.05,l2_leaf_reg=15,verbose=False,thread_count=2,random_seed=SEED,allow_writing_files=False)
    else:raise ValueError(family)
    return make_pipeline(pre,est)

def baseline_scores(tr,va,name,horizon):
    if name=='constant':return np.full(len(va),float(tr.label.mean()))
    if name=='cadence':
        # Probability-like score near an expected individual purchase occasion;
        # no observed repeat cadence falls back to training prevalence.
        wait=np.maximum(0,va.median_gap.to_numpy()-va.days_since_last.to_numpy())
        scale=np.maximum(14,va.median_gap.to_numpy()*.25)
        score=np.exp(-np.maximum(0,wait-horizon/2)/scale)
        score[~np.isfinite(score)]=float(tr.label.mean())
        return score
    if name=='recency_rate':
        bins=[-1,30,60,90,180,365,10000]
        a=pd.cut(tr.days_since_last,bins,labels=False); b=pd.cut(va.days_since_last,bins,labels=False)
        overall=float(tr.label.mean()); rates={}
        for key,group in tr.groupby(a):rates[int(key)]=(float(group.label.sum())+20*overall)/(len(group)+20)
        return np.array([rates.get(int(key),overall) for key in b])
    raise ValueError(name)

def bootstrap(frame,p,threshold):
    ids=frame.customer_hash.to_numpy(); groups=np.unique(ids); index=[np.flatnonzero(ids==g) for g in groups]
    y=frame.label.to_numpy(); rng=np.random.default_rng(SEED); values=[]
    for _ in range(800):
        idx=np.concatenate([index[j] for j in rng.integers(0,len(index),len(index))]); z=p[idx]>=threshold; yy=y[idx]
        tp=np.sum(z&(yy==1));fp=np.sum(z&(yy==0));fn=np.sum(~z&(yy==1))
        values.append([tp/max(1,tp+fp),tp/max(1,tp+fn),2*tp/max(1,2*tp+fp+fn)])
    intervals=np.quantile(values,[.025,.975],axis=0).T.tolist()
    return dict(zip(['precision','recall','f1'],intervals))

def choose(rows):
    eligible=[r for r in rows if r['recall']>=.3 and r['predicted_positive']>=15]
    candidates=eligible or rows
    return {'precision':max(candidates,key=lambda r:(r['precision'],r['f1'])),
            'f1':max(candidates,key=lambda r:(r['f1'],r['precision']))},bool(eligible)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'selection.json').exists():raise RuntimeError('Selection already declared; do not overwrite or repeat assessment')
    shutil.copy2(SOURCE,OUT/'customers_private.json');shutil.copy2(WEATHER_SOURCE,OUT/'regional_weather.json')
    protected=[ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json',ROOT/'config/cp2_model_current.json']
    save('protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),
        'question':'At month start, will an existing customer buy another distinct programme within 30/90/180 days?',
        'action':'Plan repeat-business expectations and review customer relationships. Predictions do not prove churn, cause, payment settlement or contract expiry.',
        'source_sha256':{'customers_private.json':sha(OUT/'customers_private.json'),'regional_weather.json':sha(OUT/'regional_weather.json')},
        'protected':{str(p.relative_to(ROOT)):sha(p) for p in protected},'observed_through':str(OBSERVED.date()),
        'populations':{'recent_365_days':'All known customers with a programme started in previous 365 days',
                       'repeat_customer_730_days':'At least two past purchase occasions and last programme within 730 days'},
        'unit':'Customer-month. Repeated customers occur across months; individual 90/180-day windows overlap within a fold. These are not independent claims or unique purchases.',
        'development_folds':DEV,'assessment_month_starts':TEST,'outcome_rule':'Distinct programme purchase date >= origin and < origin+horizon; programme-linked later upsells excluded.',
        'past_only':'Train outcomes mature strictly before validation or assessment start. Inputs use programme starts strictly before month origin; only initial-date sale details, no later programme extensions, paid balances, refunds or later appointments.',
        'features':{'history':NUMERIC+CATEGORICAL,'history_weather':NUMERIC+CATEGORICAL+WEATHER},
        'weather':'Archived public Kuala Lumpur regional proxy; 7-day availability lag, no customer-specific rainfall or future weather.',
        'configurations':len(HORIZONS)*len(POPULATIONS)*len(FAMILIES)*2,'families':FAMILIES,'thresholds':THRESHOLDS,
        'baselines':['training prevalence','training recency-bin rates','customer-specific median purchase cadence'],
        'selection':'All choices recorded before assessment. Per population/horizon select highest pooled development precision subject recall>=.30 and >=15 positive alerts; retain separate best-F1 policy. Select baseline by same rule.',
        'uncertainty':'800 customer-cluster bootstrap resamples; no row-independent intervals.',
        'limitations':'Exploratory extension on repeatedly examined historical data, current retrospective identity/programme linkage, sales corrections not transaction timestamps, unspecified package labels, left truncation of earlier customer history. Annual renewal cannot be labelled from inferred calendar completions.',
        'promotion_gate':'No automatic deployment. Illustrative research gate requires >=20 positive assessment customer-months, precision>=.50, recall>=.30, balanced accuracy>.5 and F1 strictly better than development-selected practical baseline.'})
    d=data(); board=[]; baseline_board=[]; folds_receipt=[]; fitted=0
    with threadpool_limits(limits=2),warnings.catch_warnings(record=True) as warning_rows:
        warnings.simplefilter('always')
        for horizon,population in itertools.product(HORIZONS,POPULATIONS):
            dd=subset(d,horizon,population); folddata=[]
            for start,end in DEV:
                tr,va=partition(dd,start,end)
                # Selection labels must also mature before later assessment.
                va=va[va.outcome_end<pd.Timestamp(TEST[0])]
                assert va.empty or (va.outcome_end<pd.Timestamp(TEST[0])).all()
                if len(tr)<50 or tr.label.nunique()<2 or len(va)==0 or va.label.nunique()<2:continue
                folddata.append((tr,va));folds_receipt.append({'horizon':horizon,'population':population,'origin':start,'train_n':len(tr),'train_positive':int(tr.label.sum()),
                    'validation_n':len(va),'validation_positive':int(va.label.sum()),'unique_validation_customers':va.customer_hash.nunique(),
                    'latest_training_outcome_end':str(tr.outcome_end.max()),'first_validation_origin':str(va.date.min())})
            if len(folddata)<2:
                print('INFEASIBLE',horizon,population,len(folddata),flush=True);continue
            for family,group in itertools.product(FAMILIES,['history','history_weather']):
                cols=NUMERIC+CATEGORICAL+(WEATHER if group.endswith('weather') else []); ys=[];ps=[]
                for tr,va in folddata:
                    m=model(family,cols);m.fit(tr[cols],tr.label);p=m.predict_proba(va[cols])[:,1];ys.extend(va.label);ps.extend(p);fitted+=1
                for threshold in THRESHOLDS:board.append({'horizon':horizon,'population':population,'model':family,'inputs':group,'input_count':len(cols),'threshold':threshold,'folds':len(folddata),**metrics(ys,ps,threshold)})
                pd.DataFrame(board).to_csv(OUT/'development_search.csv',index=False)
            for name in ['constant','recency_rate','cadence']:
                yy=[];pp=[]
                for tr,va in folddata: yy.extend(va.label);pp.extend(baseline_scores(tr,va,name,horizon))
                for threshold in THRESHOLDS:baseline_board.append({'horizon':horizon,'population':population,'model':name,'threshold':threshold,**metrics(yy,pp,threshold)})
            print('DEVELOPMENT',horizon,population,'fits',fitted,flush=True)
        save('development_folds.json',folds_receipt);pd.DataFrame(baseline_board).to_csv(OUT/'baseline_development.csv',index=False)
        selections=[]
        for horizon,population in itertools.product(HORIZONS,POPULATIONS):
            candidates=[r for r in board if r['horizon']==horizon and r['population']==population]
            if not candidates:continue
            policies,gate=choose(candidates)
            baselines,_=choose([r for r in baseline_board if r['horizon']==horizon and r['population']==population])
            selections.append({'horizon':horizon,'population':population,'policies':policies,'validation_recall_gate_met':gate,'baselines':baselines})
        save('selection.json',{'recorded_before_assessment_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha(OUT/'protocol.json'),'selections':selections})
        results=[]
        for selected in selections:
            horizon=selected['horizon'];population=selected['population'];dd=subset(d,horizon,population);tr,te=partition(dd,*TEST)
            for policy,cfg in selected['policies'].items():
                cols=NUMERIC+CATEGORICAL+(WEATHER if cfg['inputs'].endswith('weather') else [])
                m=model(cfg['model'],cols);m.fit(tr[cols],tr.label);p=m.predict_proba(te[cols])[:,1];met=metrics(te.label,p,cfg['threshold'])
                baseline=selected['baselines'][policy];bp=baseline_scores(tr,te,baseline['model'],horizon);bm=metrics(te.label,bp,baseline['threshold'])
                accepted=bool(met['positives']>=20 and met['precision']>=.5 and met['recall']>=.3 and met['balanced_accuracy']>.5 and met['f1']>bm['f1'])
                result={'horizon':horizon,'population':population,'policy':policy,'selected':cfg,'assessment':met,'baseline':{'selected':baseline,'assessment':bm},
                        'training_rows':len(tr),'training_positive':int(tr.label.sum()),'unique_test_customers':int(te.customer_hash.nunique()),
                        'input_names':cols,'confidence_95pct_customer_cluster':bootstrap(te,p,cfg['threshold']),
                        'research_gate_passed':accepted,'operationally_validated':False,'assessment_status':'Previously inspected historical era; exploratory'}
                results.append(result)
                pd.DataFrame({'customer_hash':te.customer_hash,'date':te.date.astype(str),'actual':te.label,'probability':p,'baseline':bp}).to_csv(OUT/f'assessment_{horizon}_{population}_{policy}_private.csv',index=False)
                save('results.json',results);print('ASSESSMENT',horizon,population,policy,cfg['model'],json.dumps(met),flush=True)
        save('warnings.json',sorted({str(w.message) for w in warning_rows}))
    protocol=json.loads((OUT/'protocol.json').read_text())
    assert all(sha(ROOT/path)==value for path,value in protocol['protected'].items())
    save('completion.json',{'completed_at_utc':datetime.now(timezone.utc).isoformat(),'protected_hashes_unchanged':True,'development_model_fits':fitted,
         'development_configurations':len({(r['horizon'],r['population'],r['model'],r['inputs']) for r in board}),
         'assessment_selected_policies':len(results),'script_sha256':sha(__file__)})

def report():
    """Aggregate-only report; rechecks saved predictions without refitting."""
    import nbformat
    from scripts.build_supervisor_model_review import execute,export_html
    results=json.loads((OUT/'results.json').read_text()); customers=json.loads((OUT/'customers_private.json').read_text())
    histories={hashlib.sha256(c['customer_key'].encode()).hexdigest():programme_history(c)[0]
               for c in customers if c['identity_status']!='needs_review' and not any(not s.get('date') for s in c['sales'])}
    coverage=[]; checks=[]
    for result in results:
        horizon=result['horizon'];population=result['population'];policy=result['policy']
        points=pd.read_csv(OUT/f'assessment_{horizon}_{population}_{policy}_private.csv')
        actual=metrics(points.actual,points.probability,result['selected']['threshold'])
        assert all(abs(actual[k]-result['assessment'][k])<1e-12 for k in ['accuracy','precision','recall','f1','tp','fp','fn','tn','average_precision','brier'])
        purchases=set();positive_customers=set()
        for row in points.itertuples():
            origin=pd.Timestamp(row.date);end=origin+pd.Timedelta(days=horizon)
            matches=[r for r in histories[row.customer_hash] if origin<=r['start']<end]
            assert bool(matches)==bool(row.actual) and end<=OBSERVED
            if matches:positive_customers.add(row.customer_hash)
            purchases.update((row.customer_hash,str(r['start'].date())) for r in matches)
        result['positive_unique_customers']=len(positive_customers)
        result['distinct_outcome_purchase_occasions']=len(purchases)
        result['independent_sample_caveat']='Overlapping customer-month windows can label the same actual purchase more than once; report distinct customer/event counts too.'
        result['research_gate_passed']=bool(result['research_gate_passed'] and len(positive_customers)>=20)
        checks.append({'horizon':horizon,'population':population,'policy':policy,'prediction_metrics_recomputed':True,'labels_replayed_from_programme_starts':True,'all_outcomes_mature':True})
        if policy=='precision':
            m=result['assessment'];b=result['baseline']['assessment']
            coverage.append({'Population':'Recent customers' if population=='recent_365_days' else 'Already repeat customers',
                'Horizon days':horizon,'Model':result['selected']['model'],'Inputs':result['selected']['input_count'],
                'Test customer-months':m['n'],'Test customers':result['unique_test_customers'],'Positive months':m['positives'],
                'Positive customers':len(positive_customers),'Purchase occasions':len(purchases),
                'Accuracy %':round(100*m['accuracy'],2),'Always-no accuracy %':round(100*(1-m['prevalence']),2),
                'Precision %':round(100*m['precision'],2),'Recall %':round(100*m['recall'],2),'F1':round(m['f1'],3),
                'Correct alerts':m['tp'],'False alerts':m['fp'],'Missed positive months':m['fn'],
                'Simple baseline':result['baseline']['selected']['model'],'Baseline precision %':round(100*b['precision'],2),
                'Baseline recall %':round(100*b['recall'],2),'Baseline F1':round(b['f1'],3),
                'Precision 95% interval':str([round(100*x,1) for x in result['confidence_95pct_customer_cluster']['precision']]),
                'Recall 95% interval':str([round(100*x,1) for x in result['confidence_95pct_customer_cluster']['recall']])})
    save('results.json',results);pd.DataFrame(coverage).to_csv(OUT/'summary.csv',index=False)
    protocol=json.loads((OUT/'protocol.json').read_text());folds=json.loads((OUT/'development_folds.json').read_text())
    protected=all(sha(ROOT/path)==value for path,value in protocol['protected'].items())
    assert protected
    save('acceptance.json',{'verified_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,
                          'protected_unchanged':protected,'same_historical_block_reused':True,
                          'initial_invalid_attempt_retained':True,'automatic_promotion':False,
                          'notebook_execution':'Sequential Python cells through existing project executor; no native Jupyter kernel available.'})
    payload={'summary':coverage,'audit':json.loads((OUT/'data_audit.json').read_text()),'folds':folds,
             'completion':json.loads((OUT/'completion.json').read_text()),'inputs':{'History':NUMERIC+CATEGORICAL,'Extra regional weather':WEATHER}}
    cells=[]
    md=lambda t:cells.append(nbformat.v4.new_markdown_cell(t))
    code=lambda t:cells.append(nbformat.v4.new_code_cell(t))
    md('''# Can Nomobug predict another purchase from existing customers?
**21 October 2026 · completed exploratory comparison**

## The answer
No candidate established high precision together with useful coverage. The monthly task is hard because most customers do not buy another programme soon. Previously repeated customers were easier to distinguish, but the test contains only 7 positive customer-months for 30 days and 19 for 90 days. Those months can repeat the same purchase event.

The study tested **60 model/input/horizon/population configurations**, using 156 earlier development fits. Six classifier families were compared. The 180-day repeat-customer study was infeasible because its earlier mature training history was too small. No production model was changed.''')
    code('import json\nimport pandas as pd\nimport matplotlib.pyplot as plt\ndata=json.loads('+repr(json.dumps(payload,allow_nan=False))+')\nsummary=pd.DataFrame(data["summary"])\nplt.rcParams.update({"font.size":11,"axes.spines.top":False,"axes.spines.right":False})')
    md('''## What is being predicted?
At the first day of a month, predict whether a known customer will have another **distinct programme purchase recorded in Sales** during the following 30, 90 or 180 days. Management could use this to understand expected repeat business and review customer relationships. A negative answer does not prove a customer has left, and no automated messaging is implied.

**Recent customers:** last programme bought in the previous 365 days. **Already repeat customers:** at least two past purchase occasions, with the most recent within 730 days.

The customer and programme links are exact reviewed links from the reporting snapshot. The 1x + Upsell 2x and THAS 4 + 20 records remain one programme each. An upsell inside the same programme is not counted as a new purchase. Only initial-date details inform earlier predictions; later programme values and current payment balances are excluded.

We could not truthfully label actual contract renewal after a final completed service: this archived appointment table has no customer/programme keys or independently confirmed completion. This study therefore uses observed purchase dates, not an invented expiry date.''')
    code('display(summary[["Population","Horizon days","Test customer-months","Test customers","Positive months","Positive customers","Purchase occasions"]])')
    md('''## Which results held up?
The model and threshold shown below were chosen from earlier validation. The precision policy required at least 30% recall and 15 validation alerts. A separately retained F1 policy selected the same final candidate in each feasible task. They are the same predictions, not independent successes.''')
    code('display(summary[["Population","Horizon days","Model","Inputs","Accuracy %","Always-no accuracy %","Precision %","Recall %","F1"]])')
    code('''fig,ax=plt.subplots(figsize=(10,4.8))
labels=[f"{r['Population']} · {r['Horizon days']} days" for r in data['summary']]
x=list(range(len(labels)))
ax.bar([i-.18 for i in x],summary['Precision %'],.36,label='Precision',color='#2563eb')
ax.bar([i+.18 for i in x],summary['Recall %'],.36,label='Recall',color='#f59e0b')
ax.set_ylim(0,100);ax.set_ylabel('Percent');ax.set_xticks(x,labels,rotation=25,ha='right')
ax.set_title('Monthly repurchase forecasts · later historical assessment',loc='left');ax.legend();plt.tight_layout();plt.show()''')
    md('''Accuracy alone is especially misleading here. For 30 days among recent customers, always predicting no purchase scores about 99.2%. The selected complex model scores 81.2%, with 18 correct alerts and 814 false alerts.

Among already repeat customers, the 30-day model scores 96.8% accuracy but only 28.6% precision: **4 correct alerts, 10 false alerts**. The 90-day version has 24.0% precision and finds 12 of 19 positive monthly windows. This remains too weak and too small to call dependable.''')
    code('display(summary[["Population","Horizon days","Correct alerts","False alerts","Missed positive months","Precision 95% interval","Recall 95% interval"]])')
    md('''## Did machine learning beat practical simple rules?
Simple rules included the historical purchase rate, a purchase rate learned within recency bands, and the customer's own median time between previous purchase occasions. Their thresholds were selected on the same earlier validation folds.

The complex models improve some F1 scores, especially in the very small already-repeat group. The all-customer 180-day model has slightly lower precision than the customer-cadence baseline. These improvements do not establish a high-precision operational model.''')
    code('display(summary[["Population","Horizon days","Precision %","Recall %","F1","Simple baseline","Baseline precision %","Baseline recall %","Baseline F1"]])')
    md('''## What information was used?
The main 19 inputs describe how recently and often the customer bought, initial recorded programme prices, previous purchase gaps, seasonal month, the most recent package, pest and premises. The weather variant adds four regional weather values. These end at least seven days before prediction and contain no future rainfall.

Weather is an existing archived Kuala Lumpur proxy, not a new customer-specific download. No new external dataset was introduced in this branch.''')
    code('display(pd.DataFrame({"Input group":list(data["inputs"]),"Inputs":[", ".join(v) for v in data["inputs"].values()]}))')
    md('''## How was the comparison kept fair?
All assessment month starts are **January–April 2026**. The longest label ends 28 September and is observed before the conservative 11 October bound. Sources come from the archived 14 October reporting snapshot, not a live source audit.

Every training outcome ends before the next validation or assessment origin. Every validation outcome used to choose models or thresholds also ends before 1 January 2026. These gaps are essential for a 90/180-day label. The same customer can appear in earlier and later months because the use case is prediction for existing customers; the features contain only that customer's past information.

The 90/180-day monthly labels overlap within a cohort, so customer-month totals are not independent purchase counts. We report distinct customers and outcome purchase occasions, and bootstrap whole customers for uncertainty.

The first attempt missed the requirement that all long-horizon validation outcomes must mature before assessment. It was stopped, retained under `_initial_invalid`, and excluded. Partial assessment scores had already been seen. The repaired study is therefore explicitly adaptive and reuses a previously examined historical period; it is not fresh independent evidence.''')
    code('display(pd.DataFrame(data["folds"])[["horizon","population","origin","train_n","train_positive","validation_n","validation_positive","unique_validation_customers","latest_training_outcome_end"]])')
    md('''## Source coverage and recommendation
There are 2,284 customer groups in the source, of which 2,142 are eligible after identity/date/observation exclusions. Only 159 have multiple distinct programmes. Most source package labels are unspecified, and purchases before the company's records began are unknown. Retrospective source corrections and programme membership can differ from what staff knew historically.

No candidate qualified for promotion. Keep this as an honest negative experiment. Reliable renewal dates and a larger number of independently verified repeat purchases would help more than adding many arbitrary inputs. The existing frozen prospective experiment remains unchanged.''')
    code('display(pd.DataFrame([data["audit"]]));print("Configuration count:",data["completion"]["development_configurations"]);print("Protected model hashes verified unchanged.")')
    nb=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}})
    execute(nb);nbformat.validate(nb)
    nbformat.write(nb,OUT/'Existing_Customer_Repurchase.ipynb');export_html(nb,OUT/'Existing_Customer_Repurchase.html')
    (OUT/'README.md').write_text('Open Existing_Customer_Repurchase.html for the plain-language results. The notebook contains aggregate outputs. results.json and summary.csv hold verified metrics. Raw customer data and assessment files ending _private.csv must remain private. No new external data in this branch. Initial invalid receipts are retained and excluded; this is adaptive historical research, not independent prospective evidence.\n',encoding='utf-8')

if __name__=='__main__':
    import sys
    if '--report' in sys.argv:report()
    else:main()
