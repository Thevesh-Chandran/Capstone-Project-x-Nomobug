"""Chronological calibration study for the main pest-return model; never deploys.

Uses saved out-of-fold scores, outcome maturity and property-group separation.
Q3 selects calibration/threshold; Q4 is a separately reported historical check.
The repeatedly inspected Q4 period is not an untouched final test.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss,average_precision_score,roc_auc_score,confusion_matrix

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261028_probability_calibration'
SOURCE=ROOT/'outputs/cp2-v2/model_corrected_v5/selected_ap/development_predictions.csv'

def design(probability,method):
    p=np.clip(np.asarray(probability,dtype=float),1e-6,1-1e-6)
    if method=='sigmoid':return p.reshape(-1,1)
    if method=='logit':return np.log(p/(1-p)).reshape(-1,1)
    if method=='beta':return np.column_stack([np.log(p),-np.log1p(-p)])
    raise ValueError('Unknown calibration design')

def calibrate(train,score,method):
    p=score.raw_probability.to_numpy()
    if method=='raw':return p
    y=train.warranty_signal_within_30d.astype(int)
    if method=='isotonic':
        return IsotonicRegression(out_of_bounds='clip',y_min=0,y_max=1).fit(train.raw_probability,y).predict(p)
    model=LogisticRegression(C=1,solver='lbfgs',max_iter=2000,random_state=42)
    model.fit(design(train.raw_probability,method),y)
    return model.predict_proba(design(p,method))[:,1]

def mature_training(frame,cutoff,assessment):
    train=frame[frame.outcome_end_date<pd.Timestamp(cutoff)].copy()
    train=train[~train.validation_group.isin(assessment.validation_group)]
    assert train.outcome_end_date.max()<pd.Timestamp(cutoff)
    assert set(train.validation_group).isdisjoint(assessment.validation_group)
    assert train.warranty_signal_within_30d.nunique()==2
    return train

def metrics(data,probability,threshold):
    y=data.warranty_signal_within_30d.astype(int).to_numpy();pred=probability>=threshold
    tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    precision=tp/(tp+fp) if tp+fp else 0.;recall=tp/(tp+fn) if tp+fn else 0.
    return {'services':len(y),'positive_windows':int(y.sum()),'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),
        'threshold':float(threshold),'accuracy':float((pred==y).mean()),'precision':float(precision),
        'recall':float(recall),'f1':float(2*precision*recall/(precision+recall)) if precision+recall else 0.,
        'brier':float(brier_score_loss(y,probability)),'average_precision':float(average_precision_score(y,probability)),
        'roc_auc':float(roc_auc_score(y,probability)),'always_no_accuracy':float((y==0).mean())}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    assert not (OUT/'protocol.json').exists(),'Do not overwrite the declared experiment'
    raw=SOURCE.read_bytes();f=pd.read_csv(SOURCE)
    for col in ['anchor_date','outcome_end_date']:f[col]=pd.to_datetime(f[col])
    validation=f[f.fold=='2025_q3'].copy();assessment=f[f.fold=='2025_q4'].copy()
    initial=mature_training(f,'2025-07-01',validation)
    final=mature_training(f,'2025-10-01',assessment)
    protected={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'config/cp2_model_current.json',ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json',ROOT/'outputs/cp2-v2/prospective_callback_v2/challenger_all_history.joblib']}
    protocol={'declared_at_utc':datetime.now(timezone.utc).isoformat(),'source':str(SOURCE.relative_to(ROOT)),
        'source_sha256':hashlib.sha256(raw).hexdigest(),'methods':['raw','sigmoid','logit','beta','isotonic'],
        'validation':'2025 Q3 saved OOF; calibration training outcomes before July1; property groups purged',
        'assessment':'2025 Q4 saved OOF; refit calibration on matured earlier outcomes before October1; property groups purged',
        'selection':'Lowest Q3 Brier score; choose Q3 threshold maximizing F1 among recall>=0.30 and >=10 alerts; ties higher precision then higher threshold',
        'thresholds':[float(t) for t in np.arange(.02,.501,.01)],'protected':protected,
        'limitations':'Historical OOF scores and repeatedly inspected periods. Not a new final independent test or a refit of forest weights.'}
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    results=[]
    for method in protocol['methods']:
        p=calibrate(initial,validation,method)
        grid=[metrics(validation,p,t) for t in protocol['thresholds']]
        feasible=[r for r in grid if r['recall']>=.3 and r['TP']+r['FP']>=10]
        if not feasible:raise ValueError('No predeclared feasible threshold')
        chosen=max(feasible,key=lambda r:(r['f1'],r['precision'],r['threshold']))
        results.append({'method':method,**chosen})
    choice=min(results,key=lambda r:(r['brier'],r['method']))
    (OUT/'validation_selection.json').write_text(json.dumps({'selected':choice,'all_methods':results},indent=2))
    # Assessment begins only after the method and threshold have been saved.
    selected_p=calibrate(final,assessment,choice['method'])
    raw_choice=next(r for r in results if r['method']=='raw')
    baseline=metrics(assessment,assessment.raw_probability.to_numpy(),raw_choice['threshold'])
    selected=metrics(assessment,selected_p,choice['threshold'])
    # Reject promotion when calibration or either principal classification measure worsens.
    qualified=(selected['brier']<baseline['brier'] and selected['precision']>baseline['precision'] and selected['recall']>=baseline['recall'] and selected['accuracy']>=baseline['accuracy'])
    summary={'calibration_training_services':len(initial),'validation_services':len(validation),
        'assessment_calibration_training_services':len(final),'assessment_services':len(assessment),
        'selected_method':choice['method'],'raw_reference':baseline,'calibrated_candidate':selected,
        'passed_exploratory_gate':bool(qualified),'deployed':False}
    (OUT/'results.json').write_text(json.dumps(summary,indent=2))
    pd.DataFrame(results).to_csv(OUT/'validation_metrics.csv',index=False)
    pd.DataFrame([{'Configuration':'Raw scores; validation threshold',**baseline},{'Configuration':choice['method']+' calibration; validation threshold',**selected}]).to_csv(OUT/'assessment_metrics.csv',index=False)
    for path,digest in protected.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
