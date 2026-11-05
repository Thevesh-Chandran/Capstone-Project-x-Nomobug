"""Historical pest-specialist comparison; original frozen experiment unchanged."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
import joblib
import pandas as pd,numpy as np
from sklearn.base import clone
from threadpoolctl import threadpool_limits
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.evaluate_larger_frozen_model import make_partitions
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261102_pest_specialists'
def save(name,value):(OUT/name).write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')
def masks(f):
 p=f.normalized_pest_category.fillna('UNSPECIFIED')
 out={'All pests':pd.Series(True,index=f.index),'Mixed pests':p.str.contains('|',regex=False),'Other than cockroach-only':p.ne('COCKROACH')}
 for pest in ['COCKROACH','ANT','RODENT','TERMITE','BED_BUG','FLY','MOSQUITO']:
  out[pest+' only']=p.eq(pest)
  out[pest+' including mixed']=p.str.split('|').apply(lambda xs:pest in xs)
 return out
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 if (OUT/'protocol.json').exists():raise ValueError('Preserve prior study')
 proto=json.loads((ROOT/'outputs/model_validation/20261017_larger_frozen_test/protocol.json').read_text())
 src=ROOT/proto['source_path'];assert hashlib.sha256(src.read_bytes()).hexdigest()==proto['source_sha256']
 baseline_path=ROOT/'outputs/model_validation/20261017_larger_frozen_test/larger_historical_model.joblib'
 model=joblib.load(baseline_path);cols=model['features'];frame=c.prepare_input(b.load_dataset_input(src));tr,va,te=make_partitions(frame)
 protected={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'outputs/cp2-v2/prospective_callback_v2').iterdir() if p.is_file()}
 save('protocol.json',{'declared_at':datetime.now(timezone.utc).isoformat(),'source_sha256':proto['source_sha256'],'partitions':[len(tr),len(va),len(te)],'target':'Any qualifying recorded corrective return within 30 days after service; group defined by anchor-service pest, not proof of pest-specific recurrence','settings':'Clone original 93-input Extra Trees pipeline; fit on earlier training subset; calibration and F1 threshold only on corresponding validation subset','minimum_support':{'train_rows':100,'train_positive':10,'validation_rows':50,'validation_positive':5},'assessment':'Previously explored historical period; no independent confirmation or deployment; no winner selected using test results','protected_hashes':protected})
 tm,vm,em=masks(tr),masks(va),masks(te);support=[];baseline=[];special=[]
 with threadpool_limits(limits=2):basep=b.apply_calibrator(model['calibrator'],model['pipeline'].predict_proba(te[cols])[:,1])
 for name in tm:
  a,z,t=tr[tm[name]],va[vm[name]],te[em[name]]
  support.append({'pest_group':name,'train':len(a),'train_positive':int(a[b.TARGET].sum()),'validation':len(z),'validation_positive':int(z[b.TARGET].sum()),'assessment':len(t),'assessment_positive':int(t[b.TARGET].sum())})
  if len(t):baseline.append({'pest_group':name,**b.score(t[b.TARGET],basep[em[name]],model['threshold']),'always_negative_accuracy':float(1-t[b.TARGET].mean())})
  if name=='All pests' or min(len(a),len(z))==0:continue
  if len(a)<100 or a[b.TARGET].sum()<10 or len(z)<50 or z[b.TARGET].sum()<5:continue
  pipe=clone(model['pipeline']);pipe.named_steps['classifier'].set_params(n_jobs=2)
  with threadpool_limits(limits=2):
   pipe.fit(a[cols],a[b.TARGET],classifier__sample_weight=np.ones(len(a)))
   raw=pipe.predict_proba(z[cols])[:,1];cal,_=b.fit_calibrator(z[b.TARGET],raw);q=b.apply_calibrator(cal,raw);cut=b.select_threshold(z[b.TARGET],q)
  # Save model and validation decisions before evaluating the historical assessment.
  safe=name.lower().replace(' ','_');joblib.dump({'pipeline':pipe,'features':cols,'calibrator':cal,'threshold':cut},OUT/(safe+'.joblib'))
  save(safe+'_validation.json',{'threshold':cut,'metrics':b.score(z[b.TARGET],q,cut),'model_sha256':hashlib.sha256((OUT/(safe+'.joblib')).read_bytes()).hexdigest()})
  with threadpool_limits(limits=2):p=b.apply_calibrator(cal,pipe.predict_proba(t[cols])[:,1])
  special.append({'pest_group':name,'threshold':cut,**b.score(t[b.TARGET],p,cut),'always_negative_accuracy':float(1-t[b.TARGET].mean())})
 assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in protected.items())
 save('results.json',{'support':support,'existing_general_model_by_pest':baseline,'separate_specialists':special,'original_frozen_unchanged':True})
 for name,rows in [('support',support),('general_by_pest',baseline),('specialists',special)]:pd.DataFrame(rows).to_csv(OUT/(name+'.csv'),index=False)
 print(json.dumps({'support':support,'specialists':special,'general_cockroach':[r for r in baseline if r['pest_group'] in ['COCKROACH only','COCKROACH including mixed','All pests']]},indent=2))
if __name__=='__main__':main()
