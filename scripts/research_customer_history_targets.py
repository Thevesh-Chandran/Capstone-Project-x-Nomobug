"""Separate exploratory repurchase study at each programme purchase.

Past purchases can inform a later purchase by the same customer. This deliberately
tests ongoing customer management, not generalisation to entirely new customers.
"""
import itertools,json,hashlib
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from threadpoolctl import threadpool_limits
from scripts.research_expanded_targets import ROOT,OUT,SEED,DEV,WEATHER,FEATURES,EXTRA,weather_data,weather_features,columns,classifier,scores,sha,save

DEST=OUT/'customer_history'
HISTORY=['previous_programmes','days_since_first_purchase','days_since_last_purchase','past_average_sale','purchases_last_90_days','purchases_last_365_days']
FAMILIES=['plain_logistic','logistic','random_forest','extra_trees','boosting','catboost']

def dataset(customers,horizon,w):
    rows=[];end=pd.Timestamp('2026-10-11');excluded={}
    for c in customers:
        if c['identity_status']=='needs_review' or any(not s.get('date') for s in c['sales']):continue
        sales=[s for s in c['sales'] if pd.Timestamp(s['date'])<=end];starts={}
        for s in sales:
            date=pd.Timestamp(s['date']);key=s['programme_id'];starts[key]=min(starts.get(key,date),date)
        # Collapse simultaneous first purchases to one customer/date decision.
        for date in sorted(set(starts.values())):
            if date+pd.Timedelta(days=horizon)>end:continue
            initial=[s for s in sales if pd.Timestamp(s['date'])==date and starts[s['programme_id']]==date]
            prior_dates=[a for a in starts.values() if a<date]
            prior_sales=[s for s in sales if pd.Timestamp(s['date'])<date]
            cats=lambda key:' | '.join(sorted({str(s.get(key) or 'Unknown') for s in initial}))
            amount=sum(float(s.get('sales_rm') or 0) for s in initial)
            row={'customer_hash':hashlib.sha256(str(c['customer_key']).encode()).hexdigest(),'date':date,'outcome_end':date+pd.Timedelta(days=horizon),
                'label':int(any(date<a<=date+pd.Timedelta(days=horizon) for a in starts.values())),
                'log_initial_sales':np.log1p(max(0,amount)),'missing_amount':int(any(s.get('sales_rm') is None for s in initial)),
                'month_sin':np.sin(date.month*2*np.pi/12),'month_cos':np.cos(date.month*2*np.pi/12),'initial_sale_rows':len(initial),
                **{k:cats(k) for k in ['package','pest','premise','district']},
                'previous_programmes':len(prior_dates),'days_since_first_purchase':int((date-min(prior_dates)).days) if prior_dates else 0,
                'days_since_last_purchase':int((date-max(prior_dates)).days) if prior_dates else 0,
                'past_average_sale':float(np.mean([s['sales_rm'] for s in prior_sales if s['sales_rm'] is not None])) if any(s['sales_rm'] is not None for s in prior_sales) else 0,
                'purchases_last_90_days':sum(a>=date-pd.Timedelta(days=90) for a in prior_dates),
                'purchases_last_365_days':sum(a>=date-pd.Timedelta(days=365) for a in prior_dates),**weather_features(w,date)}
            rows.append(row)
    d=pd.DataFrame(rows);assert not d.duplicated(['customer_hash','date']).any()
    return d

def features(group):return FEATURES+EXTRA+(HISTORY if group!='purchase_only' else [])+(WEATHER if group=='history_weather' else [])
def fitted_model(name,cols):
    base=classifier('logistic' if name in ['plain_logistic','catboost'] else name,cols)
    if name=='plain_logistic':return make_pipeline(base.steps[0][1],LogisticRegression(C=.1,max_iter=500,random_state=SEED))
    if name=='catboost':
        from catboost import CatBoostClassifier
        return make_pipeline(base.steps[0][1],CatBoostClassifier(iterations=100,depth=3,learning_rate=.05,l2_leaf_reg=10,verbose=False,thread_count=2,allow_writing_files=False,random_seed=SEED))
    return base

def partitions(d,start,end,window):
    start=pd.Timestamp(start);tr=d[d.outcome_end<start]
    if window=='last_365_days':tr=tr[tr.date>=start-pd.Timedelta(days=365)]
    va=d[d.date.between(start,pd.Timestamp(end))]
    assert tr.empty or tr.outcome_end.max()<start
    return tr,va

def main():
    DEST.mkdir(exist_ok=True)
    if (DEST/'results.json').exists():raise RuntimeError('Assessment already completed; do not overwrite')
    save(DEST/'protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(OUT/'customers_private.json'),'script_sha256':sha(__file__),
        'question':'At each distinct programme purchase, will this customer purchase another distinct programme within 30/90/180 days?',
        'decision':'Anticipate repeat business and review contract/service relationships; no automatic customer messaging',
        'development':DEV,'180day_feasibility':'Skip first fold because immature history has fewer than 50 rows',
        'assessment':['2026-01-01','2026-04-14'],'families':FAMILIES,'history':['all_history','last_365_days'],
        'features':['purchase_only','history','history_weather'],'thresholds':[.01,.025,.05,.1,.15,.2,.3,.4,.5,.6,.7,.8],
        'selection':'Highest pooled development precision subject to recall>=0.30 and >=10 predicted positives; tie F1. Also keep best-F1 policy for comparison, selected before assessment.',
        'limits':'Adaptive extension after prior first-purchase results; same historical period, not new untouched evidence. Repeated customers allowed only through past information; grouped uncertainty. Current retrospective programme links may differ from original recording.'})
    customers=json.loads((OUT/'customers_private.json').read_text());w=weather_data();results=[];audits=[]
    with threadpool_limits(limits=2):
        for horizon in [30,90,180]:
            d=dataset(customers,horizon,w);board=[]
            for family,group,window in itertools.product(FAMILIES,['purchase_only','history','history_weather'],['all_history','last_365_days']):
                cols=features(group);yy=[];pp=[];folds=[]
                for start,end in DEV:
                    tr,va=partitions(d,start,end,window)
                    if len(tr)<50 or tr.label.nunique()<2 or va.label.nunique()<2:continue
                    m=fitted_model(family,cols);m.fit(tr[cols],tr.label);p=m.predict_proba(va[cols])[:,1];yy.extend(va.label);pp.extend(p)
                    folds.append({'start':start,'training':len(tr),'training_positive':int(tr.label.sum()),'validation':len(va),'validation_positive':int(va.label.sum())})
                assert len(folds)==(2 if horizon==180 else 3)
                for t in [.01,.025,.05,.1,.15,.2,.3,.4,.5,.6,.7,.8]:
                    board.append({'horizon':horizon,'model':family,'inputs':group,'window':window,'threshold':t,**scores(yy,pp,t)})
            pd.DataFrame(board).to_csv(DEST/f'development_{horizon}.csv',index=False)
            eligible=[r for r in board if r['recall']>=.3 and r['predicted_positive']>=10]
            policies={'precision':max(eligible,key=lambda r:(r['precision'],r['f1'])),'f1':max(eligible,key=lambda r:(r['f1'],r['precision']))}
            save(DEST/f'selection_{horizon}.json',{'selected_at_utc':datetime.now(timezone.utc).isoformat(),'policies':policies})
            for policy,c in policies.items():
                tr,te=partitions(d,'2026-01-01','2026-04-14',c['window']);cols=features(c['inputs'])
                m=fitted_model(c['model'],cols);m.fit(tr[cols],tr.label);p=m.predict_proba(te[cols])[:,1];met=scores(te.label,p,c['threshold'])
                pd.DataFrame({'actual':te.label.to_numpy(),'probability':p,'customer_hash':te.customer_hash}).to_csv(DEST/f'assessment_{horizon}_{policy}_private.csv',index=False)
                rng=np.random.default_rng(SEED);groups=te.customer_hash.unique();ys=te.label.to_numpy();ids=[np.flatnonzero(te.customer_hash.to_numpy()==key) for key in groups];vals=[]
                for _ in range(1000):
                    idx=np.concatenate([ids[i] for i in rng.integers(0,len(ids),len(ids))]);z=p[idx]>=c['threshold'];y=ys[idx]
                    tp=np.sum(z&(y==1));fp=np.sum(z&(y==0));fn=np.sum(~z&(y==1));vals.append([float(tp/max(1,tp+fp)),float(tp/max(1,tp+fn))])
                ci=np.quantile(vals,[.025,.975],axis=0).T.tolist()
                result={'horizon':horizon,'policy':policy,'selected':c,'assessment':met,'input_count':len(cols),'input_names':cols,'training_rows':len(tr),'training_positive':int(tr.label.sum()),
                    'unique_assessment_customers':len(groups),'precision_95pct_cluster_interval':ci[0],'recall_95pct_cluster_interval':ci[1],
                    'always_no_accuracy':1-met['prevalence'],'research_gate_passed':bool(met['positives']>=20 and met['precision']>=.5 and met['recall']>=.3 and met['balanced_accuracy']>.5),
                    'operationally_validated':False}
                results.append(result);print(horizon,policy,json.dumps(met),flush=True)
                save(DEST/'progress.json',results)
            audits.append({'horizon':horizon,'eligible_purchase_dates':len(d),'unique_customers':d.customer_hash.nunique(),'development_folds':folds})
    save(DEST/'results.json',results);save(DEST/'data_audit.json',audits)

if __name__=='__main__':main()
