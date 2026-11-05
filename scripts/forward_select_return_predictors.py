"""Greedy one-variable-at-a-time selection, separated from later assessment."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from threadpoolctl import threadpool_limits
from scripts import benchmark_warranty_models as b, compare_callback_candidates_v2 as c
from scripts import research_callback_targets as r

OUT=b.ROOT/'outputs/model_validation/20261017_forward_selection_v2'
SOURCE=b.ROOT/'outputs/model_validation/20261017_before_first_weather/experiment_rows_private.pkl'
CATEGORICAL=list(dict.fromkeys(list(b.CATEGORICAL)+['normalized_pest_category']))


def pipeline(columns):
    numeric=[x for x in columns if x not in CATEGORICAL]
    categorical=[x for x in columns if x in CATEGORICAL]
    pipe=c.make_pipeline('et10_leaf5',numeric)
    pipe.named_steps['classifier'].set_params(n_jobs=1)
    pipe.named_steps['preprocess'].transformers=[(name,transform,categorical if name=='categorical' else cols)
        for name,transform,cols in pipe.named_steps['preprocess'].transformers]
    return pipe


def evaluate(columns, partitions):
    rows=[]
    for name,fit,cal,test in partitions:
        if columns:
            pipe=pipeline(columns)
            pipe.fit(fit[columns],fit[b.TARGET])
            raw=pipe.predict_proba(cal[columns])[:,1]
            calibrator,cal_audit=b.fit_calibrator(cal[b.TARGET],raw)
            probability=b.apply_calibrator(calibrator,pipe.predict_proba(test[columns])[:,1])
            threshold=b.select_threshold(cal[b.TARGET],b.apply_calibrator(calibrator,raw))
        else:
            prior=float(fit[b.TARGET].mean());probability=np.full(len(test),prior)
            threshold=b.select_threshold(cal[b.TARGET],np.full(len(cal),prior));cal_audit={'method':'constant_training_prior'}
        tn,fp,fn,tp=confusion_matrix(test[b.TARGET],probability>=threshold,labels=[False,True]).ravel()
        rows.append({'fold':name,**b.score(test[b.TARGET],probability,threshold),
          'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),'calibration':cal_audit})
    return {'mean_f1':float(np.mean([x['f1'] for x in rows])),
      'mean_brier':float(np.mean([x['brier_score'] for x in rows])),
      'mean_ap':float(np.mean([x['average_precision'] for x in rows])),'folds':rows}


def acceptable(previous,candidate):
    return candidate['mean_f1']>=previous['mean_f1']+.005 and all(
        n['f1']>=p['f1']-.02 for p,n in zip(previous['folds'],candidate['folds']))


def partitions(data,folds):
    output=[];audits=[]
    for name,start,end in folds:
        train,test,outer=r.b.purged_split(data,start,end)
        fit,cal,inner=r.calibration_split(train)
        if len(test)<50 or test[b.TARGET].sum()<5:raise ValueError('Insufficient assessment support')
        output.append((name,fit,cal,test));audits.append({'fold':name,'fit':len(fit),'calibration':len(cal),'validation':len(test),'positives':int(test[b.TARGET].sum()),'outer':outer,'inner':inner})
    return output,audits


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'protocol.json').exists():raise ValueError('Preserve declared experiment')
    data=pd.read_pickle(SOURCE)
    frozen=b.ROOT/'outputs/cp2-v2/prospective_callback_v2'
    before={x.name:r.digest(x) for x in frozen.iterdir() if x.is_file()}
    bundle=json.loads((frozen/'bundle.json').read_text())
    original=bundle['models']['challenger_all_history']['features']
    extra=[x for x in data if x.startswith(('first_to_second_','second_to_third_','before_first_'))]
    pool=list(dict.fromkeys(original+extra))
    assert all(x in data for x in pool)
    selection_folds=[['2025_q3','2025-07-01','2025-10-01'],['2025_q4','2025-10-01','2026-01-01']]
    later_folds=[['2026_q1','2026-01-01','2026-04-01'],['2026_q2_summer','2026-04-01','2026-08-15']]
    # Feature filtering uses selection-era data only, never the later assessment.
    selection_data=data[data.anchor_date<pd.Timestamp('2026-01-01')]
    constants=[x for x in pool if selection_data[x].nunique(dropna=False)<=1]
    candidates=[x for x in pool if x not in constants]
    parts,audits=partitions(data,selection_folds)
    protocol={'declared_at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':r.digest(SOURCE),
      'code_sha256':r.digest(__file__),'frozen_hashes':before,'original_input_count':len(original),
      'all_candidates':pool,'selection_era_constant_inputs_excluded':constants,'eligible_candidates':candidates,
      'categorical_fields':CATEGORICAL,
      'selection_folds':selection_folds,'later_assessment_folds':later_folds,'selection_split_audits':audits,
      'model':'ExtraTrees 300 trees, depth 10, minimum leaf 5, balanced classes, seed 42, one thread per fit',
      'rules':['Start with best single variable; at each later step test adding every remaining variable to the accepted set.',
        'Choose highest mean F1 across the two earlier periods; ties lower mean Brier then field name.',
        'Accept subsequent addition only for mean F1 improvement >=0.005 and neither period losing >0.02 F1.',
        'Stop when no acceptable addition remains, or at 20 accepted variables; report cap if reached.',
        'Always add best single variable for a readable path, but label if it fails to beat the constant baseline.',
        'Separate earlier purged fit/calibration subsets within each selection fold; threshold maximizes calibration F1 only.',
        'Once path fixed, assess baseline, selected set and full pool on later periods; never use those results to choose path.',
        'All dates and weather eligibility inherited from prior 3x experiment; same rows throughout.',
        'Later historical periods were inspected in prior experiments: this is development evidence, not a fresh independent test.',
        'Input variables, not learned tree parameters; no production replacement or prospective backfill.']}
    r.write(OUT/'protocol.json',protocol)
    with threadpool_limits(limits=1):
        baseline=evaluate([],parts);selected=[];path=[];current=baseline;reason=''
        with ThreadPoolExecutor(max_workers=2) as executor:
            while len(selected)<20:
                remaining=[x for x in candidates if x not in selected]
                if not remaining:reason='All eligible inputs included';break
                def test_addition(feature):
                    return {'added':feature,'columns':selected+[feature],**evaluate(selected+[feature],parts)}
                proposals=list(executor.map(test_addition,remaining))
                step=len(selected)+1
                with (OUT/'candidate_steps.jsonl').open('a') as f:
                    for proposal in proposals:f.write(json.dumps({'step':step,**proposal})+'\n')
                if selected:
                    allowed=[x for x in proposals if acceptable(current,x)]
                    if not allowed:reason='No remaining addition met the declared improvement rule';break
                else:allowed=proposals
                best=sorted(allowed,key=lambda x:(-x['mean_f1'],x['mean_brier'],x['added']))[0]
                selected.append(best['added']);current=best
                path.append({'step':step,**best,'beats_constant_baseline':best['mean_f1']>=baseline['mean_f1']+.005})
                r.write(OUT/'accepted_path.json',path)
                print(f'Step {step}: {best["added"]}; selection F1={best["mean_f1"]:.4f}',flush=True)
            if len(selected)==20:reason='Declared 20-variable search cap reached'
        r.write(OUT/'selection_locked.json',{'locked_at_utc':datetime.now(timezone.utc).isoformat(),'selected':selected,'path':path,'reason':reason,'baseline':baseline})
        later,later_audits=partitions(data,later_folds)
        assessment={name:evaluate(cols,later) for name,cols in [('constant_baseline',[]),('selected',selected),('all_inputs',candidates)]}
    assert before=={x.name:r.digest(x) for x in frozen.iterdir() if x.is_file()}
    r.write(OUT/'results.json',{'selected':selected,'stop_reason':reason,'selection_baseline':baseline,'path':path,
      'later_assessment':assessment,'later_split_audits':later_audits,'frozen_bundle_unchanged':True,'status':'adaptive_historical_development'})
    print('Completed selection and later assessment',flush=True)

if __name__=='__main__':main()
