"""Separate exploratory first-recorded-purchase study; no PII exported."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,ExtraTreesClassifier,HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score,roc_auc_score,brier_score_loss
from threadpoolctl import threadpool_limits
from scripts.research_additional_models import ROOT,save,digest


def build(customers,observed_through):
    end=pd.Timestamp(observed_through);rows=[];excluded={'identity_review':0,'no_dates':0,'immature':0,'unknown_date_in_profile':0}
    for c in customers:
        if c['identity_status']=='needs_review':excluded['identity_review']+=1;continue
        # An undated sale could change which purchase was first or the outcome.
        if any(not s['date'] for s in c['sales']):excluded['unknown_date_in_profile']+=1;continue
        sales=[s for s in c['sales'] if pd.Timestamp(s['date'])<=end]
        if not sales:excluded['no_dates']+=1;continue
        dates={}
        for s in sales:
            d=pd.Timestamp(s['date']);key=s['programme_id'];dates[key]=min(dates.get(key,d),d)
        first=min(dates.values());mature=first+pd.Timedelta(days=90)
        if mature>end:excluded['immature']+=1;continue
        initial=[s for s in sales if pd.Timestamp(s['date'])==first]
        amount=sum(float(s['sales_rm'] or 0) for s in initial)
        missing=any(s['sales_rm'] is None for s in initial)
        categorical=lambda key:' | '.join(sorted(set(str(s.get(key) or 'Unknown') for s in initial)))
        positive=int(any(first<d<=mature for d in dates.values()))
        rows.append({'first_date':first,'outcome_end':mature,'log_initial_sales':math.log1p(max(0,amount)),
            'missing_amount':int(missing),'month_sin':math.sin(first.month*2*math.pi/12),'month_cos':math.cos(first.month*2*math.pi/12),
            'package':categorical('package'),'pest':categorical('pest'),'premise':categorical('premise'),'repeat90':positive})
    return pd.DataFrame(rows),excluded


def model(name):
    pre=ColumnTransformer([('num',make_pipeline(SimpleImputer(strategy='median'),StandardScaler()),
        ['log_initial_sales','missing_amount','month_sin','month_cos']),
        ('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['package','pest','premise'])])
    if name in ('logistic','weighted_logistic'):
        est=LogisticRegression(C=.1,max_iter=500,class_weight='balanced' if name.startswith('weighted') else None,random_state=20261015)
    elif name=='random_forest':est=RandomForestClassifier(n_estimators=200,max_depth=4,min_samples_leaf=15,class_weight='balanced',random_state=20261015,n_jobs=2)
    elif name=='extra_trees':est=ExtraTreesClassifier(n_estimators=200,max_depth=4,min_samples_leaf=15,class_weight='balanced',random_state=20261015,n_jobs=2)
    elif name=='hist_gradient_boosting':est=HistGradientBoostingClassifier(max_iter=80,max_leaf_nodes=7,min_samples_leaf=20,l2_regularization=10,early_stopping=False,random_state=20261015)
    elif name=='catboost':
        from catboost import CatBoostClassifier
        est=CatBoostClassifier(iterations=100,depth=3,learning_rate=.05,l2_leaf_reg=10,verbose=False,allow_writing_files=False,thread_count=2,random_seed=20261015)
    else:raise ValueError(name)
    return make_pipeline(pre,est)


def score(y,p):
    y=np.asarray(y);p=np.asarray(p);budget=math.ceil(.2*len(y));top=np.argsort(-p,kind='stable')[:budget]
    prevalence=float(y.mean());found=int(y[top].sum());positives=int(y.sum())
    return {'customers':len(y),'positive_customers':positives,'prevalence':prevalence,
        'average_precision':float(average_precision_score(y,p)),
        'roc_auc':float(roc_auc_score(y,p)) if 0<positives<len(y) else None,
        'brier':float(brier_score_loss(y,p)),'review_budget':budget,'cases_in_review_list':found,
        'false_alerts_in_review_list':budget-found,'capture_fraction':found/positives if positives else 0,
        'random_expected_cases':budget*prevalence,'review_lift':found/(budget*prevalence) if prevalence else 0}


def main():
    folder=ROOT/'outputs/additional_model_research/20261014';protocol_path=ROOT/'config/cp2_repeat_purchase_research_v1.json'
    protocol=json.loads(protocol_path.read_text());source=ROOT/protocol['source'];customers=json.loads(source.read_text())
    df,excluded=build(customers,protocol['observed_through'])
    dev_start,dev_end=map(pd.Timestamp,protocol['development_first_purchase_dates'])
    test_start,test_end=map(pd.Timestamp,protocol['test_first_purchase_dates'])
    development=df[df.first_date.between(dev_start,dev_end)];train=df[df.outcome_end<dev_start]
    test=df[df.first_date.between(test_start,test_end)];final_train=df[df.outcome_end<test_start]
    assert train.outcome_end.max()<dev_start and final_train.outcome_end.max()<test_start
    features=['log_initial_sales','missing_amount','month_sin','month_cos','package','pest','premise']
    results=[]
    with threadpool_limits(limits=2):
        for name in protocol['candidate_families']:
            fitted=model(name);fitted.fit(train[features],train.repeat90)
            p=fitted.predict_proba(development[features])[:,1]
            results.append({'model':name,**score(development.repeat90,p)})
        selected=max(results,key=lambda r:r['average_precision'])
        selection={'protocol_sha256':digest(protocol_path),'source_sha256':digest(source),'excluded':excluded,
            'cohorts':{'training':len(train),'development':len(development),'final_training':len(final_train),'test':len(test)},
            'development_candidates':results,'selected':selected}
        save(folder/'repeat90_selection.json',selection)
        fitted=model(selected['model']);fitted.fit(final_train[features],final_train.repeat90)
        p=fitted.predict_proba(test[features])[:,1];y=test.repeat90.to_numpy();holdout=score(y,p)
        rng=np.random.default_rng(20261015);lifts=[]
        for _ in range(4000):
            idx=rng.integers(0,len(y),len(y))
            if y[idx].sum():lifts.append(score(y[idx],p[idx])['review_lift'])
        holdout['review_lift_90pct_bootstrap_interval']=list(map(float,np.quantile(lifts,[.05,.95])))
        selection['holdout']=holdout;selection['research_gate_passed']=bool(holdout['positive_customers']>=20 and holdout['average_precision']>holdout['prevalence'] and holdout['review_lift']>1.5 and holdout['review_lift_90pct_bootstrap_interval'][0]>1)
        selection['operationally_validated']=False
        save(folder/'repeat90_results.json',selection)
        # Labels/scores only, no name, contact, customer key or precise geography.
        pd.DataFrame({'actual':y,'probability':p}).to_csv(folder/'repeat90_test_scores.csv',index=False)
        print(json.dumps(selection,default=str))


if __name__=='__main__':main()
