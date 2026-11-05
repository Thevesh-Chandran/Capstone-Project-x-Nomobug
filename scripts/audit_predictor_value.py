"""Development-only predictor ablation; never changes the frozen experiment."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from scripts import benchmark_warranty_models as b, compare_callback_candidates_v2 as c
from scripts.research_callback_targets import calibration_split
from scripts.simplify_supervisor_review import explain
from scripts.build_supervisor_model_review import group

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261017_predictor_value'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'protocol.json').exists():raise ValueError('Preserve existing declared run')
    directory=ROOT/'outputs/cp2-v2/prospective_callback_v2'
    before={p.name:digest(p) for p in directory.iterdir() if p.is_file()}
    bundle=json.loads((directory/'bundle.json').read_text())
    source=ROOT/bundle['training_input_relative_path']
    assert digest(source)==bundle['input_file_sha256']
    features=bundle['models']['challenger_all_history']['features']
    groups={g:[n for n in features if group(n)==g] for g in sorted(set(map(group,features)))}
    protocol={'declared_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':digest(source),
      'code_sha256':digest(Path(__file__)),'frozen_hashes':before,'features':features,'groups':groups,
      'folds':b.DEVELOPMENT_FOLDS,'model':'et10_leaf5','calibration':'Earlier purged calibration partition only',
      'permutation_repeats':1,'seed':1700,'scope':'Historical development diagnostic; no new final accuracy or deployment',
      'decision':'Candidate removal only if all three folds improve AP and Brier after group removal. Individual permutation is screening, not a removal verdict.'}
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    f=c.prepare_input(b.load_dataset_input(source));f=f[f.outcome_end_date<pd.Timestamp('2026-08-15')]
    rows=[];perms=[]
    for fi,(fold,start,end) in enumerate(b.DEVELOPMENT_FOLDS):
        train,test,audit=b.purged_split(f,start,end)
        fit,cal,inner=calibration_split(train)
        variants={'All 93 inputs':features,**{'Without '+g:[n for n in features if n not in cols] for g,cols in groups.items()}}
        for variant,columns in variants.items():
            numeric=[n for n in columns if n not in b.CATEGORICAL]
            pipe=c.make_pipeline('et10_leaf5',numeric)
            # Allow categorical-group removal as well as numerical-group removal.
            cat=[n for n in columns if n in b.CATEGORICAL]
            transforms=pipe.named_steps['preprocess'].transformers
            pipe.named_steps['preprocess'].transformers=[(name,transform,cat if name=='categorical' else cols) for name,transform,cols in transforms]
            with threadpool_limits(limits=2):
                pipe.fit(fit[columns],fit[b.TARGET],classifier__sample_weight=c.training_weights(fit,'standard'))
                calibrator,_=b.fit_calibrator(cal[b.TARGET],pipe.predict_proba(cal[columns])[:,1])
                threshold=b.select_threshold(cal[b.TARGET],b.apply_calibrator(calibrator,pipe.predict_proba(cal[columns])[:,1]))
                def score(x):return b.score(test[b.TARGET],b.apply_calibrator(calibrator,pipe.predict_proba(x)[:,1]),threshold)
                metrics=score(test[columns]);rows.append({'fold':fold,'variant':variant,'inputs':len(columns),'fit':len(fit),'calibration':len(cal),**metrics})
                if variant=='All 93 inputs':
                    for j,n in enumerate(features):
                        shuffled=test[columns].copy();rng=np.random.default_rng(1700+fi*1000+j)
                        shuffled[n]=rng.permutation(shuffled[n].to_numpy())
                        altered=score(shuffled)
                        perms.append({'fold':fold,'feature':n,'variable':explain(n)[0],
                            'AP_loss_when_shuffled':metrics['average_precision']-altered['average_precision'],
                            'Brier_increase_when_shuffled':altered['brier_score']-metrics['brier_score']})
            pd.DataFrame(rows).to_csv(OUT/'group_fold_metrics.csv',index=False)
            pd.DataFrame(perms).to_csv(OUT/'individual_fold_screen.csv',index=False)
            print(f'{fold}: {variant}; AP {metrics["average_precision"]:.4f}',flush=True)
    scores=pd.DataFrame(rows);base=scores[scores.variant.eq('All 93 inputs')].set_index('fold')
    summary=[]
    for variant,part in scores.groupby('variant',sort=False):
        part=part.set_index('fold');ap=part.average_precision-base.average_precision;br=part.brier_score-base.brier_score
        summary.append({'variant':variant,'mean_AP':part.average_precision.mean(),'mean_Brier':part.brier_score.mean(),
            'mean_F1':part.f1.mean(),'mean_accuracy':part.accuracy.mean(),'AP_change_vs_full':ap.mean(),'Brier_change_vs_full':br.mean(),
            'folds_improved_both':int(((ap>0)&(br<0)).sum()),
            'decision':'Reference' if variant=='All 93 inputs' else ('Candidate removal; confirm independently' if ((ap>0)&(br<0)).all() else 'No consistent evidence to remove this whole group')})
    pd.DataFrame(summary).to_csv(OUT/'group_decisions.csv',index=False)
    individual=pd.DataFrame(perms).groupby(['feature','variable'],as_index=False).agg(mean_AP_loss=('AP_loss_when_shuffled','mean'),mean_Brier_increase=('Brier_increase_when_shuffled','mean'),folds_AP_helped=('AP_loss_when_shuffled',lambda x:int((x>0).sum())))
    individual['decision']='Screening only: correlated inputs can substitute for one another; confirm by refitting without the variable.'
    individual.to_csv(OUT/'individual_predictor_screen.csv',index=False)
    after={p.name:digest(p) for p in directory.iterdir() if p.is_file()};assert before==after
    (OUT/'acceptance.json').write_text(json.dumps({'completed_utc':datetime.now(timezone.utc).isoformat(),'frozen_unchanged':True,'folds':3,'group_fits':len(rows),'individual_checks':len(perms),'independent_final_test':False},indent=2))
    print(pd.DataFrame(summary).to_string(index=False))

if __name__=='__main__':main()
