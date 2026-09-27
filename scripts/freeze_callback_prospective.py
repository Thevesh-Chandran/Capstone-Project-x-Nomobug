"""Freeze all-mature-data callback models and append prospective feature/score logs.

No live Calendar/sheet/warehouse writes. Refit models have no measured future
performance. Historical replay is separate from real prospective recording.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import joblib
import numpy as np
import pandas as pd
try:
    from scripts import benchmark_warranty_models as b
    from scripts.compare_callback_blind_spots import add_targeted_features,fit_pipeline,masks,segment_metrics,paired_intervals
    from scripts.compare_flood_models import configure_contracts
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    from compare_callback_blind_spots import add_targeted_features,fit_pipeline,masks,segment_metrics,paired_intervals
    from compare_flood_models import configure_contracts

LOCAL=ZoneInfo('Asia/Kuala_Lumpur')
DEFAULT_OUTPUT=b.ROOT/'outputs/cp2-v2/prospective_callback_v1'
INPUT=b.ROOT/'outputs/cp2-v2/model_callback_normalized_pest/dataset_input.json'
KEYS=['population','sales_record_id','anchor_date']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record_digest(record):
    content={k:v for k,v in record.items() if k!='record_sha256'}
    return hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def timestamp(value):
    parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timezone-bearing timestamp required')
    return parsed.astimezone(timezone.utc)


def prepare_scoring_frame(raw):
    raw=raw.copy()
    raw['outcome_end_date']=pd.to_datetime(raw.anchor_date)+pd.Timedelta(days=30)
    # Outcomes may be absent: never synthesize a false/no-callback label.
    return add_targeted_features(b.prepare_frame(raw,require_outcomes=False))


def validate_prediction_times(frame,manifest,now):
    now=timestamp(now); frozen=timestamp(manifest['frozen_at_utc'])
    start=pd.Timestamp(manifest['cohort_start']);end=pd.Timestamp(manifest['cohort_end'])
    if not frame.anchor_date.between(start,end).all():
        raise ValueError('Anchors outside the predeclared prospective cohort')
    if now<frozen:
        raise ValueError('Cannot score before model freeze')
    if not {'prediction_at','feature_snapshot_at','service_start_at','service_end_at'}.issubset(frame.columns):
        raise ValueError('Prediction, snapshot and Calendar service timestamps required')
    for row in frame.to_dict('records'):
        prediction=timestamp(row['prediction_at']); snapshot=timestamp(row['feature_snapshot_at'])
        service_start=timestamp(row['service_start_at']);service_end=timestamp(row['service_end_at'])
        if not frozen<=prediction<=now or snapshot>prediction:
            raise ValueError('Prediction/snapshot timing violates prospective availability')
        if (now-prediction).total_seconds()>300:
            raise ValueError('Historical backfill cannot be presented as prospective scoring')
        if not service_start<=service_end<=prediction or (prediction-service_end).total_seconds()>300:
            raise ValueError('Score must be recorded within five minutes after Calendar service end')
        if service_start.astimezone(LOCAL).date()!=row['anchor_date'].date():
            raise ValueError('Calendar service start must match the local anchor date')


def freeze(output):
    if (output/'bundle.json').exists():
        raise ValueError('Frozen bundle already exists; use a new explicitly versioned directory')
    configure_contracts(False)
    receipt=json.loads((b.ROOT/'config/warranty_blind_spot_experiment_v1.json').read_text())
    input_hash=digest(INPUT)
    if receipt['input_file_sha256']!=input_hash:
        raise ValueError('Development selection and frozen source differ')
    frame=add_targeted_features(b.prepare_frame(b.load_dataset_input(INPUT)))
    now=datetime.now(timezone.utc); local_date=now.astimezone(LOCAL).date()
    if not frame.outcome_end_date.lt(pd.Timestamp(local_date)).all():
        raise ValueError('All training outcomes must mature before freeze')
    output.mkdir(parents=True,exist_ok=True)
    manifest={'version':'prospective_callback_v1','status':'frozen_not_operational_no_future_performance',
      'frozen_at_utc':now.isoformat(),'cohort_start':str(local_date+timedelta(days=1)),
      'cohort_end':str(local_date+timedelta(days=30)),
      'earliest_final_evaluation_date':str(local_date+timedelta(days=61)),
      'target':'recorded_corrective_calendar_callback_within_30d',
      'date_authority':'Calendar','review_fraction':.2,'input_file_sha256':input_hash,
      'training_rows':len(frame),'training_positive_rows':int(frame[b.TARGET].sum()),
      'training_2026_rows':int(frame.anchor_date.ge('2026-01-01').sum()),
      'latest_training_anchor':str(frame.anchor_date.max().date()),
      'latest_training_outcome_end':str(frame.outcome_end_date.max().date()),
      'training_segment_support':{name:{'rows':int(mask.sum()),'positive_rows':int(frame.loc[mask,b.TARGET].sum())}
                                  for name,mask in masks(frame).items()},
      'models':{},'training_replay_file':'training_replay_private.csv',
      'feature_preparation_hashes':{str(path.relative_to(b.ROOT)):digest(path) for path in
          [b.ROOT/'scripts/benchmark_warranty_models.py',b.ROOT/'scripts/compare_callback_blind_spots.py']},
      'limits':['These all-history refits are distinct from the 108-versus-100 diagnostic models.',
        'No training-set scores establish future model accuracy.',
        'Calibrators and thresholds remain from earlier purged development; monitor future calibration.',
        'Timestamp declarations cannot independently prove every upstream predictor was available.',
        'The all-mature-data reference is an experimental refit; governing v4 is not replaced.',
        'Prospective services can include previously seen customers; this differs from retrospective group-disjoint generalization.',
        'Source refresh/feature extraction and complete Calendar outcome capture remain required.']}
    replay=frame[KEYS].copy();replay.anchor_date=replay.anchor_date.dt.strftime('%Y-%m-%d')
    for name,variant in [('reference_all_history','control'),('challenger_all_history','focus_selected')]:
        selected=receipt['results'][variant]
        old_info=next(x for x in receipt['artifacts'] if x['variant']==variant)
        old_path=b.ROOT/old_info['relative_path']
        if digest(old_path)!=old_info['sha256']:
            raise ValueError('Development artifact integrity failure')
        old=joblib.load(old_path)
        features=list(old['features']);numeric=[c for c in features if c not in b.CATEGORICAL]
        selection=selected['selection']
        fitted=fit_pipeline(selection['model'],numeric,frame,selection['training_policy'])
        artifact={**old,'pipeline':fitted,'purpose':'frozen_all_history_prospective_not_deployment',
                  'frozen_at_utc':now.isoformat(),'training_rows':len(frame),
                  'training_outcome_end_exclusive':str(local_date),'input_file_sha256':input_hash}
        path=output/(name+'.joblib');joblib.dump(artifact,path)
        probability=b.apply_calibrator(artifact['calibrator'],fitted.predict_proba(frame[features])[:,1])
        replay[name]=probability
        manifest['models'][name]={'file':path.name,'sha256':digest(path),'features':features,
          'selection_name':selection['name'],'threshold':artifact['threshold'],
          'source_development_artifact_sha256':old_info['sha256']}
    replay.to_csv(output/manifest['training_replay_file'],index=False)
    manifest['training_replay_sha256']=digest(output/manifest['training_replay_file'])
    (output/'bundle.json').write_text(json.dumps(manifest,indent=2,allow_nan=False))
    return manifest


def load_bundle(output):
    manifest=json.loads((output/'bundle.json').read_text())
    for relative,expected_hash in manifest['feature_preparation_hashes'].items():
        if digest(b.ROOT/relative)!=expected_hash:
            raise ValueError('Frozen feature-preparation code changed')
    models={}
    for name,info in manifest['models'].items():
        path=output/info['file']
        if digest(path)!=info['sha256']:
            raise ValueError('Frozen model hash mismatch')
        artifact=joblib.load(path)
        if artifact['features']!=info['features'] or artifact['frozen_at_utc']!=manifest['frozen_at_utc']:
            raise ValueError('Bundle feature or freeze contract differs')
        models[name]=artifact
    return manifest,models


def verify(output):
    configure_contracts(False);manifest,models=load_bundle(output)
    if digest(INPUT)!=manifest['input_file_sha256'] or digest(output/manifest['training_replay_file'])!=manifest['training_replay_sha256']:
        raise ValueError('Replay inputs changed')
    raw=b.load_dataset_input(INPUT).drop(columns=[b.TARGET])
    frame=prepare_scoring_frame(raw)
    if b.TARGET in frame:
        raise ValueError('Outcome entered prospective predictors')
    expected=pd.read_csv(output/manifest['training_replay_file'],dtype={'sales_record_id':str})
    keys=frame[KEYS].copy();keys.anchor_date=keys.anchor_date.dt.strftime('%Y-%m-%d')
    differences={}
    for name,artifact in models.items():
        p=b.apply_calibrator(artifact['calibrator'],artifact['pipeline'].predict_proba(frame[artifact['features']])[:,1])
        joined=keys.assign(replayed=p).merge(expected[KEYS+[name]],on=KEYS,how='outer',validate='one_to_one',indicator=True)
        if not joined['_merge'].eq('both').all() or not np.allclose(joined.replayed,joined[name],rtol=0,atol=1e-12):
            raise ValueError('Bundle predictor-only replay failed')
        differences[name]=float(abs(joined.replayed-joined[name]).max())
    return {'rows':len(frame),'max_probability_difference':differences,'outcome_required_for_scoring':False}


def score(output,input_path,log_dir):
    configure_contracts(False);manifest,models=load_bundle(output)
    frame=prepare_scoring_frame(b.load_dataset_input(input_path))
    now=datetime.now(timezone.utc)
    validate_prediction_times(frame,manifest,now)
    for name,artifact in models.items():
        frame[name]=b.apply_calibrator(artifact['calibrator'],artifact['pipeline'].predict_proba(frame[artifact['features']])[:,1])
    feature_columns=sorted({c for info in manifest['models'].values() for c in info['features']})
    rows=json.loads(frame[KEYS+['address_hash','prediction_at','feature_snapshot_at','service_start_at','service_end_at']+feature_columns+list(models)].to_json(orient='records',date_format='iso'))
    pending=[]
    for row in rows:
        key='|'.join(str(row[k]) for k in KEYS)
        path=log_dir/(hashlib.sha256(key.encode()).hexdigest()+'.json')
        if path.exists():
            raise ValueError('Prediction already logged; immutable records cannot be overwritten')
        record={'logged_at_utc':now.isoformat(),'bundle_sha256':digest(output/'bundle.json'),
          'row':row,'label_status':'awaiting_calendar_30d_outcome'}
        record['record_sha256']=record_digest(record)
        pending.append((path,record))
    log_dir.mkdir(parents=True,exist_ok=True)
    for path,record in pending:
        with path.open('x',encoding='utf-8') as handle:
            json.dump(record,handle,indent=2,allow_nan=False)
    return {'logged_rows':len(pending),'models':list(models),'performance':'not_available_until_mature_outcomes'}


def evaluate(output,labels_path,log_dir):
    manifest,models=load_bundle(output);now=datetime.now(timezone.utc)
    if now.astimezone(LOCAL).date()<pd.Timestamp(manifest['earliest_final_evaluation_date']).date():
        raise ValueError('Prospective cohort and inclusive 30-day outcomes have not matured')
    result_path=output/'prospective_evaluation.json'
    if result_path.exists():
        raise ValueError('Final prospective evaluation already recorded; do not repeatedly tune this cohort')
    labels=json.loads(labels_path.read_text())
    if labels.get('date_authority')!='Calendar' or labels.get('cohort_complete') is not True:
        raise ValueError('Complete Calendar-derived cohort outcomes required')
    last_outcome=pd.Timestamp(manifest['cohort_end'])+pd.Timedelta(days=30)
    if pd.Timestamp(labels['calendar_coverage_through'])<last_outcome:
        raise ValueError('Calendar coverage is incomplete for the full outcome window')
    records=[]
    for path in sorted(log_dir.glob('*.json')):
        entry=json.loads(path.read_text())
        if entry.get('bundle_sha256')!=digest(output/'bundle.json'):
            continue
        if entry.get('record_sha256')!=record_digest(entry) or b.TARGET in entry['row']:
            raise ValueError('Prospective prediction record changed or included an outcome')
        one=pd.DataFrame([entry['row']]);one.anchor_date=pd.to_datetime(one.anchor_date)
        validate_prediction_times(one,manifest,entry['logged_at_utc'])
        records.append(entry['row'])
    if not records:
        raise ValueError('No prospectively logged anchors; historical backfill is not an evaluation')
    if len(records)!=labels['expected_cohort_anchors']:
        raise ValueError('Prediction logging coverage does not match the complete Calendar cohort')
    if not all(type(row.get(b.TARGET)) is bool for row in labels['records']):
        raise ValueError('Outcome labels must be resolved true/false; unknown is not negative')
    frame=pd.DataFrame(records);truth=pd.DataFrame(labels['records'])
    for f in [frame,truth]:
        f.anchor_date=pd.to_datetime(f.anchor_date).dt.normalize()
        f.sales_record_id=f.sales_record_id.astype(str)
    frame=frame.merge(truth[KEYS+[b.TARGET]],on=KEYS,how='outer',validate='one_to_one',indicator=True)
    if not frame['_merge'].eq('both').all():
        raise ValueError('Prospective labels and logged anchors differ')
    frame['outcome_end_date']=frame.anchor_date+pd.Timedelta(days=30)
    frame['validation_group']=b.connected_validation_groups(frame)
    results={};predictions={}
    for name,artifact in models.items():
        probabilities=frame[name].astype(float)
        if not np.isfinite(probabilities).all() or not probabilities.between(0,1).all():
            raise ValueError('Invalid logged scores')
        results[name]={'metrics':b.score(frame[b.TARGET],probabilities,artifact['threshold']),
          'priority_top20pct':b.priority_review_metrics(frame[b.TARGET],probabilities,manifest['review_fraction']),
          'segments':segment_metrics(frame,probabilities,artifact['threshold'])}
        predictions[name]=frame[KEYS+[b.TARGET]].assign(probability=probabilities)
    names=list(models)
    interval=paired_intervals(frame,predictions[names[0]],predictions[names[1]])
    interval['direction']=names[1]+'_minus_'+names[0]
    result={'evaluated_at_utc':now.isoformat(),'cohort_start':manifest['cohort_start'],
      'cohort_end':manifest['cohort_end'],'rows':len(frame),'source_labels_sha256':digest(labels_path),
      'bundle_sha256':digest(output/'bundle.json'),'results':results,'paired_intervals':interval,
      'limits':['Complete-source coverage is a declared source contract, not proof of biological recurrence.',
        'Known customers may appear in both historical training and prospective services.',
        'The cohort must not be used to retune thresholds, feature sets or training emphasis.']}
    result_path.write_text(json.dumps(result,indent=2,allow_nan=False))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['freeze','verify','score','evaluate'])
    p.add_argument('--bundle-dir',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--input-json',type=Path)
    p.add_argument('--log-dir',type=Path,default=b.ROOT/'outputs/cp2-v2/prospective_callback_logs')
    args=p.parse_args()
    if args.mode=='freeze':result=freeze(args.bundle_dir)
    elif args.mode=='verify':result=verify(args.bundle_dir)
    elif args.mode=='score':
        if not args.input_json:p.error('score requires --input-json')
        result=score(args.bundle_dir,args.input_json,args.log_dir)
    else:
        if not args.input_json:p.error('evaluate requires Calendar outcomes in --input-json')
        result=evaluate(args.bundle_dir,args.input_json,args.log_dir)
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':main()
