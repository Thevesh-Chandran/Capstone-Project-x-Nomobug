"""Exploratory challenger check for return_risk_v1, 4 November 2026.

Fits challengers on development data and compares them on the validation months only (the test months were
already used once). Also checks whether an intercept shift fitted on validation fixes the total-count
undercount, and the frozen model's ranking (AUC) by test month. Changes no frozen model or receipt.

  python scripts/check_return_risk_challengers_20261104.py <mature_labels dataset_input.json>
"""
import json,pandas as pd,numpy as np,sys
DATA=sys.argv[1]
Y='warranty_signal_within_30d'
def load():
    v=json.load(open(DATA));df=pd.DataFrame(v['records'],columns=v['columns'])
    for c in ['anchor_date','outcome_end_date','observed_through']:df[c]=pd.to_datetime(df[c])
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_datetime64_any_dtype(df[c]) and c not in ('address_hash','sales_record_id','package_category','pest_category','premise_type','calendar_pest_text_category','calendar_service_method_category','label_evidence','population','prediction_time_definition','environment_feature_scope','environment_feature_source','weather_location_id','anchor_event_row','event_date_local','latest_weather_date_used'):
            df[c]=pd.to_numeric(df[c],errors='coerce')
    df['final']=(df.service_number>=df.package_sessions_recorded).astype(int)
    df['res']=(df.premise_type=='RESIDENTIAL').astype(int)
    df['res_final']=df.res*df.final
    df[Y]=df[Y].astype(int)
    return df

import hashlib,datetime

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
import warnings;warnings.filterwarnings('ignore')
df=load()
def feats(df):
    F=pd.DataFrame(index=df.index)
    F['final_residential']=df.res_final
    F['final_service']=df.final
    F['residential']=df.res
    F['three_service_programme']=(df.package_sessions_recorded==3).astype(float)
    F['first_service']=(df.service_number==1).astype(float)
    F['log_sale_rm']=np.log1p(df.sale_total_rm.fillna(0))
    d=df.days_since_previous_service
    F['gap_missing']=d.isna().astype(float);F['gap_days_capped']=d.fillna(0).clip(0,120)
    F['property_past_claims']=df.prior_property_warranty_claims.fillna(0).clip(0,4)
    F['programme_past_claims']=df.prior_package_warranty_claims.fillna(0).clip(0,3)
    F['property_claims_90d']=df.prior_property_claims_90d.fillna(0).clip(0,3)
    F['area_claim_rate_90d']=(df.prior_area_claims_90d/(df.prior_area_services_90d.replace(0,np.nan))).fillna(0).clip(0,1)
    F['area_services_90d']=np.log1p(df.prior_area_services_90d.fillna(0))
    F['rain_30d_mm']=df.prior_30d_precipitation_mm.fillna(df.prior_30d_precipitation_mm.median())
    F['humidity_30d']=df.prior_30d_relative_humidity_mean_pct.fillna(df.prior_30d_relative_humidity_mean_pct.median())
    F['month_sin']=df.anchor_month_sin;F['month_cos']=df.anchor_month_cos
    pc=df.pest_category.fillna('').str.lower()
    F['cockroach_only']=(pc.str.strip().isin(['lipas']) ).astype(float)
    F['includes_rodent']=pc.str.contains('tikus').astype(float)
    return F
F=feats(df)
SETS={'structure':['final_residential','final_service','residential','three_service_programme','first_service'],
 'history':['property_past_claims','programme_past_claims','property_claims_90d','gap_missing','gap_days_capped','log_sale_rm'],
 'context':['area_claim_rate_90d','area_services_90d','rain_30d_mm','humidity_30d','month_sin','month_cos'],
 'pest':['cockroach_only','includes_rodent']}
CAND={'S1 structure':SETS['structure'],'S2 +history':SETS['structure']+SETS['history'],'S3 +context':SETS['structure']+SETS['history']+SETS['context'],'S4 +pest':SETS['structure']+SETS['history']+SETS['context']+SETS['pest'],'S5 structure+history+pest':SETS['structure']+SETS['history']+SETS['pest']}
# partitions: fixed dates, 30-day gaps, sale groups disjoint
dev=df.anchor_date<='2025-09-30';val=(df.anchor_date>='2025-11-01')&(df.anchor_date<='2026-03-31');test=df.anchor_date>='2026-05-01'
g=df.sales_record_id;dev=dev&~g.isin(g[val|test]);val=val&~g.isin(g[test])
assert df.outcome_end_date[dev].max()<pd.Timestamp('2025-11-01') and df.outcome_end_date[val].max()<pd.Timestamp('2026-05-01')
y=df[Y].values
def cap(yy,p,f):k=max(1,int(round(len(p)*f)));i=np.argsort(-p,kind='stable')[:k];return float(yy[i].sum()/yy.sum()),float(yy[i].mean())
def fit(cols,C,mask):
    m=make_pipeline(StandardScaler(),LogisticRegression(C=C,max_iter=5000));m.fit(F.loc[mask,cols],y[mask]);return m

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import PolynomialFeatures
from sklearn.calibration import CalibratedClassifierCV
S5=CAND['S5 structure+history+pest']
def ev(name,p,mask):
    yy=y[mask];return {'model':name,'auc':round(roc_auc_score(yy,p),3),'ap':round(average_precision_score(yy,p),3),'cap20':round(cap(yy,p,.2)[0],3),'expected_vs_actual':round(p.sum()/yy.sum(),3)}
out=[]
# 1. chosen design refit on dev, scored on validation (reference)
m=fit(S5,0.03,dev);out.append(ev('Logistic (chosen design)',m.predict_proba(F.loc[val,S5])[:,1],val))
# 2. gradient boosting, small and regularised
for lr,leaf in [(0.05,40),(0.03,80)]:
    hb=HistGradientBoostingClassifier(learning_rate=lr,max_iter=300,min_samples_leaf=leaf,max_depth=3,l2_regularization=1.0,random_state=0)
    hb.fit(F.loc[dev,S5],y[dev]);out.append(ev(f'Gradient boosting lr={lr} leaf={leaf}',hb.predict_proba(F.loc[val,S5])[:,1],val))
# 3. logistic with pairwise interactions
pi=make_pipeline(StandardScaler(),PolynomialFeatures(2,interaction_only=True,include_bias=False),StandardScaler(),LogisticRegression(C=0.01,max_iter=5000))
pi.fit(F.loc[dev,S5],y[dev]);out.append(ev('Logistic + interactions',pi.predict_proba(F.loc[val,S5])[:,1],val))
# 4. all candidate features incl. context with gradient boosting
allf=list(F.columns)
hb2=HistGradientBoostingClassifier(learning_rate=0.03,max_iter=300,min_samples_leaf=80,max_depth=3,l2_regularization=1.0,random_state=0)
hb2.fit(F.loc[dev,allf],y[dev]);out.append(ev('Gradient boosting, all inputs incl. weather/area',hb2.predict_proba(F.loc[val,allf])[:,1],val))
print(pd.DataFrame(out).to_string(index=False))
# 5. recalibration: does an intercept shift fit on validation fix the total on test? (diagnostic only)
fm=(dev|val);m2=fit(S5,0.03,fm);pt=m2.predict_proba(F.loc[test,S5])[:,1];yt=y[test]
pv=fit(S5,0.03,dev).predict_proba(F.loc[val,S5])[:,1];yv=y[val]
from scipy.optimize import brentq
lo=lambda p:np.log(p/(1-p));sig=lambda z:1/(1+np.exp(-z))
shift=brentq(lambda s:sig(lo(pv)+s).sum()-yv.sum(),-3,3)
print('val expected/actual before',round(pv.sum()/yv.sum(),3),'shift',round(shift,3))
print('test expected/actual: frozen',round(pt.sum()/yt.sum(),3),'after shift',round(sig(lo(pt)+shift).sum()/yt.sum(),3))
# 6. recent months: model on test by quarter
T=df[test].copy();T['p']=pt
T['q']=T.anchor_date.dt.to_period('M')
print(T.groupby('q').apply(lambda g:pd.Series({'n':len(g),'returns':int(g[Y].sum()),'auc':round(roc_auc_score(g[Y],g.p),3) if 0<g[Y].sum()<len(g) else None})).to_string())
