"""Exact original 100-service comparison, new duplicate feature variants."""
from pathlib import Path
from datetime import datetime,timezone
import json,joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import confusion_matrix
from threadpoolctl import threadpool_limits
import nbformat
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.compare_callback_blind_spots import folds
from scripts.freeze_age_rain_candidate import AGE,RAIN
from scripts.research_expanded_targets import ROOT,save,sha
from scripts.build_supervisor_model_review import execute,export_html

OUT=ROOT/'outputs/model_validation/20261018_original100_age_rain'
ORIGINAL=ROOT/'outputs/cp2-v2/model_corrected_v5/selected_ap'

def pipeline_copy(template,extra):
    pipe=clone(template);pipe.named_steps['classifier'].set_params(n_jobs=2)
    pre=pipe.steps[0][1];trans=[]
    for name,transformer,cols in pre.transformers:
        cols=list(cols);trans.append((name,transformer,cols if set(cols)&set(b.CATEGORICAL) else cols+extra))
    pre.set_params(transformers=trans);return pipe

def main():
    OUT.mkdir(parents=True,exist_ok=True);assert not (OUT/'protocol.json').exists()
    path=ORIGINAL/'historical_model.joblib';original=joblib.load(path);assert original['training_rows']==5333
    trainpath=ROOT/'outputs/cp2-v2/source_refresh_20260927/corrected_training/dataset_input.json'
    testpath=ROOT/'outputs/cp2-v2/source_refresh_20260927/new_mature_holdout/dataset_input.json'
    additions=ROOT/'outputs/model_validation/20261018_frozen_age_rain/new_inputs_private.pkl'
    protected={str(p.relative_to(ROOT)):sha(p) for folder in [ORIGINAL,ROOT/'outputs/cp2-v2/prospective_callback_v2'] for p in folder.iterdir() if p.is_file()}
    variants={'Original baseline':[],'Add age':AGE,'Add rainfall':RAIN,'Add both':AGE+RAIN}
    save(OUT/'protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'code_sha256':sha(__file__),
        'inputs':{str(p.relative_to(ROOT)):sha(p) for p in [path,trainpath,testpath,additions]},'protected':protected,
        'model':'Clone exact original et10_leaf5 pipeline and settings; baseline retrained and required to reproduce original saved probabilities.',
        'partitions':'Original corrected-training source5595rows; original historical fitting5333rows with outcomes before15Aug2026. Original reserved3048row development population, purged2025Q2/Q3/Q4 validation folds796/772/410. Same original100row later test15-27Aug2026.',
        'calibration':'Original procedure: pooled chronological out-of-fold2025 probabilities; Platt calibration and maximum-F1 threshold from those labels only; no tuning on100test.',
        'variants':variants,'freeze':'Save all four model files and thresholds/hashes before assessment predictions.',
        'limitations':'Adaptive historical comparison;100outcomes previously examined. GHS-AGE released June2025 after earliest validation period, so retrospective inputs are not strict as-issued historical predictions. Precise geocodes sparse. Original historical fit and validation observations overlap by design through OOF calibration; same procedure reproduced, not a wholly separate calibration holdout.'})
    frame=c.prepare_input(b.load_dataset_input(trainpath));test=c.prepare_input(b.load_dataset_input(testpath));extra=pd.read_pickle(additions)
    assert not extra.duplicated(c.KEYS).any()
    frame=frame.merge(extra,on=c.KEYS,how='left',validate='one_to_one',indicator=True);test=test.merge(extra,on=c.KEYS,how='left',validate='one_to_one',indicator=True)
    assert frame._merge.eq('both').all() and test._merge.eq('both').all()
    frame=frame.drop(columns='_merge');test=test.drop(columns='_merge')
    train=frame[frame.outcome_end_date<pd.Timestamp('2026-08-15')].copy();dev,diagnostic,_=c.reserved_split(frame)
    assert len(train)==5333 and len(test)==100 and int(test[b.TARGET].sum())==5
    assert train.outcome_end_date.max()<test.anchor_date.min()
    split=folds(dev);base=original['members'][0]['features'];template=original['members'][0]['pipeline']
    saved=pd.read_csv(ORIGINAL/'development_predictions.csv');saved.anchor_date=pd.to_datetime(saved.anchor_date)
    coverage=[]
    for name,d in [('Training',train),('Test',test)]:coverage.append({'Partition':name,'Services':len(d),'Returns':int(d[b.TARGET].sum()),'Known age':int(d.settlement_age_code.notna().sum()),'Known interval rain':int(d.previous_interval_rain_mean_mm.notna().sum()),'Known before-first rain':int(d.before_first_7d_rain_mean_mm.notna().sum())})
    save(OUT/'coverage.json',coverage);receipt={}
    for name,newcols in variants.items():
        cols=base+newcols;parts=[]
        for fold,fit,valid,audit in split:
            pipe=pipeline_copy(template,newcols)
            with threadpool_limits(limits=2):
                pipe.fit(fit[cols],fit[b.TARGET],classifier__sample_weight=c.training_weights(fit,'standard'));raw=pipe.predict_proba(valid[cols])[:,1]
            parts.append(valid[c.KEYS+[b.TARGET]].assign(raw_probability=raw,fold=fold))
        oof=pd.concat(parts,ignore_index=True)
        if not newcols:
            compare=oof.merge(saved[c.KEYS+['fold','raw_probability']],on=c.KEYS+['fold'],suffixes=('_new','_old'),validate='one_to_one')
            assert len(compare)==1978 and np.allclose(compare.raw_probability_new,compare.raw_probability_old,atol=1e-12,rtol=0)
        cal,_=b.fit_calibrator(oof[b.TARGET],oof.raw_probability);cut=b.select_threshold(oof[b.TARGET],b.apply_calibrator(cal,oof.raw_probability))
        pipe=pipeline_copy(template,newcols)
        with threadpool_limits(limits=2):pipe.fit(train[cols],train[b.TARGET],classifier__sample_weight=c.training_weights(train,'standard'))
        filename=name.lower().replace(' ','_')+'.joblib';artifact={'pipeline':pipe,'features':cols,'calibrator':cal,'threshold':cut,'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha(OUT/'protocol.json')}
        joblib.dump(artifact,OUT/filename);receipt[name]={'file':filename,'sha256':sha(OUT/filename),'threshold':cut,'inputs':len(cols),'frozen_at_utc':artifact['frozen_at_utc']}
        print('Frozen',name,'cutoff',cut,flush=True)
    save(OUT/'frozen_manifest.json',{'models':receipt,'all_frozen_before_test_predictions':True})
    with threadpool_limits(limits=2):original_raw=template.predict_proba(test[base])[:,1]
    original_p=b.apply_calibrator(original['calibrator'],original_raw)
    expected=b.score(test[b.TARGET],original_p,original['threshold']);assert expected['precision']==.4 and expected['recall']==.4
    results=[]
    for name,entry in receipt.items():
        assert sha(OUT/entry['file'])==entry['sha256'];model=joblib.load(OUT/entry['file'])
        with threadpool_limits(limits=2):raw=model['pipeline'].predict_proba(test[model['features']])[:,1]
        p=b.apply_calibrator(model['calibrator'],raw);metrics=b.score(test[b.TARGET],p,model['threshold']);tn,fp,fn,tp=confusion_matrix(test[b.TARGET],p>=model['threshold'],labels=[False,True]).ravel()
        if name=='Original baseline':assert np.allclose(p,original_p,atol=1e-12,rtol=0) and model['threshold']==original['threshold']
        results.append({'Model':name,'Inputs':len(model['features']),'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),**metrics})
        pd.DataFrame({'actual':test[b.TARGET].to_numpy(),'probability':p}).to_csv(OUT/(entry['file'].replace('.joblib','_test.csv')),index=False)
    save(OUT/'results.json',results)
    assert all(sha(ROOT/p)==h for p,h in protected.items())
    save(OUT/'verification.json',{'original_oof_probabilities_reproduced':1978,'original_test_probabilities_reproduced':100,'baseline_precision':.4,'all_frozen_before_test':True,'original_files_unchanged':True})
    report(results,coverage)
    print(json.dumps([{k:r[k] for k in ['Model','TP','FP','FN','TN','precision','recall','accuracy']} for r in results]))

def report(results,coverage):
    rows=[{'Model':r['Model'],'Inputs':r['Inputs'],'Accuracy %':100*r['accuracy'],'Precision %':100*r['precision'],'Recall %':100*r['recall'],'Correct alerts':r['TP'],'False alerts':r['FP'],'Missed returns':r['FN'],'F1':r['f1']} for r in results]
    nb=nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell('''# Original 100-service comparison: age and rainfall
**This is the exact original setup that produced40% precision.**

The original baseline was duplicated and retrained. All1,978original validation probabilities and100original test probabilities were reproduced to numerical tolerance. It caught2of5returns and gave3false alerts.

The three new versions add neighbourhood age, extra rainfall information, or both. The original pre-service rain inputs remain included. Added rain covers before the first visit and completed intervals between earlier visits. No post-prediction rainfall was used.

## Results on the same100services
All four models and thresholds were saved before any new test prediction. Calibration and thresholds came only from the original purged2025validation predictions. The final historical fit uses the original5,333mature training services.

This is a retrospective feature comparison. Five positive outcomes are too few to establish stable performance. Previously examined historical outcomes and age-data publication timing prevent a new independent future-test claim. No original artifact was overwritten.'''),nbformat.v4.new_code_cell('import pandas as pd\n'+f'display(pd.DataFrame({rows!r}).round(2))'),nbformat.v4.new_markdown_cell('## Coverage\nAge describes1kmneighbourhood development, not exact building age. Unknown ages/intervals remain missing.'),nbformat.v4.new_code_cell(f'display(pd.DataFrame({coverage!r}))')])
    execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'Original_100_Comparison.ipynb');export_html(nb,OUT/'Original_100_Comparison.html')

if __name__=='__main__':main()
