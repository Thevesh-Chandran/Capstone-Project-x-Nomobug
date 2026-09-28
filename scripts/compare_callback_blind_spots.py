"""Bounded development-only selection of mixed-pest/first-service experiments.

Uses frozen full-cohort evidence; no operational sources or labels are changed.
All 2026 groups are reserved before 2025 selection, calibration and fitting.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
try:
    from scripts import benchmark_warranty_models as b
    from scripts.compare_flood_models import configure_contracts
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    from compare_flood_models import configure_contracts

MODELS=['extra_trees_depth6','rf_depth6','lr_c1.0_balanced','catboost_depth4_balanced']
PESTS=[k for k in b.PEST_ALIASES if k!='GENERAL_CONTROL']
TARGETED_NUMERIC=[
 'anchor_is_first','anchor_is_final','anchor_is_single_service','anchor_is_mixed_pest',
 'anchor_service_progress','anchor_remaining_services','prior_property_return_rate_smoothed',
 'prior_package_return_rate_smoothed','first_service_prior_property_return_rate',
 'mixed_pest_prior_property_return_rate','first_service_no_property_history',
 'mixed_pest_rain_14d','first_service_rain_14d',
] + [f'{stage}_pest_{pest.lower()}' for stage in ['first','final'] for pest in PESTS]
KEYS=['population','sales_record_id','anchor_date']


def add_targeted_features(frame):
    f=frame.copy()
    if (f.service_number.lt(1)|f.package_sessions_recorded.lt(f.service_number)).any():
        raise ValueError('Targeted features require paid within-package anchors')
    f['anchor_is_first']=f.service_number.eq(1).astype(float)
    f['anchor_is_final']=f.service_number.eq(f.package_sessions_recorded).astype(float)
    f['anchor_is_single_service']=f.package_sessions_recorded.eq(1).astype(float)
    f['anchor_is_mixed_pest']=f.pest_distinct_known_types.ge(2).astype(float)
    f['anchor_service_progress']=f.service_number/f.package_sessions_recorded
    f['anchor_remaining_services']=f.package_sessions_recorded-f.service_number
    # Fixed smoothing constants, not learned from held-out outcomes.
    f['prior_property_return_rate_smoothed']=(f.prior_property_warranty_claims+1)/(f.prior_property_service_events+10)
    f['prior_package_return_rate_smoothed']=(f.prior_package_warranty_claims+1)/(f.prior_package_service_events+10)
    f['first_service_prior_property_return_rate']=f.anchor_is_first*f.prior_property_return_rate_smoothed
    f['mixed_pest_prior_property_return_rate']=f.anchor_is_mixed_pest*f.prior_property_return_rate_smoothed
    f['first_service_no_property_history']=f.anchor_is_first*f.prior_property_service_events.eq(0)
    f['mixed_pest_rain_14d']=f.anchor_is_mixed_pest*f.prior_14d_precipitation_mm
    f['first_service_rain_14d']=f.anchor_is_first*f.prior_14d_precipitation_mm
    for pest in PESTS:
        for stage in ['first','final']:
            f[f'{stage}_pest_{pest.lower()}']=f[f'anchor_is_{stage}']*f[f'pest_has_{pest.lower()}']
    return f


def masks(f):
    first=f.service_number.eq(1); mixed=f.pest_distinct_known_types.ge(2)
    return {'all':pd.Series(True,index=f.index),'first_service':first,'mixed_pest':mixed,
            'target_union':first|mixed,'other_pests':~f.normalized_pest_category.eq('COCKROACH')}


def training_weights(f,policy):
    if policy not in ['standard','focus_positive_2x']:
        raise ValueError('Unknown training emphasis')
    w=np.ones(len(f))
    if policy=='focus_positive_2x':
        w[(masks(f)['target_union']&f[b.TARGET]).to_numpy()]=2
    return w


def budget_alert(scores,fraction=.2):
    scores=np.asarray(scores,dtype=float)
    if len(scores)==0 or not np.isfinite(scores).all() or not 0<fraction<=1:
        raise ValueError('Valid finite nonempty scores and budget required')
    cutoff=np.sort(scores)[-max(1,int(np.ceil(len(scores)*fraction)))]
    return scores>=cutoff


def segment_metrics(f,scores,threshold):
    alert=budget_alert(scores); threshold_alert=np.asarray(scores)>=threshold
    result={}
    for name,mask in masks(f).items():
        mask=mask.to_numpy(); y=f[b.TARGET].to_numpy(dtype=bool)[mask]
        pred=alert[mask]; th=threshold_alert[mask]
        pos=int(y.sum()); tp=int((y&pred).sum())
        result[name]={'rows':int(mask.sum()),'positive_rows':pos,'budget_alerts':int(pred.sum()),
          'budget_TP':tp,'budget_FN':int((y&~pred).sum()),'budget_FP':int((~y&pred).sum()),
          'budget_recall':tp/pos if pos else None,
          'budget_precision':tp/int(pred.sum()) if pred.sum() else None,
          'threshold_TP':int((y&th).sum()),'threshold_FN':int((y&~th).sum()),
          'threshold_FP':int((~y&th).sum())}
    return result


def paired_intervals(frame,baseline,candidate,repeats=300):
    """Paired connected-component resampling, including fixed-capacity recall."""
    def align(p):
        joined=frame[KEYS+[b.TARGET,'validation_group']].merge(p[KEYS+[b.TARGET,'probability']],on=KEYS,
           how='outer',validate='one_to_one',indicator=True,suffixes=('','_saved'))
        if not joined['_merge'].eq('both').all() or not joined[b.TARGET].eq(joined[b.TARGET+'_saved']).all():
            raise ValueError('Paired cohort or outcomes differ')
        return joined.probability.to_numpy()
    p0,p1=align(baseline),align(candidate)
    y=frame[b.TARGET].to_numpy(dtype=bool)
    groups=list(frame.reset_index(drop=True).groupby('validation_group',sort=False).indices.values())
    target_masks={name:mask.to_numpy() for name,mask in masks(frame).items()
                  if name in ['all','first_service','mixed_pest','target_union']}
    values={k:[] for k in ['roc_auc','average_precision']+[name+'_budget_recall' for name in target_masks]}
    rng=np.random.default_rng(42)
    for _ in range(repeats):
        idx=np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))])
        if np.unique(y[idx]).size<2:
            continue
        metrics=[b.score(y[idx],p[idx]) for p in [p0,p1]]
        for name in ['roc_auc','average_precision']:
            values[name].append(metrics[1][name]-metrics[0][name])
        alerts=[budget_alert(p[idx]) for p in [p0,p1]]
        for name,mask in target_masks.items():
            positives=y[idx]&mask[idx]
            if positives.sum():
                values[name+'_budget_recall'].append(float((alerts[1]&positives).sum()/positives.sum()
                    -(alerts[0]&positives).sum()/positives.sum()))
    return {'direction':'candidate_minus_baseline','groups':len(groups),'requested_repeats':repeats,
      'valid_repeats':{name:len(v) for name,v in values.items()},
      'confidence_95pct':{name:np.quantile(v,[.025,.975]).tolist() if v else None for name,v in values.items()}}


def select_candidates(candidates):
    control=next(c for c in candidates if c['name']=='base__extra_trees_depth6__standard')
    overall=max(candidates,key=lambda c:(c['mean_ap'],c['mean_auc']))
    eligible=[c for c in candidates if c['mean_ap']>=control['mean_ap']-1e-12
              and c['mean_budget_recall']>=control['mean_budget_recall']-1e-12]
    focused=max(eligible,key=lambda c:(c['mean_target_union_budget_recall'],c['mean_ap'],c['mean_auc']))
    return control,overall,focused


def folds(train):
    result=[]
    for name,start,end in b.DEVELOPMENT_FOLDS:
        past,validation,audit=b.purged_split(train,start,end)
        if len(past)<30 or len(validation)<15 or past[b.TARGET].nunique()<2 or validation[b.TARGET].sum()<3:
            raise ValueError(f'Insufficient pooled fold support: {name}')
        result.append((name,past,validation,audit))
    return result


def fit_pipeline(model,numeric,train,policy):
    fitted=b.make_model(model,numeric)
    fitted.fit(train[numeric+b.CATEGORICAL],train[b.TARGET],
               classifier__sample_weight=training_weights(train,policy))
    return fitted


def evaluate(train,feature_sets,output):
    split=folds(train); candidates=[]; oof={}
    for feature_set,numeric in feature_sets.items():
        for model in MODELS:
            for policy in ['standard','focus_positive_2x']:
                name='__'.join([feature_set,model,policy]); metrics=[]; parts=[]
                for fold,past,validation,audit in split:
                    fitted=fit_pipeline(model,numeric,past,policy)
                    probability=fitted.predict_proba(validation[numeric+b.CATEGORICAL])[:,1]
                    segments=segment_metrics(validation,probability,.5)
                    metrics.append({'fold':fold,'training_rows':len(past),**audit,
                      **b.score(validation[b.TARGET],probability),'segments':segments,
                      'top20pct':b.priority_review_metrics(validation[b.TARGET],probability)})
                    parts.append(validation[b.KEYS+['validation_group']].assign(raw_probability=probability,fold=fold))
                candidate={'name':name,'feature_set':feature_set,'model':model,'training_policy':policy,
                  'mean_ap':float(np.mean([m['average_precision'] for m in metrics])),
                  'mean_auc':float(np.mean([m['roc_auc'] for m in metrics])),
                  'mean_budget_recall':float(np.mean([m['segments']['all']['budget_recall'] for m in metrics])),
                  'mean_target_union_budget_recall':float(np.mean([m['segments']['target_union']['budget_recall'] for m in metrics])),
                  'folds':metrics}
                candidates.append(candidate); oof[name]=pd.concat(parts,ignore_index=True)
                print(f'{name}: dev AP={candidate["mean_ap"]:.4f}, target recall={candidate["mean_target_union_budget_recall"]:.4f}',flush=True)
    (output/'development_candidates.json').write_text(json.dumps(candidates,indent=2,allow_nan=False))
    return candidates,oof


def fit_and_score(selection,train,test,numeric,oof,directory,input_hash):
    calibrator,calibration=b.fit_calibrator(oof[b.TARGET],oof.raw_probability)
    oof=oof.assign(probability=b.apply_calibrator(calibrator,oof.raw_probability))
    threshold=b.select_threshold(oof[b.TARGET],oof.probability)
    fitted=fit_pipeline(selection['model'],numeric,train,selection['training_policy'])
    features=numeric+b.CATEGORICAL
    raw=fitted.predict_proba(test[features])[:,1]; probability=b.apply_calibrator(calibrator,raw)
    predictions=test[b.KEYS+['validation_group']].assign(raw_probability=raw,probability=probability,threshold=threshold)
    directory.mkdir(parents=True,exist_ok=True)
    predictions.to_csv(directory/'diagnostic_predictions.csv',index=False)
    oof.to_csv(directory/'development_predictions.csv',index=False)
    joblib.dump({'pipeline':fitted,'features':features,'calibrator':calibrator,'threshold':threshold,
      'input_file_sha256':input_hash,'feature_preparation':'compare_callback_blind_spots.add_targeted_features',
      'training_outcome_end_exclusive':b.REPORTING_START,'selection':selection,
      'feature_preparation_options':b.feature_preparation_options(),'purpose':'diagnostic_not_deployment'},directory/'selected_model.joblib')
    return {'selection':selection,'features':features,'calibration':calibration,'threshold':threshold,
      'diagnostic':b.score(test[b.TARGET],probability,threshold),
      'priority_top20pct':b.priority_review_metrics(test[b.TARGET],probability),
      'segments':segment_metrics(test,probability,threshold)},predictions


def verify(path,test,input_hash):
    artifact=joblib.load(path)
    if artifact['input_file_sha256']!=input_hash:
        raise ValueError('Replay input changed')
    expected=pd.read_csv(path.parent/'diagnostic_predictions.csv',dtype={'sales_record_id':str})
    expected.anchor_date=pd.to_datetime(expected.anchor_date)
    raw=artifact['pipeline'].predict_proba(test[artifact['features']])[:,1]
    p=b.apply_calibrator(artifact['calibrator'],raw)
    joined=test[KEYS+[b.TARGET]].assign(replayed=p).merge(expected,on=KEYS,how='outer',validate='one_to_one',indicator=True,suffixes=('','_saved'))
    if not joined['_merge'].eq('both').all() or not joined[b.TARGET].eq(joined[b.TARGET+'_saved']).all() or not np.allclose(joined.replayed,joined.probability,rtol=0,atol=1e-12):
        raise ValueError('Saved prediction replay failed')
    return {'rows':len(joined),'max_probability_difference':float(abs(joined.replayed-joined.probability).max())}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-json',type=Path,default=b.ROOT/'outputs/cp2-v2/model_callback_normalized_pest/dataset_input.json')
    p.add_argument('--output-dir',type=Path,default=b.ROOT/'outputs/cp2-v2/blind_spot_comparison')
    p.add_argument('--verify-model',type=Path)
    args=p.parse_args(); configure_contracts(False)
    frame=add_targeted_features(b.prepare_frame(b.load_dataset_input(args.input_json)))
    train,test,audit=b.purged_split(frame,b.REPORTING_START)
    digest=hashlib.sha256(args.input_json.read_bytes()).hexdigest()
    if args.verify_model:
        print(json.dumps(verify(args.verify_model,test,digest)));return
    args.output_dir.mkdir(parents=True,exist_ok=True)
    base=list(b.FEATURE_SETS['base_weather_environment'])
    feature_sets={'base':base,'targeted':base+TARGETED_NUMERIC}
    candidates,oof=evaluate(train,feature_sets,args.output_dir)
    control,overall,focused=select_candidates(candidates)
    results={}; predictions={}
    family_control=next(c for c in candidates if c['feature_set']=='base' and c['model']==focused['model']
                        and c['training_policy']==focused['training_policy'])
    unweighted=next(c for c in candidates if c['feature_set']==focused['feature_set'] and c['model']==focused['model']
                    and c['training_policy']=='standard')
    for name,selected in [('control',control),('overall_selected',overall),('focus_selected',focused),
                          ('focus_family_control',family_control),('focus_unweighted',unweighted)]:
        results[name],predictions[name]=fit_and_score(selected,train,test,feature_sets[selected['feature_set']],
           oof[selected['name']],args.output_dir/name,digest)
    intervals={}
    for name in ['overall_selected','focus_selected']:
        intervals[name]=paired_intervals(test,predictions['control'],predictions[name])
        intervals[name]['direction']=name+'_minus_control'
    for control_name in ['focus_family_control','focus_unweighted']:
        key='focus_selected_minus_'+control_name
        intervals[key]=paired_intervals(test,predictions[control_name],predictions['focus_selected'])
        intervals[key]['direction']=key
    report={'status':'experimental_not_deployment','input_file_sha256':digest,
      'target':'recorded_corrective_calendar_callback_within_30d','original_rows':len(frame),
      'training_rows':len(train),'training_positive_rows':int(train[b.TARGET].sum()),
      'diagnostic_rows':len(test),'diagnostic_positive_rows':int(test[b.TARGET].sum()),
      'all_2026_groups_excluded_before_development_selection':True,'split_audit':audit,
      'numeric_feature_sets':feature_sets,'categorical_features':b.CATEGORICAL,
      'candidate_count':len(candidates),'development_candidates':candidates,
      'selection_rule':{'overall':'Maximum mean 2025 fold AP; AUC tiebreak',
        'focus':'Maximum mean target-union recall at global top20%, subject to no decline in mean fold AP or global top20% recall versus the fixed ExtraTrees control; AP/AUC tiebreak',
        'focus_union':'service_number=1 OR at least two known pest types',
        'focus_training_weight':'Double training weight only for positive first/mixed-pest anchors; model class weighting otherwise unchanged'},
      'training_segments':{name:{'rows':int(mask.sum()),'positive_rows':int(train.loc[mask,b.TARGET].sum())}
                           for name,mask in masks(train).items()},
      'results':results,'paired_intervals':intervals,
      'limits':['2026 already inspected; exploratory diagnostic, not independent final evaluation.',
        'Targeted ideas were motivated by earlier 2026 error inspection; selection scores do not remove that adaptive exposure.',
        'Mixed-pest and first-service positives are scarce; separate specialists are not fitted.',
        'Segment groups overlap; callback anchors are not independent completed events.',
        'Review capacity keeps cutoff ties, and prospective deployment needs a defined scoring batch.',
        'No new source data, labels, warranty policy or operational model changed.']}
    (args.output_dir/'comparison_results.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps({k:{'selection':v['selection']['name'],'metrics':v['diagnostic'],
      'budget':v['priority_top20pct'],'segments':v['segments']} for k,v in results.items()},indent=2))


if __name__=='__main__':
    main()
