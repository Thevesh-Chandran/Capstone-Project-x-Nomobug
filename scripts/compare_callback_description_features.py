"""Exploratory, pre-2026-selected comparison of structured Problem-field features.

Uses the same timestamp-eligible cohort in both arms and removes all 2026
package/property groups before development selection. Never deploys a model.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
try:
    from scripts import benchmark_warranty_models as b
    from scripts.compare_flood_models import configure_contracts, evaluate_locked_candidate, paired_bootstrap
    from scripts.reconcile_callback_evidence import PESTS
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    from compare_flood_models import configure_contracts, evaluate_locked_candidate, paired_bootstrap
    from reconcile_callback_evidence import PESTS

MODELS=['extra_trees_depth6','rf_depth6','catboost_depth4_plain','lr_c1.0_plain']
DESCRIPTION_NUMERIC=[f'description_pest_{k.lower()}' for k in PESTS]+[
    'description_pest_count','description_problem_present','description_prevention']
KEYS=['population','sales_record_id','anchor_date']


def add_description_features(frame,features):
    features=features.copy(); features.anchor_date=pd.to_datetime(features.anchor_date)
    joined=frame.merge(features,on=KEYS,how='outer',validate='one_to_one',indicator=True)
    if not joined['_merge'].eq('both').all():
        raise ValueError('Description evidence and frozen anchors differ')
    for pest in PESTS:
        joined[f'description_pest_{pest.lower()}']=joined.problem_pests.map(lambda v:int(pest in str(v).split('|')))
    joined['description_pest_count']=joined[[f'description_pest_{k.lower()}' for k in PESTS]].sum(axis=1)
    joined['description_problem_present']=joined.problem_field_present.astype(int)
    joined['description_prevention']=joined.problem_prevention_mentioned.astype(int)
    return joined


def comparison_partitions(frame):
    # Purge against every original diagnostic group, even excluded edited records.
    past,diagnostic,audit=b.purged_split(frame,b.REPORTING_START)
    past=past[past.snapshot_timestamp_gate_pass].copy()
    diagnostic=diagnostic[diagnostic.snapshot_timestamp_gate_pass].copy()
    b.assert_package_property_disjoint(past,diagnostic)
    if not past.outcome_end_date.lt(b.REPORTING_START).all():
        raise ValueError('Immature training outcomes')
    return past,diagnostic,audit


def freeze_artifact_contract(path,input_path,feature_path):
    artifact=joblib.load(path)
    artifact.update(feature_preparation='compare_callback_description_features.add_description_features',
       cohort_eligibility='snapshot updated timestamp <= recorded service end; retrospective subset only',
       model_input_file_sha256=hashlib.sha256(input_path.read_bytes()).hexdigest(),
       description_features_file_sha256=hashlib.sha256(feature_path.read_bytes()).hexdigest(),
       deployment_status='not_operational; prospective validation required')
    joblib.dump(artifact,path)


def replay(path,test,input_path,feature_path):
    artifact=joblib.load(path)
    for field,source in [('model_input_file_sha256',input_path),('description_features_file_sha256',feature_path)]:
        if artifact[field]!=hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError('Frozen replay source hash mismatch')
    raw=artifact['pipeline'].predict_proba(test[artifact['features']])[:,1]
    probability=b.apply_calibrator(artifact['calibrator'],raw)
    prefix=str(test.population.iloc[0])
    prediction_path=path.parent/('diagnostic_predictions.csv' if path.name=='selected_model.joblib' else prefix+'_diagnostic_predictions.csv')
    saved=pd.read_csv(prediction_path,dtype={'sales_record_id':str})
    saved.anchor_date=pd.to_datetime(saved.anchor_date)
    check=test[KEYS].assign(replayed_probability=probability).merge(saved[KEYS+['probability']],on=KEYS,how='outer',validate='one_to_one',indicator=True)
    if not check['_merge'].eq('both').all() or not np.allclose(check.probability,check.replayed_probability,rtol=0,atol=1e-12):
        raise ValueError('Saved model replay differs')
    return {'rows':len(check),'max_probability_difference':float(abs(check.probability-check.replayed_probability).max())}


def blind_spots(frame,predictions):
    merged=frame.merge(predictions[KEYS+['probability','threshold']],on=KEYS,validate='one_to_one')
    merged['alert']=merged.probability.ge(merged.threshold)
    mask=merged.normalized_pest_category.eq('COCKROACH')
    rows=[]
    for name,m in [('cockroach_only',mask),('other_pests',~mask),('first_service',merged.service_number.eq(1))]:
        g=merged[m]; y=g[b.TARGET]
        rows.append({'segment':name,'rows':len(g),'positive_rows':int(y.sum()),
          'detected':int((y&g.alert).sum()),'missed':int((y&~g.alert).sum()),
          'false_alarms':int((~y&g.alert).sum())})
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=b.ROOT/'outputs/cp2-v2/description_feature_comparison')
    p.add_argument('--replay-model',type=Path)
    args=p.parse_args(); output=args.output_dir; output.mkdir(parents=True,exist_ok=True)
    configure_contracts(False)
    input_path=b.ROOT/'outputs/cp2-v2/model_callback_normalized_pest/dataset_input.json'
    feature_path=b.ROOT/'outputs/cp2-v2/callback_evidence_reconciliation/private_description_features.csv'
    frame=add_description_features(b.prepare_frame(b.load_dataset_input(input_path)),
          pd.read_csv(feature_path,dtype={'sales_record_id':str}))
    train,test,audit=comparison_partitions(frame)
    if args.replay_model:
        print(json.dumps(replay(args.replay_model,test,input_path,feature_path)))
        return
    eligible=pd.concat([train,test],ignore_index=True)
    baseline=list(b.FEATURE_SETS['base_weather_environment'])
    comparisons={}; predictions={}; population=str(frame.population.iloc[0])
    for name,numeric in [('baseline',baseline),('description',baseline+DESCRIPTION_NUMERIC)]:
        b.FEATURE_SETS.clear(); b.FEATURE_SETS['comparison']=numeric
        result=b.benchmark_population(eligible,output/name,200,MODELS)
        if 'diagnostic_2026' not in result:
            raise ValueError('Insufficient comparison support')
        comparisons[name]=result
        predictions[name]=pd.read_csv(output/name/f'{population}_diagnostic_predictions.csv',dtype={'sales_record_id':str})
        predictions[name].anchor_date=pd.to_datetime(predictions[name].anchor_date)
    b.FEATURE_SETS['comparison']=baseline+DESCRIPTION_NUMERIC
    locked=evaluate_locked_candidate(eligible,'comparison',comparisons['baseline']['selected_model'],output/'locked_description')
    predictions['locked_description']=pd.read_csv(output/'locked_description/diagnostic_predictions.csv',dtype={'sales_record_id':str})
    predictions['locked_description'].anchor_date=pd.to_datetime(predictions['locked_description'].anchor_date)
    receipt={'status':'exploratory_not_deployment','model_input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),
      'description_features_sha256':hashlib.sha256(feature_path.read_bytes()).hexdigest(),
      'feature_definitions':{'description_pest_flags':'Named Problem/Pest/Masalah field only; seven exact bounded bilingual pest patterns',
        'description_pest_count':'Count of recognized distinct pest types',
        'description_problem_present':'Nonempty named problem field',
        'description_prevention':'Explicit prevention/preventive/pencegahan mention in problem field'},
      'description_numeric_features':DESCRIPTION_NUMERIC,'models':MODELS,'candidate_count':8,
      'selection':'Mean pre-2026 purged quarterly development AP; ROC AUC tiebreak',
      'original_rows':len(frame),'excluded_post_service_or_unknown_edit_rows':int((~frame.snapshot_timestamp_gate_pass).sum()),
      'training_rows':len(train),'training_positive_rows':int(train[b.TARGET].sum()),
      'diagnostic_rows':len(test),'diagnostic_positive_rows':int(test[b.TARGET].sum()),
      'global_2026_group_purge_audit':audit,
      'comparisons':comparisons,'locked_same_family_description':locked,
      'blind_spots':{name:blind_spots(test,pr) for name,pr in predictions.items()},
      'paired_intervals':{},
      'limits':['Already inspected 2026 cohort; not an independent final test.',
        'Comparison covers only Calendar snapshots not edited after service end; same subset in both arms.',
        'Eligibility uses retrospective edit metadata and can bias sample selection; not all-customer performance.',
        'Timestamp gate cannot replace historical versioned snapshots or prospective collection.',
        'Problem mentions are not confirmed active infestation or treatment performed.',
        'Claim dates and later callback details are never predictors; target remains unchanged.']}
    for mode in ['description','locked_description']:
        paired=paired_bootstrap(predictions['baseline'],predictions[mode],200)
        paired['direction']=mode+'_minus_baseline'; receipt['paired_intervals'][mode]=paired
    for name,path in [('baseline',output/'baseline'/f'{population}_selected_model.joblib'),
                      ('description',output/'description'/f'{population}_selected_model.joblib'),
                      ('locked_description',output/'locked_description/selected_model.joblib')]:
        freeze_artifact_contract(path,input_path,feature_path)
    frozen=pd.read_csv(input_path.parent/f'{population}_diagnostic_predictions.csv',dtype={'sales_record_id':str})
    frozen.anchor_date=pd.to_datetime(frozen.anchor_date)
    reference=test[KEYS].merge(frozen,on=KEYS,validate='one_to_one')
    if len(reference)!=len(test):
        raise ValueError('Frozen reference cohort differs')
    receipt['retained_v4_same_subset_reference']={
        'metrics':b.score(reference[b.TARGET],reference.probability,float(reference.threshold.iloc[0])),
        'top20pct':b.priority_review_metrics(reference[b.TARGET],reference.probability),
        'caveat':'Original v4 development selection was not globally purged against this diagnostic subset; contextual reference only.'}
    (output/'comparison_results.json').write_text(json.dumps(receipt,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['comparisons','locked_same_family_description']},indent=2))


if __name__=='__main__':
    main()
