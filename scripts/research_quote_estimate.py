"""Predict recorded package sales amounts from quote-time requirements.

This is a price benchmark, not approved pricing, profitability or settlement.
No current-sale amount, deposit, balance, invoice, full package name or sale ID
is an input. Historical source corrections remain a limitation.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,re
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator,RegressorMixin,clone

class PerSessionRegressor(RegressorMixin,BaseEstimator):
    """Learn amount/session; return total amount using the supplied session count."""
    def __init__(self,estimator):self.estimator=estimator
    def fit(self,X,y):
        units=np.asarray(X['sessions'],dtype=float)
        if not np.isfinite(units).all() or (units<=0).any():raise ValueError('Known positive session counts required')
        self.estimator_=clone(self.estimator).fit(X,np.asarray(y)/units);return self
    def predict(self,X):
        units=np.asarray(X['sessions'],dtype=float)
        if not np.isfinite(units).all() or (units<=0).any():raise ValueError('Known positive session counts required')
        return self.estimator_.predict(X)*units

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261030_quote_estimate'
REQUIREMENTS=['sessions','tbs_units','trbs_units','includes_car','misting','fogging','service_family','premise','pest','district']
CONTEXT=['prior_programmes','prior_average_sales_rm','customer_age_days','month_sin','month_cos']
GROUP=['service_family','premise','sessions','tbs_units','trbs_units','includes_car','misting','fogging']
CATEGORIES=['service_family','premise','pest','district']

def write(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(value,indent=2,default=str,allow_nan=False),encoding='utf-8')

def package_inputs(text):
    # Strip explicit money before deriving requirements; raw text is never fitted.
    text=re.sub(r'\bRM\s*[\d,.]+',' ',str(text or '').upper())
    def units(token):
        found=re.search(r'\b(\d+)\s*(?:UNITS?\s*)?'+token+r'\b',text)
        return int(found[1]) if found else 0
    family='TRBS' if re.search(r'\bTRBS\b',text) else 'TBS' if re.search(r'\bTBS\b',text) else 'GPC' if re.search(r'\b(?:GPC|B2B)\s*\d*',text) else 'OTHER'
    return {'tbs_units':units('TBS'),'trbs_units':units('TRBS'),'includes_car':int(bool(re.search(r'\bCAR\b',text))),
            'misting':int('MISTING' in text),'fogging':int('FOGGING' in text),'service_family':family}

def dataset(business,facts):
    lookup={r['sales_record_id']:r for r in facts};audit=Counter();records=[]
    reliable={c['customer_key']:c['identity_status']!='needs_review' for c in business['customers']}
    all_sales=business['records']['sales']
    for sale in all_sales:
        audit['source_sales']+=1;f=lookup[sale['sale_id']]
        day=pd.to_datetime(f.get('closed_date'),errors='coerce')
        try:amount=float(f['sale_total_rm'])
        except (ValueError,TypeError):amount=np.nan
        if not f['include_in_sale_count'] or f.get('sale_total_needs_review') or pd.isna(day) or day>pd.Timestamp('2026-10-27') or not np.isfinite(amount) or amount<=0:
            audit['unknown_invalid_free_or_incomplete_date']+=1;continue
        # A linked upsell is not a stand-alone complete package quotation.
        if not sale['programme_id'].startswith('SALE_'):
            audit['pooled_programme_member']+=1;continue
        known=reliable.get(sale['customer_key'],False)
        prior=[s for s in all_sales if s['customer_key']==sale['customer_key'] and s['sale_id']!=sale['sale_id']
               and s['programme_id']!=sale['programme_id'] and s.get('date') and pd.Timestamp(s['date'])<day] if known else []
        prior_programmes=len({s['programme_id'] for s in prior})
        prior_values=[s['sales_rm'] for s in prior]
        prior_mean=float(np.mean(prior_values)) if prior_values and all(v is not None for v in prior_values) else (0. if known and not prior else np.nan)
        records.append({'sale_id':sale['sale_id'],'customer_group':sale['customer_key'],'date':day,'target_rm':amount,
            'sessions':float(f['package_sessions_recorded']) if f.get('package_sessions_recorded') is not None else np.nan,
            **package_inputs(f.get('package_type_raw')),'premise':str(f.get('premise_type') or 'Unknown'),
            'pest':str(sale.get('pest') or 'Unknown'),'district':str(sale.get('district') or 'Unassigned'),
            'prior_programmes':float(prior_programmes) if known else np.nan,'prior_average_sales_rm':prior_mean,
            'customer_age_days':float((day-min(pd.Timestamp(s['date']) for s in prior)).days) if prior else (0. if known else np.nan),
            'month_sin':float(np.sin(day.month*2*np.pi/12)),'month_cos':float(np.cos(day.month*2*np.pi/12))})
    frame=pd.DataFrame(records).sort_values(['date','sale_id']).reset_index(drop=True)
    assert frame.sale_id.is_unique
    audit['eligible_quotes']=len(frame)
    return frame,dict(audit)

def partition(frame):
    dates=frame.date.sort_values().reset_index(drop=True)
    val_start=dates.iloc[int(len(dates)*.6)];test_start=dates.iloc[int(len(dates)*.8)]
    test=frame[frame.date>=test_start].copy();test_groups=set(test.customer_group)
    valid=frame[(frame.date>=val_start)&(frame.date<test_start)&~frame.customer_group.isin(test_groups)].copy()
    train=frame[(frame.date<val_start)&~frame.customer_group.isin(test_groups|set(valid.customer_group))].copy()
    assert not(set(train.customer_group)&set(valid.customer_group) or set(train.customer_group)&set(test.customer_group) or set(valid.customer_group)&set(test.customer_group))
    return train,valid,test,{'validation_start':str(val_start.date()),'test_start':str(test_start.date()),
                           'rule':'60th/80th percentile sale dates; customer groups disjoint, never choose split by score'}

def price_baseline(train,test,group=GROUP):
    # The strongest lookup baseline uses actual quoted requirements, not an
    # artificially weak global mean. Unseen combinations fall back by family.
    a=train.copy();b=test.copy()
    for col in group:a[col]=a[col].fillna('Unknown').astype(str);b[col]=b[col].fillna('Unknown').astype(str)
    medians=a.groupby(group,dropna=False).target_rm.median().to_dict();families=a.groupby('service_family').target_rm.median().to_dict()
    return np.array([medians.get(tuple(r[k] for k in group),families.get(r['service_family'],float(train.target_rm.median()))) for _,r in b.iterrows()])

def measures(y,pred):
    from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
    y=np.asarray(y);pred=np.maximum(0,np.asarray(pred));absolute=np.abs(y-pred)
    return {'rows':len(y),'mae_rm':float(mean_absolute_error(y,pred)),'mse_rm_squared':float(mean_squared_error(y,pred)),
        'rmse_rm':float(np.sqrt(mean_squared_error(y,pred))),'r_squared':float(r2_score(y,pred)),
        'wape':float(absolute.sum()/y.sum()),'median_absolute_percentage_error':float(np.median(absolute/y)),
        'within_20_percent':float(np.mean(absolute/y<=.2)),'median_absolute_error_rm':float(np.median(absolute))}

def study(frame,output_dir=None,feature_sets=None,include_per_session=False,research_context=None):
    output_dir=Path(output_dir) if output_dir is not None else OUT
    output_dir.mkdir(parents=True,exist_ok=True)
    def write(name,value):
        (output_dir/name).write_text(json.dumps(value,indent=2,default=str,allow_nan=False),encoding='utf-8')
    import joblib
    from threadpoolctl import threadpool_limits
    from sklearn.base import clone
    from sklearn.compose import ColumnTransformer,TransformedTargetRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler,OneHotEncoder
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LinearRegression,Ridge
    from sklearn.tree import DecisionTreeRegressor
    from sklearn.ensemble import RandomForestRegressor,ExtraTreesRegressor,HistGradientBoostingRegressor
    from catboost import CatBoostRegressor
    from sklearn.inspection import permutation_importance
    train,valid,test,split=partition(frame);seed=20261030
    families={'Linear regression':LinearRegression(), 'Ridge 10':Ridge(alpha=10), 'Ridge 100':Ridge(alpha=100),
        'Decision tree depth 3':DecisionTreeRegressor(max_depth=3,min_samples_leaf=15,random_state=seed),
        'Decision tree depth 6':DecisionTreeRegressor(max_depth=6,min_samples_leaf=10,random_state=seed),
        'Random forest':RandomForestRegressor(n_estimators=300,max_depth=12,min_samples_leaf=5,n_jobs=1,random_state=seed),
        'Extra Trees':ExtraTreesRegressor(n_estimators=300,max_depth=12,min_samples_leaf=3,n_jobs=1,random_state=seed),
        'Gradient boosting':HistGradientBoostingRegressor(loss='absolute_error',max_iter=200,max_leaf_nodes=15,min_samples_leaf=10,l2_regularization=10,random_state=seed),
        'CatBoost':CatBoostRegressor(iterations=400,depth=4,learning_rate=.04,l2_leaf_reg=10,loss_function='MAE',thread_count=1,random_seed=seed,verbose=False,allow_writing_files=False)}
    protocol={'target':'Recorded package sales amount (RM), not profit or cash received','split':split,
      'feature_sets':feature_sets or {'requirements':REQUIREMENTS,'requirements_and_context':REQUIREMENTS+CONTEXT},
      'families':{k:v.get_params() for k,v in families.items()},'target_transforms':['original RM','log1p RM']+(['per session','log per session'] if include_per_session else []),
      'selection':'Lowest validation MAE; no assessment comparison before selection; threshold-free regression',
      'excluded_inputs':['Current sale amount','deposit','remaining balance','paid amounts','invoices','full package name','IDs','future purchases'],
      'baseline':'Training-only median by requirements, fallback to family median',
      'acceptance':'At least 10% lower MAE than the same baseline, positive 95% customer-bootstrap improvement lower bound, median percentage error at most 20%',
      'independence':'Historical source and periods previously examined; exploratory new target, not independent future evaluation',
      'source_sha256':{n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['business_private.json','sales_facts_private.json']}}
    protocol.update(research_context or {})
    write('protocol_before_training.json',protocol);candidates=[];models={};failures=[]
    with threadpool_limits(limits=1):
        for group,features in protocol['feature_sets'].items():
            cats=[c for c in features if not pd.api.types.is_numeric_dtype(frame[c])];nums=[c for c in features if c not in cats]
            prep=ColumnTransformer([('numbers',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler()),nums),
                ('categories',OneHotEncoder(handle_unknown='ignore',min_frequency=5,sparse_output=False),cats)])
            for name,estimator in families.items():
                for transform in (['rm','log_rm','per_session','log_per_session'] if include_per_session else ['rm','log_rm']):
                    model=make_pipeline(clone(prep),clone(estimator))
                    if transform in ('log_rm','log_per_session'):model=TransformedTargetRegressor(regressor=model,func=np.log1p,inverse_func=np.expm1)
                    if transform in ('per_session','log_per_session'):model=PerSessionRegressor(model)
                    key=name+' / '+group+' / '+transform
                    try:
                        model.fit(train[features],train.target_rm);pred=np.maximum(0,model.predict(valid[features]))
                        if not np.isfinite(pred).all():raise ValueError('Nonfinite validation predictions')
                        measured=measures(valid.target_rm,pred)
                        if not all(np.isfinite(v) for v in measured.values()):raise ValueError('Nonfinite validation metrics')
                    except (ValueError,OverflowError) as error:
                        failures.append({'candidate':key,'error_type':type(error).__name__,'message':str(error)[:300]});continue
                    row={'candidate':key,'inputs':len(features),**measured};candidates.append(row);models[key]=(model,features)
                    print('Validation:',key,round(row['mae_rm'],2),flush=True)
        write('candidate_failures.json',failures)
        if not candidates:raise ValueError('No model fit completed; inspect candidate_failures.json before interpreting results')
        selected=min(candidates,key=lambda r:(r['mae_rm'],r['rmse_rm'],r['candidate']))
        write('validation_results.json',candidates);write('selected_before_test.json',selected)
        development,features=models[selected['candidate']]
        effect=permutation_importance(development,valid[features],valid.target_rm,scoring='neg_mean_absolute_error',n_repeats=15,random_state=seed,n_jobs=1)
        pd.DataFrame({'input':features,'validation_MAE_increase_rm':effect.importances_mean,'sd_rm':effect.importances_std}).sort_values('validation_MAE_increase_rm',ascending=False).to_csv(output_dir/'input_effects.csv',index=False)
        final=clone(development);refit=pd.concat([train,valid],ignore_index=True);final.fit(refit[features],refit.target_rm)
        pred=np.maximum(0,final.predict(test[features]));baseline=price_baseline(refit,test)
        joblib.dump({'pipeline':final,'features':features,'protocol':protocol},output_dir/'experimental_model.joblib')
    result=measures(test.target_rm,pred);base=measures(test.target_rm,baseline)
    predictions=test[['sale_id','customer_group','date','target_rm','premise','service_family']].copy();predictions['prediction_rm']=pred;predictions['baseline_rm']=baseline
    predictions.to_csv(output_dir/'test_predictions_private.csv',index=False)
    delta=np.abs(test.target_rm.to_numpy()-baseline)-np.abs(test.target_rm.to_numpy()-pred)
    groups=test.customer_group.to_numpy();unique=np.unique(groups);sums=np.array([delta[groups==g].sum() for g in unique]);sizes=np.array([(groups==g).sum() for g in unique]);rng=np.random.default_rng(seed)
    boots=[]
    for _ in range(1000):ix=rng.integers(0,len(unique),len(unique));boots.append(float(sums[ix].sum()/sizes[ix].sum()))
    interval=[float(x) for x in np.quantile(boots,[.025,.975])]
    reduction=float(1-result['mae_rm']/base['mae_rm']);passing=reduction>=.1 and interval[0]>0 and result['median_absolute_percentage_error']<=.2
    subsets={}
    for premise,group in predictions.groupby('premise'):
        subsets[premise]={'model':measures(group.target_rm,group.prediction_rm),'baseline':measures(group.target_rm,group.baseline_rm)} if len(group)>1 else {'rows':len(group)}
    output={'selected':selected['candidate'],'raw_inputs':features,'input_count':len(features),'training_rows':len(train),'validation_rows':len(valid),'test_rows':len(test),'final_fit_rows':len(refit),
       'test':result,'baseline':base,'mae_reduction':reduction,'bootstrap_MAE_improvement_rm_95':interval,'segments':subsets,
       'passed_research_gate':bool(passing),'deployed':False,'limitations':['Recorded sold price is a quotation benchmark, not a mandated price or profit estimate.',
       'Exact building size, verified infestation severity and actual treatment cost are unavailable.',
       'Package and customer fields come from a later snapshot; historical corrections cannot be fully reconstructed.',
       'Historical periods were previously inspected; new future quotations are needed to confirm reliability.']}
    write('results.json',output);return output

def prepare():
    b=json.loads((OUT/'business_private.json').read_text(encoding='utf-8'));f=json.loads((OUT/'sales_facts_private.json').read_text(encoding='utf-8'))
    frame,audit=dataset(b,f);frame.to_csv(OUT/'labelled_quotes_private.csv',index=False)
    train,valid,test,split=partition(frame)
    detail={'audit':audit,'split':split,'samples':{name:{'rows':len(d),'customers':d.customer_group.nunique(),'from':str(d.date.min().date()),'to':str(d.date.max().date())} for name,d in [('train',train),('validation',valid),('test',test)]}}
    write('feasibility.json',detail);return frame,detail

if __name__=='__main__':
    import sys
    frame,detail=prepare();print(json.dumps(detail,indent=2),flush=True)
    if '--train' in sys.argv:print(json.dumps(study(frame),indent=2))
