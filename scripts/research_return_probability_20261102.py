"""Historical probability calibration comparison; leaves the frozen bundle unchanged."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import joblib,numpy as np,pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss,log_loss,average_precision_score,roc_auc_score
from threadpoolctl import threadpool_limits
from scripts import benchmark_warranty_models as b, compare_callback_candidates_v2 as c
from scripts.evaluate_larger_frozen_model import make_partitions
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/model_validation/20261102_return_probability'
def save(name,x):(OUT/name).write_text(json.dumps(x,indent=2,default=str),encoding='utf-8')
def design(p,method):
 p=np.clip(p,1e-6,1-1e-6)
 if method=='sigmoid':return p.reshape(-1,1)
 if method=='logit':return np.log(p/(1-p)).reshape(-1,1)
 return np.column_stack([np.log(p),-np.log1p(-p)])
def fit(method,p,y):
 if method=='raw':return None
 if method=='isotonic':return IsotonicRegression(out_of_bounds='clip').fit(p,y)
 return LogisticRegression(C=1,max_iter=3000,random_state=42).fit(design(p,method),y)
def apply(method,m,p):
 if method=='raw':return p
 if method=='isotonic':return np.clip(m.predict(p),1e-6,1-1e-6)
 return m.predict_proba(design(p,method))[:,1]
def metrics(y,p):return {'services':len(y),'positives':int(np.sum(y)),'brier':float(brier_score_loss(y,p)),'log_loss':float(log_loss(y,np.clip(p,1e-6,1-1e-6),labels=[0,1])),'auc':float(roc_auc_score(y,p)),'average_precision':float(average_precision_score(y,p)),'mean_predicted_risk':float(np.mean(p)),'actual_rate':float(np.mean(y))}
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 if (OUT/'protocol.json').exists():raise ValueError('Preserve completed study')
 old=ROOT/'outputs/model_validation/20261017_larger_frozen_test';pr=json.loads((old/'protocol.json').read_text());src=ROOT/pr['source_path'];assert hashlib.sha256(src.read_bytes()).hexdigest()==pr['source_sha256']
 f=c.prepare_input(b.load_dataset_input(src));tr,va,te=make_partitions(f)
 select=va[va.anchor_date.ge('2025-10-01')].copy();cal=va[va.outcome_end_date.lt('2025-10-01') & ~va.validation_group.isin(select.validation_group)].copy()
 assert set(cal.validation_group).isdisjoint(select.validation_group) and cal.outcome_end_date.max()<select.anchor_date.min()
 assert cal[b.TARGET].nunique()==select[b.TARGET].nunique()==2
 m=joblib.load(old/'larger_historical_model.joblib');cols=m['features'];protected={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'outputs/cp2-v2/prospective_callback_v2').iterdir() if p.is_file()}
 save('protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':pr['source_sha256'],'classifier':'Fixed larger historical 93-input Extra Trees classifier; fitted on 1,506 training rows only','calibration_fit':'Earlier validation rows with outcomes before 1 Oct 2025; groups overlapping method-selection rows removed','method_selection':'Later validation rows Oct-Nov 2025; choose lowest Brier, then log loss; classifier and calibrator not refit after selection','assessment':'Same previously examined 2026 assessment; no independent prospective result','methods':['raw','sigmoid','logit','beta','isotonic'],'target':'Recorded corrective Calendar return within 30 days; not verified biological recurrence or formal warranty entitlement','protected_hashes':protected,'partition_counts':{'classifier_training':len(tr),'calibration_fit':len(cal),'method_validation':len(select),'assessment':len(te)},'partition_positives':{'classifier_training':int(tr[b.TARGET].sum()),'calibration_fit':int(cal[b.TARGET].sum()),'method_validation':int(select[b.TARGET].sum()),'assessment':int(te[b.TARGET].sum())}})
 with threadpool_limits(limits=2):
  pc=m['pipeline'].predict_proba(cal[cols])[:,1];pv=m['pipeline'].predict_proba(select[cols])[:,1]
 methods={};validation=[]
 for method in ['raw','sigmoid','logit','beta','isotonic']:
  obj=fit(method,pc,cal[b.TARGET]);methods[method]=obj;validation.append({'method':method,**metrics(select[b.TARGET],apply(method,obj,pv))})
 chosen=min(validation,key=lambda r:(r['brier'],r['log_loss'],r['method']))['method']
 save('validation_selection.json',{'selected':chosen,'candidates':validation});joblib.dump({'method':chosen,'calibrator':methods[chosen]},OUT/'probability_candidate.joblib')
 with threadpool_limits(limits=2):pt=m['pipeline'].predict_proba(te[cols])[:,1]
 p=apply(chosen,methods[chosen],pt);ref=b.apply_calibrator(m['calibrator'],pt)
 base=np.repeat(cal[b.TARGET].mean(),len(te));records=[{'model':'Uncalibrated forest',**metrics(te[b.TARGET],pt)},{'model':'Existing larger-study calibration',**metrics(te[b.TARGET],ref)},{'model':'New validation-selected '+chosen,**metrics(te[b.TARGET],p)},{'model':'Constant earlier return rate',**metrics(te[b.TARGET],base)}]
 bins=[]
 for name,pred in [('Existing calibration',ref),('New probability candidate',p)]:
  for lo,hi in zip([0,.05,.1,.2,.3,.5],[.05,.1,.2,.3,.5,1.000001]):
   mask=(pred>=lo)&(pred<hi)
   if mask.any():bins.append({'model':name,'risk_band':f'{lo:.0%}–{min(hi,1):.0%}','services':int(mask.sum()),'positive_windows':int(te[b.TARGET].to_numpy()[mask].sum()),'predicted':float(pred[mask].mean()),'observed':float(te[b.TARGET].to_numpy()[mask].mean())})
 pd.DataFrame(records).to_csv(OUT/'probability_metrics.csv',index=False);pd.DataFrame(bins).to_csv(OUT/'risk_bands.csv',index=False)
 # Test comparisons are descriptive; no further model selection follows.
 save('results.json',{'selected_using_validation':chosen,'metrics':records,'bands':bins,'deployed':False,'candidate_brier_better_than_existing':records[2]['brier']<records[1]['brier'],'candidate_brier_better_than_constant':records[2]['brier']<records[3]['brier'],'limitation':'Already examined historical assessment; 100-service and Claude results are separate populations.'})
 assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in protected.items())
 print(json.dumps({'selected':chosen,'partitions':{'train':len(tr),'calibration':len(cal),'selection':len(select),'assessment':len(te)},'metrics':records},indent=2))
if __name__=='__main__':main()
