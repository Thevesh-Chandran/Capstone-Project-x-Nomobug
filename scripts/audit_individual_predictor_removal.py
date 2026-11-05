"""Refit without every individual predictor on the declared development folds."""
from datetime import datetime,timezone
import json
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from scripts.audit_predictor_value import ROOT,OUT,digest
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.research_callback_targets import calibration_split
from scripts.simplify_supervisor_review import explain

def main():
    path=OUT/'individual_removal_protocol.json'
    if path.exists():raise ValueError('Preserve existing run')
    protocol=json.loads((OUT/'protocol.json').read_text())
    folder=ROOT/'outputs/cp2-v2/prospective_callback_v2'
    before={p.name:digest(p) for p in folder.iterdir() if p.is_file()}
    bundle=json.loads((folder/'bundle.json').read_text());source=ROOT/bundle['training_input_relative_path']
    assert digest(source)==protocol['source_sha256']
    features=protocol['features']
    path.write_text(json.dumps({'declared_utc':datetime.now(timezone.utc).isoformat(),'code_sha256':digest(__import__('pathlib').Path(__file__)),
      'parent_protocol_sha256':digest(OUT/'protocol.json'),'remove_each':features,'folds':protocol['folds'],
      'decision_rule':'Removal candidate only when AP improves and Brier decreases in every fold. This is adaptive historical research, not independent confirmation.'},indent=2))
    f=c.prepare_input(b.load_dataset_input(source));f=f[f.outcome_end_date<pd.Timestamp('2026-08-15')]
    baseline=pd.read_csv(OUT/'group_fold_metrics.csv');baseline=baseline[baseline.variant.eq('All 93 inputs')].set_index('fold')
    results=[]
    for fold,start,end in b.DEVELOPMENT_FOLDS:
        train,test,_=b.purged_split(f,start,end);fit,cal,_=calibration_split(train)
        for index,removed in enumerate(features):
            columns=[n for n in features if n!=removed];numeric=[n for n in columns if n not in b.CATEGORICAL];cat=[n for n in columns if n in b.CATEGORICAL]
            pipe=c.make_pipeline('et10_leaf5',numeric)
            pipe.named_steps['preprocess'].transformers=[(name,transform,cat if name=='categorical' else cols) for name,transform,cols in pipe.named_steps['preprocess'].transformers]
            with threadpool_limits(limits=2):
                pipe.fit(fit[columns],fit[b.TARGET],classifier__sample_weight=c.training_weights(fit,'standard'))
                raw=pipe.predict_proba(cal[columns])[:,1];calibrator,_=b.fit_calibrator(cal[b.TARGET],raw)
                threshold=b.select_threshold(cal[b.TARGET],b.apply_calibrator(calibrator,raw))
                metrics=b.score(test[b.TARGET],b.apply_calibrator(calibrator,pipe.predict_proba(test[columns])[:,1]),threshold)
            results.append({'fold':fold,'removed':removed,'variable':explain(removed)[0],**metrics,
                'AP_change_vs_full':metrics['average_precision']-baseline.loc[fold,'average_precision'],
                'Brier_change_vs_full':metrics['brier_score']-baseline.loc[fold,'brier_score']})
            pd.DataFrame(results).to_csv(OUT/'individual_removal_fold_metrics.csv',index=False)
            if (index+1)%20==0:print(f'{fold}: {index+1}/93 individual removals',flush=True)
    df=pd.DataFrame(results);rows=[]
    for (name,label),part in df.groupby(['removed','variable'],sort=False):
        better=(part.AP_change_vs_full>0)&(part.Brier_change_vs_full<0)
        worse=(part.AP_change_vs_full<0)&(part.Brier_change_vs_full>0)
        rows.append({'Technical field':name,'Variable':label,'Mean AP change after removal':part.AP_change_vs_full.mean(),
          'Mean Brier change after removal':part.Brier_change_vs_full.mean(),'Folds improved both':int(better.sum()),
          'Decision':'Candidate to remove; confirm independently' if better.all() else ('Retain: removal worsened both measures in every fold' if worse.all() else 'Mixed evidence: no automatic removal')})
    pd.DataFrame(rows).to_csv(OUT/'individual_removal_decisions.csv',index=False)
    assert before=={p.name:digest(p) for p in folder.iterdir() if p.is_file()}
    (OUT/'individual_removal_acceptance.json').write_text(json.dumps({'completed_utc':datetime.now(timezone.utc).isoformat(),'fits':len(df),'variables':len(rows),'frozen_unchanged':True,'independent_confirmation':False},indent=2))
    print(pd.DataFrame(rows).Decision.value_counts().to_string())

if __name__=='__main__':main()
