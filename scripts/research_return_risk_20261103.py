"""Return-visit risk score study, 3 November 2026.

Question: after a recorded paid service, will the same sale record a corrective return (warranty-signal) visit within 30 days?
Data: sale-linked service anchors with matured 30-day labels (outputs/project_audit/20261101_outcome_repair/features/mature_labels/dataset_input.json).
Protocol (fixed before fitting):
  development  anchors to 2025-09-30
  validation   2025-11-01 to 2026-03-31  (feature set and regularisation chosen here, by average precision)
  test         2026-05-01 onwards, scored once after the model was frozen
  30-day gaps between partitions, sale groups disjoint, final model refitted on development+validation only.
Comparisons on identical test services: random order, the business rule "final residential service", and a random forest on all inputs.
The original frozen pest-return experiment and its receipts are not touched.

  python scripts/research_return_risk_20261103.py --data <dataset_input.json> --out outputs/model_validation/20261103_return_risk
"""
import argparse,os,sys
ap=argparse.ArgumentParser();ap.add_argument('--data',required=True);ap.add_argument('--out',required=True);A=ap.parse_args()
DATA=os.path.abspath(A.data);os.makedirs(A.out,exist_ok=True)
if os.path.exists(os.path.join(A.out,'return_risk_v1.json')):raise SystemExit('Completed study exists; never overwrite it')
os.chdir(A.out)
import json,pandas as pd,numpy as np
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
# selection on validation only
rows=[]
for name,cols in CAND.items():
    for C in [0.03,0.1,0.3,1.0]:
        m=fit(cols,C,dev);p=m.predict_proba(F.loc[val,cols])[:,1];yv=y[val]
        rows.append({'set':name,'C':C,'val_auc':roc_auc_score(yv,p),'val_ap':average_precision_score(yv,p),'val_cap20':cap(yv,p,.2)[0]})
sel=pd.DataFrame(rows).sort_values(['val_ap','val_auc'],ascending=False);print(sel.round(3).head(10).to_string(index=False))
best=sel.iloc[0];json.dump({'chosen_set':best['set'],'C':float(best['C']),'chosen_by':'highest validation average precision','validation_table':rows},open('selection.json','w'),indent=1)
print('CHOSEN',best['set'],best['C'])
sel=json.load(open('selection.json'));cols=CAND[sel['chosen_set']];C=sel['C']
fitmask=(dev|val)
assert df.outcome_end_date[fitmask].max()<pd.Timestamp('2026-05-01')
m=fit(cols,C,fitmask)
# freeze before test
coef=dict(zip(cols,m[-1].coef_[0]));frozen={'features':cols,'C':C,'scaler_mean':m[0].mean_.tolist(),'scaler_scale':m[0].scale_.tolist(),'coef':m[-1].coef_[0].tolist(),'intercept':float(m[-1].intercept_[0]),'fit_rows':int(fitmask.sum()),'fit_positives':int(y[fitmask].sum()),'fit_period':'2024-03-08 to 2026-03-31 (development + validation, sale groups disjoint from test)','frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),'source_sha256':hashlib.sha256(open(DATA,'rb').read()).hexdigest()}
open('return_risk_v1.json','w').write(json.dumps(frozen,indent=1))
# comparison models fit on the same rows, no tuning
rf=make_pipeline(SimpleImputer(),RandomForestClassifier(400,min_samples_leaf=10,max_features=.3,class_weight='balanced_subsample',n_jobs=-1,random_state=0))
allnum=[c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c not in (Y,'warranty_claim_count_30d','anchor_event_row')]
rf.fit(df.loc[fitmask,allnum],y[fitmask])
yt=y[test];T=df[test]
P={'Random order':np.random.RandomState(0).rand(test.sum()),'Rule: final residential service':df.res_final[test].values+np.random.RandomState(1).rand(test.sum())*1e-3,
   'Complex model (random forest, all inputs)':rf.predict_proba(df.loc[test,allnum])[:,1],'Return-risk score (chosen)':m.predict_proba(F.loc[test,cols])[:,1]}
res={}
for k,p in P.items():
    r={'auc':roc_auc_score(yt,p),'ap':average_precision_score(yt,p)}
    for f in (.1,.2,.3):c,pr=cap(yt,p,f);r[f'capture_{int(f*100)}']=c;r[f'precision_{int(f*100)}']=pr
    res[k]=r
out=pd.DataFrame(res).T;print('TEST',test.sum(),'services',yt.sum(),'returns base',round(yt.mean(),3));print(out.round(3).to_string())
p=P['Return-risk score (chosen)']
print('brier model',round(brier_score_loss(yt,p),4),'constant',round(brier_score_loss(yt,np.full_like(p,y[fitmask].mean())),4))
dec=pd.qcut(p,5,labels=False,duplicates='drop');cal=pd.DataFrame({'band':dec,'p':p,'y':yt}).groupby('band').agg(services=('y','size'),predicted=('p','mean'),actual=('y','mean'));print(cal.round(3))
mon=pd.DataFrame({'m':T.anchor_date.dt.to_period('M').astype(str).values,'p':p,'y':yt}).groupby('m').agg(services=('y','size'),expected=('p','sum'),actual=('y','sum'));print(mon.round(1))
# untouched slice: anchors after 2026-08-27 (not examined by earlier studies)
u=(T.anchor_date>'2026-08-27').values
if u.sum() and 0<yt[u].sum()<u.sum():print('UNTOUCHED slice',u.sum(),'services',yt[u].sum(),'returns auc',round(roc_auc_score(yt[u],p[u]),3),'rule auc',round(roc_auc_score(yt[u],P['Rule: final residential service'][u]),3),'cap20',cap(yt[u],p[u],.2))
# bootstrap by sale group: capture20 model - rule
gr=T.sales_record_id.values;ug=np.unique(gr);rs=np.random.RandomState(7);diffs=[];aucs=[]
idx={k:np.where(gr==k)[0] for k in ug}
for _ in range(500):
    s=np.concatenate([idx[k] for k in rs.choice(ug,len(ug))]);yy=yt[s]
    if yy.sum()==0:continue
    diffs.append(cap(yy,p[s],.2)[0]-cap(yy,P['Rule: final residential service'][s],.2)[0]);aucs.append(roc_auc_score(yy,p[s]))
print('capture20 gain vs rule 95% CI',np.percentile(diffs,[2.5,50,97.5]).round(3),'AUC CI',np.percentile(aucs,[2.5,97.5]).round(3))
pts=pd.Series(coef).sort_values();print((pts/ m[0].scale_[[cols.index(c) for c in pts.index]]).round(3).to_string())
json.dump({'test':{k:{kk:float(vv) for kk,vv in v.items()} for k,v in res.items()},'test_services':int(test.sum()),'test_returns':int(yt.sum()),'calibration':cal.reset_index().to_dict('records'),'monthly':mon.reset_index().to_dict('records'),'gain_ci':np.percentile(diffs,[2.5,50,97.5]).tolist(),'auc_ci':np.percentile(aucs,[2.5,97.5]).tolist()},open('test_results.json','w'),indent=1,default=float)
# capture curve and plain-language factors for the report and portal page
curve={k:[round(cap(yt,v,f/100)[0],4) for f in range(0,101,5) if f>0] for k,v in P.items()}
unit=pd.Series(m[-1].coef_[0]/m[0].scale_,index=cols)
R=json.load(open('test_results.json'));R['capture_curve']={'review_share_pct':list(range(5,101,5)),**curve};R['per_unit_log_odds']=unit.round(4).to_dict()
R['base_rates']={'all_services':float(df[Y].mean()),'final_residential':float(df[Y][df.res_final==1].mean()),'first_service':float(df[Y][df.service_number==1].mean())}
json.dump(R,open('test_results.json','w'),indent=1,default=float)
print('saved capture curve')
