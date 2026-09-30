"""Freeze all-mature-data callback models and append prospective feature/score logs.

No live Calendar/sheet/warehouse writes. Refit models have no measured future
performance. Historical replay is separate from real prospective recording.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from zoneinfo import ZoneInfo
import joblib
import numpy as np
import pandas as pd
try:
    from scripts import benchmark_warranty_models as b
    from scripts.compare_callback_blind_spots import add_targeted_features,fit_pipeline,masks,segment_metrics
    from scripts.callback_evaluation import paired_intervals
    from scripts.compare_flood_models import configure_contracts
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    from compare_callback_blind_spots import add_targeted_features,fit_pipeline,masks,segment_metrics
    from callback_evaluation import paired_intervals
    from compare_flood_models import configure_contracts

LOCAL=ZoneInfo('Asia/Kuala_Lumpur')
DEFAULT_OUTPUT=b.ROOT/'outputs/cp2-v2/prospective_callback_v1'
INPUT=b.ROOT/'outputs/cp2-v2/model_callback_normalized_pest/dataset_input.json'
KEYS=['population','sales_record_id','anchor_date']
SOURCE_NAME='Google Calendar + Google Sheets'


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


def private_path(path):
    path=Path(path).resolve()
    if not path.is_relative_to((b.ROOT/'outputs').resolve()):
        raise ValueError('Customer-level prospective evidence must stay in ignored project outputs')
    return path


@contextmanager
def append_lock(directory):
    """OS-held lock releases after a process crash; a leftover file is harmless."""
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'.append.lock').open('a+b') as handle:
        if handle.tell()==0:
            handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            lock=lambda:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            unlock=lambda:msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            lock=lambda:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            unlock=lambda:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
        try:lock()
        except OSError as error:
            raise ValueError('Prospective evidence writer is busy; retry the same input') from error
        try:yield
        finally:unlock()


def atomic_create_json(path,payload):
    """Publish a fully flushed file without exposing partial JSON or overwriting."""
    path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,name=tempfile.mkstemp(prefix='.pending-',suffix='.tmp',dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as handle:
            json.dump(payload,handle,indent=2,allow_nan=False)
            handle.flush();os.fsync(handle.fileno())
        # Atomic hard-link creation fails if another process already committed.
        os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)


def validate_source_receipt(receipt,input_path,now,*,outcomes=False):
    if not isinstance(receipt,dict) or receipt.get('source')!=SOURCE_NAME:
        raise ValueError('Source receipt for Google Calendar + Google Sheets required')
    for field in ['snapshot_sha256','feature_input_sha256']:
        if not re.fullmatch('[0-9a-f]{64}',str(receipt.get(field,''))):
            raise ValueError('Source receipt requires valid SHA256 fingerprints')
    if digest(input_path)!=receipt['feature_input_sha256']:
        raise ValueError('Source receipt and exact predictor/label input differ')
    extracted=timestamp(receipt['extracted_at_utc'])
    if extracted>timestamp(now):raise ValueError('Source extraction cannot be in the future')
    minimum=timestamp(receipt.get('source_extraction_min_at_utc',extracted))
    maximum=timestamp(receipt.get('source_extraction_max_at_utc',extracted))
    if minimum>maximum or maximum!=extracted:
        raise ValueError('Source extraction receipt ordering differs')
    if not outcomes:
        generated=timestamp(receipt['prediction_generated_at_utc'])
        if not extracted<=generated<=timestamp(now):
            raise ValueError('Source extraction must finish before prediction generation')
        if not isinstance(receipt.get('run_id'),str) or not receipt['run_id'].strip():
            raise ValueError('Source receipt requires a pipeline run identifier')
    return extracted


def prepare_scoring_frame(raw,preparation=None):
    raw=raw.copy()
    raw['outcome_end_date']=pd.to_datetime(raw.anchor_date)+pd.Timedelta(days=30)
    # Outcomes may be absent: never synthesize a false/no-callback label.
    frame=add_targeted_features(b.prepare_frame(raw,require_outcomes=False))
    if preparation=='candidate_v5':
        try:
            from scripts.compare_callback_candidates_v2 import add_contract_policy_feature
        except ModuleNotFoundError:
            from compare_callback_candidates_v2 import add_contract_policy_feature
        frame=add_contract_policy_feature(frame)
    return frame


def artifact_probability(artifact,frame):
    if 'members' in artifact:
        try:
            from scripts.compare_callback_candidates_v2 import predict_raw
        except ModuleNotFoundError:
            from compare_callback_candidates_v2 import predict_raw
        raw=predict_raw(artifact['members'],frame)
    else:
        raw=artifact['pipeline'].predict_proba(frame[artifact['features']])[:,1]
    return b.apply_calibrator(artifact['calibrator'],raw)


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
        if (not service_start<=service_end<=prediction or (prediction-service_end).total_seconds()>300
                or (now-service_end).total_seconds()>300):
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
        # The frozen manifest was written on Windows; Cloud Run uses POSIX paths.
        if digest(b.ROOT/relative.replace('\\','/'))!=expected_hash:
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


def cohort_contract(output, manifest, protocol_path=None):
    """Keep the original frozen cohort or validate a predeclared narrower cohort."""
    if protocol_path is None:
        return {'cohort_start':manifest['cohort_start'], 'cohort_end':manifest['cohort_end'],
            'earliest_final_evaluation_date':manifest['earliest_final_evaluation_date'],
            'result_path':output/'prospective_evaluation.json', 'protocol_sha256':None}
    path=Path(protocol_path)
    registered={
        (b.ROOT/'config/cp2_repaired_cohort.json').resolve():
            ('repaired_cohort_protocol_sha256','cp2_repaired_2026',
             'prospective_repaired_evaluation.json'),
        (b.ROOT/'config/cp2_cloud_cohort.json').resolve():
            ('cloud_cohort_protocol_sha256','cp2_cloud_2026',
             'prospective_cloud_evaluation.json')}
    registry_key,name,result_name=registered.get(path.resolve(),
        (None,'cp2_repaired_2026','prospective_repaired_evaluation.json'))
    if registry_key:
        registry=json.loads((b.ROOT/'config/cp2_model_current.json').read_text(encoding='utf-8'))
        if registry.get(registry_key)!=digest(path):
            raise ValueError('Cohort protocol differs from registered immutable hash')
    protocol=json.loads(path.read_text(encoding='utf-8'))
    start=pd.Timestamp(protocol['cohort_start']);end=pd.Timestamp(protocol['cohort_end'])
    declared=timestamp(protocol['declared_at_utc'])
    if (protocol.get('schema_version')!=1 or protocol.get('name')!=name
            or protocol.get('record_sha256')!=record_digest(protocol)
            or protocol.get('bundle_sha256')!=digest(output/'bundle.json')
            or protocol.get('target')!=manifest['target']
            or protocol.get('date_authority')!='Calendar'
            or not pd.Timestamp(manifest['cohort_start'])<=start<=end==pd.Timestamp(manifest['cohort_end'])
            or declared>=start.tz_localize(LOCAL).tz_convert('UTC').to_pydatetime()
            or protocol.get('earliest_final_evaluation_date')!=manifest['earliest_final_evaluation_date']):
        raise ValueError('Repaired cohort protocol or frozen model contract differs')
    return {'cohort_start':protocol['cohort_start'], 'cohort_end':protocol['cohort_end'],
        'earliest_final_evaluation_date':protocol['earliest_final_evaluation_date'],
        'result_path':output/result_name,
        'protocol_sha256':digest(path)}


def verify(output):
    configure_contracts(False);manifest,models=load_bundle(output)
    replay_input=b.ROOT/manifest['training_input_relative_path'] if 'training_input_relative_path' in manifest else INPUT
    if digest(replay_input)!=manifest['input_file_sha256'] or digest(output/manifest['training_replay_file'])!=manifest['training_replay_sha256']:
        raise ValueError('Replay inputs changed')
    raw=b.load_dataset_input(replay_input).drop(columns=[b.TARGET])
    frame=prepare_scoring_frame(raw,manifest.get('preparation'))
    if b.TARGET in frame:
        raise ValueError('Outcome entered prospective predictors')
    expected=pd.read_csv(output/manifest['training_replay_file'],dtype={'sales_record_id':str})
    keys=frame[KEYS].copy();keys.anchor_date=keys.anchor_date.dt.strftime('%Y-%m-%d')
    differences={}
    for name,artifact in models.items():
        p=artifact_probability(artifact,frame)
        joined=keys.assign(replayed=p).merge(expected[KEYS+[name]],on=KEYS,how='outer',validate='one_to_one',indicator=True)
        if not joined['_merge'].eq('both').all() or not np.allclose(joined.replayed,joined[name],rtol=0,atol=1e-12):
            raise ValueError('Bundle predictor-only replay failed')
        differences[name]=float(abs(joined.replayed-joined[name]).max())
    return {'rows':len(frame),'max_probability_difference':differences,'outcome_required_for_scoring':False}


def score(output,input_path,log_dir,*,source_receipt=None):
    log_dir=private_path(log_dir)
    configure_contracts(False);manifest,models=load_bundle(output)
    frame=prepare_scoring_frame(b.load_dataset_input(input_path),manifest.get('preparation'))
    now=datetime.now(timezone.utc)
    extracted=validate_source_receipt(source_receipt,input_path,now)
    generated=timestamp(source_receipt['prediction_generated_at_utc'])
    for row in frame.to_dict('records'):
        if timestamp(row['prediction_at'])!=generated or not extracted<=timestamp(row['feature_snapshot_at'])<=generated:
            raise ValueError('Logged prediction and feature snapshot must match source receipt timing')
        if generated.astimezone(LOCAL).date()>row['anchor_date'].date():
            raise ValueError('Prediction must precede the first local day of the callback outcome window')
    for name,artifact in models.items():
        frame[name]=artifact_probability(artifact,frame)
        if not np.isfinite(frame[name]).all() or not frame[name].between(0,1).all():
            raise ValueError('Scoring produced an invalid probability')
    feature_columns=sorted({c for info in manifest['models'].values() for c in info['features']}
      | {'service_number','pest_distinct_known_types','normalized_pest_category'})
    rows=json.loads(frame[KEYS+['address_hash','prediction_at','feature_snapshot_at','service_start_at','service_end_at']+feature_columns+list(models)].to_json(orient='records',date_format='iso'))
    pending=[];existing_count=0
    with append_lock(log_dir):
        # Inference/lock acquisition can cross the five-minute or midnight
        # boundary. Timestamp the actual commit phase and validate it again.
        now=datetime.now(timezone.utc)
        for row in rows:
            key='|'.join(str(row[k]) for k in KEYS)
            path=log_dir/(hashlib.sha256(key.encode()).hexdigest()+'.json')
            record={'schema_version':2,'logged_at_utc':now.isoformat(),'bundle_sha256':digest(output/'bundle.json'),
              'source_receipt':source_receipt,'row':row,'label_status':'awaiting_calendar_30d_outcome'}
            record['record_sha256']=record_digest(record)
            if path.exists():
                prior=json.loads(path.read_text(encoding='utf-8'))
                if prior.get('record_sha256')!=record_digest(prior):
                    raise ValueError('Existing prospective record integrity failure')
                # Idempotent retries preserve the FIRST timestamp and evidence.
                fields=['schema_version','bundle_sha256','source_receipt','row','label_status']
                if any(prior.get(field)!=record.get(field) for field in fields):
                    raise ValueError('Prediction already logged with different immutable evidence')
                earlier=pd.DataFrame([row]);earlier.anchor_date=pd.to_datetime(earlier.anchor_date)
                validate_prediction_times(earlier,manifest,prior['logged_at_utc'])
                existing_count+=1
                continue
            one=pd.DataFrame([row]);one.anchor_date=pd.to_datetime(one.anchor_date)
            validate_prediction_times(one,manifest,now)
            if now.astimezone(LOCAL).date()>one.anchor_date.iloc[0].date():
                raise ValueError('Prediction commit must precede the first local outcome day')
            pending.append((path,record))
        # Validate the entire batch before committing any new row. If a process
        # dies between atomic commits, rerunning the EXACT input safely resumes.
        for path,record in pending:
            # Cloud Run has an ephemeral filesystem. Commit the immutable receipt
            # to private object storage before acknowledging a local write.
            bucket_name=os.getenv('NOMOBUG_CP2_COLLECTOR_BUCKET')
            if bucket_name:
                from google.cloud import storage
                object_name='prospective_logs/'+path.name
                payload=json.dumps(record,indent=2,allow_nan=False).encode('utf-8')
                storage.Client().bucket(bucket_name).blob(object_name).upload_from_string(
                    payload,content_type='application/json',if_generation_match=0)
            atomic_create_json(path,record)
    return {'logged_rows':len(pending),'already_logged_rows':existing_count,'models':list(models),
      'performance':'not_available_until_mature_outcomes'}


def prepare_labels(output,input_path,source_receipt,labels_path,*,protocol_path=None):
    """Create final labels from a fresh, complete source-derived mature dataset."""
    labels_path=private_path(labels_path)
    manifest,_=load_bundle(output);contract=cohort_contract(output,manifest,protocol_path)
    now=datetime.now(timezone.utc)
    if now.astimezone(LOCAL).date()<pd.Timestamp(contract['earliest_final_evaluation_date']).date():
        raise ValueError('Prospective cohort and inclusive 30-day outcomes have not matured')
    extracted=validate_source_receipt(source_receipt,input_path,now,outcomes=True)
    last_outcome=pd.Timestamp(contract['cohort_end'])+pd.Timedelta(days=30)
    coverage=pd.Timestamp(source_receipt['complete_outcomes_through'])
    if (source_receipt.get('complete_calendar_inventory') is not True
            or pd.Timestamp(source_receipt['calendar_coverage_start'])>pd.Timestamp(contract['cohort_start'])
            or coverage<last_outcome
            or coverage.date()>extracted.astimezone(LOCAL).date()-timedelta(days=1)):
        raise ValueError('Full Calendar inventory and completed-day outcome coverage required')
    raw=b.load_dataset_input(input_path)
    required=KEYS+[b.TARGET]
    if not set(required).issubset(raw):raise ValueError('Source-derived dataset lacks outcome keys')
    raw=raw.copy();raw.anchor_date=pd.to_datetime(raw.anchor_date).dt.normalize()
    raw=raw[raw.anchor_date.between(pd.Timestamp(contract['cohort_start']),pd.Timestamp(contract['cohort_end']))]
    if raw[required].isna().any().any() or raw.duplicated(KEYS).any():
        raise ValueError('Unresolved or duplicate Calendar cohort outcomes')
    if not all(type(value) in [bool,np.bool_] for value in raw[b.TARGET]):
        raise ValueError('Outcome labels must be resolved true/false; unknown is not negative')
    if 'outcome_end_date' in raw and not pd.to_datetime(raw.outcome_end_date).eq(raw.anchor_date+pd.Timedelta(days=30)).all():
        raise ValueError('Source-derived outcome horizon differs from the frozen 30-day target')
    if raw.empty:raise ValueError('No complete prospective cohort anchors in source dataset')
    truth=raw[required].copy();truth.sales_record_id=truth.sales_record_id.astype(str)
    truth.anchor_date=truth.anchor_date.dt.strftime('%Y-%m-%d')
    labels={'schema_version':2,'date_authority':'Calendar','cohort_complete':True,
      'cohort_start':contract['cohort_start'],'cohort_end':contract['cohort_end'],
      'calendar_coverage_through':coverage.strftime('%Y-%m-%d'),'expected_cohort_anchors':len(truth),
      'source_receipt':source_receipt,'prepared_at_utc':now.isoformat(),
      'records':json.loads(truth.to_json(orient='records'))}
    if protocol_path is not None:
        labels['repaired_protocol_sha256']=contract['protocol_sha256']
    labels['record_sha256']=record_digest(labels)
    with append_lock(labels_path.parent):
        if labels_path.exists():raise ValueError('Prepared prospective labels already exist')
        atomic_create_json(labels_path,labels)
    return {'labels_path':str(labels_path),'complete_cohort_anchors':len(truth),
      'positive_anchors':int(raw[b.TARGET].sum()),'source_input_sha256':digest(input_path)}


def evaluate(output,labels_path,log_dir,*,protocol_path=None):
    private_path(output);log_dir=private_path(log_dir)
    manifest,models=load_bundle(output);contract=cohort_contract(output,manifest,protocol_path)
    now=datetime.now(timezone.utc)
    if now.astimezone(LOCAL).date()<pd.Timestamp(contract['earliest_final_evaluation_date']).date():
        raise ValueError('Prospective cohort and inclusive 30-day outcomes have not matured')
    result_path=contract['result_path']
    if result_path.exists():
        raise ValueError('Final prospective evaluation already recorded; do not repeatedly tune this cohort')
    labels=json.loads(labels_path.read_text())
    if labels.get('date_authority')!='Calendar' or labels.get('cohort_complete') is not True:
        raise ValueError('Complete Calendar-derived cohort outcomes required')
    last_outcome=pd.Timestamp(contract['cohort_end'])+pd.Timedelta(days=30)
    if pd.Timestamp(labels['calendar_coverage_through'])<last_outcome:
        raise ValueError('Calendar coverage is incomplete for the full outcome window')
    if manifest.get('version','').startswith('prospective_callback_v2'):
        receipt=labels.get('source_receipt',{})
        if labels.get('record_sha256')!=record_digest(labels):
            raise ValueError('Prepared outcome labels changed after source derivation')
        if (labels.get('schema_version')!=2 or receipt.get('source')!=SOURCE_NAME
                or receipt.get('complete_calendar_inventory') is not True
                or labels.get('cohort_start')!=contract['cohort_start']
                or labels.get('cohort_end')!=contract['cohort_end']
                or labels.get('repaired_protocol_sha256')!=contract['protocol_sha256']
                or pd.Timestamp(receipt.get('calendar_coverage_start','2100-01-01'))>pd.Timestamp(contract['cohort_start'])
                or pd.Timestamp(receipt.get('complete_outcomes_through','1900-01-01'))<last_outcome):
            raise ValueError('Source-derived prospective v2 labels and coverage receipt required')
        for field in ['snapshot_sha256','feature_input_sha256']:
            if not re.fullmatch('[0-9a-f]{64}',str(receipt.get(field,''))):
                raise ValueError('Outcome source fingerprints required')
        extracted=timestamp(receipt['extracted_at_utc'])
        if (extracted>now or pd.Timestamp(labels['calendar_coverage_through']).date()>
                extracted.astimezone(LOCAL).date()-timedelta(days=1)):
            raise ValueError('Outcome coverage must contain completed days before source extraction')
    records=[]
    for path in sorted(log_dir.glob('*.json')):
        entry=json.loads(path.read_text())
        if entry.get('bundle_sha256')!=digest(output/'bundle.json'):
            continue
        if entry.get('record_sha256')!=record_digest(entry) or b.TARGET in entry['row']:
            raise ValueError('Prospective prediction record changed or included an outcome')
        if manifest.get('version','').startswith('prospective_callback_v2'):
            receipt=entry.get('source_receipt',{})
            if entry.get('schema_version')!=2 or receipt.get('source')!=SOURCE_NAME:
                raise ValueError('Source-linked prospective v2 prediction receipt required')
            extracted=timestamp(receipt['extracted_at_utc'])
            prediction=timestamp(entry['row']['prediction_at'])
            if (not extracted<=timestamp(entry['row']['feature_snapshot_at'])<=prediction
                    or timestamp(receipt['prediction_generated_at_utc'])!=prediction
                    or prediction.astimezone(LOCAL).date()>pd.Timestamp(entry['row']['anchor_date']).date()
                    or timestamp(entry['logged_at_utc']).astimezone(LOCAL).date()>pd.Timestamp(entry['row']['anchor_date']).date()):
                raise ValueError('Prospective source/prediction timing differs')
        one=pd.DataFrame([entry['row']]);one.anchor_date=pd.to_datetime(one.anchor_date)
        validate_prediction_times(one,manifest,entry['logged_at_utc'])
        if one.anchor_date.between(pd.Timestamp(contract['cohort_start']),
                pd.Timestamp(contract['cohort_end'])).all():
            records.append(entry['row'])
    if not records:
        raise ValueError('No prospectively logged anchors; historical backfill is not an evaluation')
    if type(labels.get('expected_cohort_anchors')) is not int or len(labels['records'])!=labels['expected_cohort_anchors']:
        raise ValueError('Calendar outcome records and declared cohort size differ')
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
    frame=frame.sort_values(KEYS,kind='stable').reset_index(drop=True)
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
    result={'evaluated_at_utc':now.isoformat(),'cohort_start':contract['cohort_start'],
      'cohort_end':contract['cohort_end'],'rows':len(frame),'source_labels_sha256':digest(labels_path),
      'bundle_sha256':digest(output/'bundle.json'),'results':results,'paired_intervals':interval,
      'limits':['Complete-source coverage is a declared source contract, not proof of biological recurrence.',
        'Known customers may appear in both historical training and prospective services.',
        'The cohort must not be used to retune thresholds, feature sets or training emphasis.']}
    if protocol_path is not None:
        result['repaired_protocol_sha256']=contract['protocol_sha256']
    with append_lock(output):
        if result_path.exists():raise ValueError('Final prospective evaluation already recorded')
        atomic_create_json(result_path,result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['freeze','verify','score','prepare-labels','evaluate'])
    p.add_argument('--bundle-dir',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--input-json',type=Path)
    p.add_argument('--source-receipt',type=Path)
    p.add_argument('--output-json',type=Path)
    p.add_argument('--log-dir',type=Path,default=b.ROOT/'outputs/cp2-v2/prospective_callback_logs')
    args=p.parse_args()
    if args.mode=='freeze':result=freeze(args.bundle_dir)
    elif args.mode=='verify':result=verify(args.bundle_dir)
    elif args.mode=='score':
        if not args.input_json or not args.source_receipt:p.error('score requires --input-json and --source-receipt')
        result=score(args.bundle_dir,args.input_json,args.log_dir,
          source_receipt=json.loads(args.source_receipt.read_text(encoding='utf-8')))
    elif args.mode=='prepare-labels':
        if not args.input_json or not args.source_receipt or not args.output_json:
            p.error('prepare-labels requires --input-json, --source-receipt and --output-json')
        result=prepare_labels(args.bundle_dir,args.input_json,
          json.loads(args.source_receipt.read_text(encoding='utf-8')),args.output_json)
    else:
        if not args.input_json:p.error('evaluate requires Calendar outcomes in --input-json')
        result=evaluate(args.bundle_dir,args.input_json,args.log_dir)
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':main()
