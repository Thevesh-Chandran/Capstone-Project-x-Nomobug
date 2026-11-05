"""Freeze a separate 93-input historical model before its larger later assessment."""
from datetime import datetime,timezone
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import confusion_matrix
from threadpoolctl import threadpool_limits
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts import research_callback_targets as r

OUT=b.ROOT/'outputs/model_validation/20261017_larger_frozen_test'
ORIGINAL=b.ROOT/'outputs/cp2-v2/prospective_callback_v2'


def make_partitions(data):
    test=data[data.anchor_date.between('2026-01-01','2026-08-27')].copy()
    validation0=data[data.anchor_date.between('2025-07-01','2025-11-30') & data.outcome_end_date.lt('2026-01-01')].copy()
    train0=data[data.anchor_date.between('2024-03-08','2025-05-31') & data.outcome_end_date.lt('2025-07-01')].copy()
    validation=validation0[~validation0.validation_group.isin(set(test.validation_group))].copy()
    train=train0[~train0.validation_group.isin(set(test.validation_group)|set(validation0.validation_group))].copy()
    for left,right in [(train,validation),(train,test),(validation,test)]:
        b.assert_package_property_disjoint(left,right)
        assert set(left.validation_group).isdisjoint(right.validation_group)
    assert train.outcome_end_date.max()<pd.Timestamp('2025-07-01')
    assert validation.outcome_end_date.max()<pd.Timestamp('2026-01-01')
    return train,validation,test


def bootstrap_intervals(test,probability,threshold,repeats=2000):
    y=test[b.TARGET].to_numpy(dtype=bool);pred=probability>=threshold
    rows=pd.DataFrame({'group':test.validation_group.to_numpy(),'TP':y&pred,'FP':~y&pred,'FN':y&~pred,'TN':~y&~pred})
    grouped=rows.groupby('group')[['TP','FP','FN','TN']].sum().to_numpy(dtype=float)
    rng=np.random.default_rng(17017);values=[]
    for _ in range(repeats):
        tp,fp,fn,tn=grouped[rng.integers(0,len(grouped),size=len(grouped))].sum(axis=0)
        values.append([(tp+tn)/(tp+fp+fn+tn),tp/(tp+fp) if tp+fp else np.nan,
                       tp/(tp+fn) if tp+fn else np.nan,2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else np.nan])
    return {metric:{'low':float(np.nanpercentile(np.array(values)[:,i],2.5)),
                    'high':float(np.nanpercentile(np.array(values)[:,i],97.5))}
            for i,metric in enumerate(['accuracy','precision','recall','f1'])}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'protocol.json').exists():raise ValueError('Preserve declared evaluation; do not overwrite')
    before={p.name:r.digest(p) for p in ORIGINAL.iterdir() if p.is_file()}
    manifest=json.loads((ORIGINAL/'bundle.json').read_text())
    source=b.ROOT/manifest['training_input_relative_path']
    assert r.digest(source)==manifest['input_file_sha256']
    old_path=ORIGINAL/'challenger_all_history.joblib'
    assert r.digest(old_path)==manifest['models']['challenger_all_history']['sha256']
    old=joblib.load(old_path)
    assert len(old['members'])==1
    features=list(old['members'][0]['features']);assert len(set(features))==93
    protocol={'declared_at_utc':datetime.now(timezone.utc).isoformat(),'code_sha256':r.digest(__file__),
      'source_path':str(source.relative_to(b.ROOT)),'source_sha256':r.digest(source),
      'original_model_sha256':r.digest(old_path),'original_frozen_hashes':before,'features':features,
      'model':'Clone of frozen Extra Trees pipeline: 300 trees, max depth 10, min leaf 5, balanced classes, seed 42',
      'training_dates':['2024-03-08','2025-05-31'],'validation_dates':['2025-07-01','2025-11-30'],
      'test_dates':['2026-01-01','2026-08-27'],
      'rules':['Use agreed fixed dates, not a search for the highest-scoring split.',
        'Train and validation exclude test property/sale groups; training also excludes validation groups.',
        'Training outcomes complete before validation starts; validation outcomes complete before test starts.',
        'Fit model only on training; fit Platt calibration and maximum-F1 cutoff only on validation.',
        'Keep calibration observations out of classifier fitting; do not refit using test records.',
        'Persist new model and cutoff with hash before predicting test; evaluate test once.',
        'No feature search, model-setting search, cutoff retuning or production replacement.',
        'Records and modelling choices were explored in previous work; historical assessment is not a fresh independent prospective test.',
        'Target matches original model: recorded corrective Calendar return within 30 days, not all formal warranty claims.',
        'Cluster bootstrap 2000 repeats by property/sale validation group, conditional on this fitted model; does not account for prior research selection.']}
    r.write(OUT/'protocol.json',protocol)
    frame=c.prepare_input(b.load_dataset_input(source))
    train,validation,test=make_partitions(frame)
    assert (len(train),len(validation),len(test))==(1506,1177,2075)
    assert not set(features)-set(frame)
    split_counts=[]
    for name,part in [('Training',train),('Validation',validation),('Test',test)]:
        split_counts.append({'part':name,'services':len(part),'return_windows':int(part[b.TARGET].sum()),
          'groups':int(part.validation_group.nunique()),'first_service':str(part.anchor_date.min().date()),
          'last_service':str(part.anchor_date.max().date()),'latest_outcome_end':str(part.outcome_end_date.max().date())})
    r.write(OUT/'split_audit.json',{'parts':split_counts,'groups_disjoint':True,'no_features_or_settings_selected_from_test':True})
    for name,part in [('train',train),('validation',validation),('test',test)]:
        part[c.KEYS+['validation_group',b.TARGET]].to_json(OUT/(name+'_identities_private.json'),orient='records',date_format='iso')
    pipeline=clone(old['members'][0]['pipeline'])
    pipeline.named_steps['classifier'].set_params(n_jobs=2)
    with threadpool_limits(limits=2):
        pipeline.fit(train[features],train[b.TARGET],classifier__sample_weight=np.ones(len(train)))
        raw=pipeline.predict_proba(validation[features])[:,1]
        calibrator,calibration_audit=b.fit_calibrator(validation[b.TARGET],raw)
        calibration_audit['data_authority']='Separate July-November 2025 validation only; not out-of-fold test data'
        if calibrator is not None:calibration_audit['method']='platt_on_separate_2025_validation'
        threshold=b.select_threshold(validation[b.TARGET],b.apply_calibrator(calibrator,raw))
    artifact={'pipeline':pipeline,'features':features,'calibrator':calibrator,'threshold':threshold,
       'training_rows':len(train),'validation_rows':len(validation),'calibration':calibration_audit,
       'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':r.digest(OUT/'protocol.json'),
       'purpose':'separate_historical_larger_test_not_live_model','source_sha256':r.digest(source)}
    path=OUT/'larger_historical_model.joblib';joblib.dump(artifact,path)
    freeze_receipt={'frozen_at_utc':artifact['frozen_at_utc'],'model_sha256':r.digest(path),
       'threshold':threshold,'protocol_sha256':r.digest(OUT/'protocol.json'),'features':len(features),
       'training_rows':len(train),'validation_rows':len(validation),'test_predictions_not_yet_computed':True}
    r.write(OUT/'frozen_manifest.json',freeze_receipt)
    print('Separate model and cutoff frozen; now assessing 2075 later service windows',flush=True)
    assert r.digest(path)==freeze_receipt['model_sha256']
    frozen=joblib.load(path)
    with threadpool_limits(limits=2):
        probability=b.apply_calibrator(frozen['calibrator'],frozen['pipeline'].predict_proba(test[features])[:,1])
    metrics=b.score(test[b.TARGET],probability,threshold)
    tn,fp,fn,tp=confusion_matrix(test[b.TARGET],probability>=threshold,labels=[False,True]).ravel()
    constant=np.full(len(test),float(train[b.TARGET].mean()))
    result={'status':'larger_historical_assessment_not_fresh_prospective','evaluated_at_utc':datetime.now(timezone.utc).isoformat(),
       'frozen_model_sha256':r.digest(path),'protocol_sha256':r.digest(OUT/'protocol.json'),
       'features':len(features),'metrics':metrics,'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),
       'cluster_bootstrap_95':bootstrap_intervals(test,probability,threshold),
       'always_no':b.score(test[b.TARGET],np.zeros(len(test)),.5),
       'always_yes':b.score(test[b.TARGET],np.ones(len(test)),.5),
       'training_prevalence_brier':float(np.mean((test[b.TARGET].to_numpy(dtype=float)-constant)**2)),
       'original_frozen_bundle_unchanged':before=={p.name:r.digest(p) for p in ORIGINAL.iterdir() if p.is_file()},
       'new_artifact_unchanged_during_scoring':r.digest(path)==freeze_receipt['model_sha256']}
    assert result['original_frozen_bundle_unchanged'] and result['new_artifact_unchanged_during_scoring']
    private=test[c.KEYS+['validation_group',b.TARGET]].copy()
    private['probability']=probability;private['predicted_return']=probability>=threshold
    private.to_csv(OUT/'test_predictions_private.csv',index=False)
    r.write(OUT/'results.json',result)
    print(json.dumps({k:v for k,v in result.items() if k in ['metrics','TP','FP','FN','TN','cluster_bootstrap_95']},indent=2))

if __name__=='__main__':main()
