from datetime import datetime,timedelta,timezone
import json
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from scripts import benchmark_warranty_models as b
from scripts import freeze_callback_prospective as p
from scripts.compare_flood_models import configure_contracts


@pytest.fixture(autouse=True)
def isolated_contracts(monkeypatch,tmp_path):
    monkeypatch.setattr(b,'ROOT',tmp_path)
    monkeypatch.setattr(b,'CATEGORICAL',list(b.CATEGORICAL))
    monkeypatch.setattr(b,'FEATURE_SETS',{k:list(v) for k,v in b.FEATURE_SETS.items()})
    monkeypatch.setattr(b,'FLOOD_CONTEXT_ENABLED',b.FLOOD_CONTEXT_ENABLED)
    monkeypatch.setattr(b,'REPORTED_FLOOD_CONTEXT_ENABLED',b.REPORTED_FLOOD_CONTEXT_ENABLED)


def raw_fixture():
    configure_contracts(False)
    columns=set(b.KEYS+b.BASE_NUMERIC+b.CATEGORICAL+b.WEATHER_NUMERIC+b.ENVIRONMENT_NUMERIC+b.LANDCOVER_NUMERIC)
    f=pd.DataFrame({col:[np.nan] for col in columns})
    f['population']='matched_packages_recorded_callback_30d';f['sales_record_id']='fixture'
    f['anchor_date']='2026-09-28';f['outcome_end_date']='2026-10-28'
    f['pest_category']='Lipas dan semut';f['package_category']='3x';f['premise_type']='Residential'
    f['service_number']=1;f['package_sessions_recorded']=3
    for col in ['prior_property_warranty_claims','prior_property_service_events','prior_package_warranty_claims','prior_package_service_events']:
        f[col]=0
    f['prediction_at']='2026-09-28T11:01:00+08:00'
    f['feature_snapshot_at']='2026-09-28T10:50:00+08:00'
    f['service_start_at']='2026-09-28T10:00:00+08:00'
    f['service_end_at']='2026-09-28T11:00:00+08:00'
    return f


def manifest_fixture():
    return {'frozen_at_utc':'2026-09-27T09:00:00+00:00',
      'cohort_start':'2026-09-28','cohort_end':'2026-10-27',
      'models':{'model':{'features':['anchor_is_first','anchor_is_mixed_pest']}}}


def source_receipt(input_path):
    return {'source':p.SOURCE_NAME,'extracted_at_utc':'2026-09-28T10:49:00+08:00',
      'prediction_generated_at_utc':'2026-09-28T11:01:00+08:00','run_id':'fixture-run',
      'snapshot_sha256':'a'*64,'feature_input_sha256':p.digest(input_path)}


def test_predictors_do_not_require_or_retain_an_outcome():
    raw=raw_fixture().drop(columns=[b.TARGET])
    out=p.prepare_scoring_frame(raw)
    assert b.TARGET not in out
    assert out.anchor_is_mixed_pest.iloc[0]==1
    other=p.prepare_scoring_frame(raw.assign(**{b.TARGET:True}))
    pd.testing.assert_frame_equal(out,other)
    with pytest.raises(ValueError,match='missing contracted'):
        b.prepare_frame(raw)


def test_prospective_dates_require_available_snapshot_and_service_end():
    f=p.prepare_scoring_frame(raw_fixture());m=manifest_fixture()
    now=p.timestamp('2026-09-28T11:02:00+08:00')
    p.validate_prediction_times(f,m,now)
    with pytest.raises(ValueError,match='availability'):
        p.validate_prediction_times(f.assign(feature_snapshot_at='2026-09-28T11:02:00+08:00'),m,now)
    with pytest.raises(ValueError,match='service end'):
        p.validate_prediction_times(f.assign(service_end_at='2026-09-28T11:03:00+08:00'),m,now)
    with pytest.raises(ValueError,match='backfill'):
        p.validate_prediction_times(f,m,now+timedelta(minutes=5))


def test_cross_midnight_service_keeps_calendar_start_anchor():
    f=p.prepare_scoring_frame(raw_fixture()).assign(service_start_at='2026-09-28T23:00:00+08:00',
      service_end_at='2026-09-29T00:30:00+08:00',prediction_at='2026-09-29T00:31:00+08:00')
    p.validate_prediction_times(f,manifest_fixture(),p.timestamp('2026-09-29T00:32:00+08:00'))


def test_timezone_and_cohort_boundaries_are_required():
    with pytest.raises(ValueError,match='Timezone'):
        p.timestamp('2026-09-28T11:00:00')
    f=p.prepare_scoring_frame(raw_fixture()).assign(anchor_date=pd.Timestamp('2026-09-27'))
    with pytest.raises(ValueError,match='outside'):
        p.validate_prediction_times(f,manifest_fixture(),p.timestamp('2026-09-28T11:02:00+08:00'))


def test_freeze_does_not_overwrite_existing_bundle(tmp_path):
    (tmp_path/'bundle.json').write_text('{}')
    with pytest.raises(ValueError,match='already exists'):
        p.freeze(tmp_path)


def test_real_scoring_logs_unknown_outcome_and_retries_preserve_first_commit(tmp_path,monkeypatch):
    raw=raw_fixture().drop(columns=[b.TARGET]);input_path=tmp_path/'input.json'
    input_path.write_text(raw.to_json(orient='records'))
    manifest=manifest_fixture();(tmp_path/'bundle.json').write_text(json.dumps(manifest))
    class Pipeline:
        def predict_proba(self,frame):
            assert b.TARGET not in frame
            return np.array([[.75,.25]])
    models={'model':{'features':['anchor_is_first','anchor_is_mixed_pest'],
                     'pipeline':Pipeline(),'calibrator':None}}
    monkeypatch.setattr(p,'load_bundle',lambda output:(manifest,models))
    fixed=p.timestamp('2026-09-28T11:02:00+08:00')
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:fixed,fromisoformat=datetime.fromisoformat))
    logs=tmp_path/'outputs/logs';receipt=source_receipt(input_path)
    assert p.score(tmp_path,input_path,logs,source_receipt=receipt)['logged_rows']==1
    record=json.loads(next(logs.glob('*.json')).read_text())
    assert record['label_status']=='awaiting_calendar_30d_outcome'
    assert b.TARGET not in record['row']
    assert record['row']['model']==.25
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:fixed+timedelta(hours=1),fromisoformat=datetime.fromisoformat))
    assert p.score(tmp_path,input_path,logs,source_receipt=receipt)['already_logged_rows']==1
    assert json.loads(next(logs.glob('*.json')).read_text())==record
    receipt['snapshot_sha256']='b'*64
    with pytest.raises(ValueError,match='already logged'):
        p.score(tmp_path,input_path,logs,source_receipt=receipt)


def test_evaluation_waits_until_after_full_inclusive_window(tmp_path,monkeypatch):
    manifest=manifest_fixture()|{'earliest_final_evaluation_date':'2026-11-27'}
    monkeypatch.setattr(p,'load_bundle',lambda output:(manifest,{}))
    fixed=p.timestamp('2026-11-26T23:59:00+08:00')
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:fixed,fromisoformat=datetime.fromisoformat))
    with pytest.raises(ValueError,match='not matured'):
        p.evaluate(tmp_path/'outputs',tmp_path/'missing_labels.json',tmp_path/'outputs/logs')


def test_mature_evaluation_requires_complete_resolved_calendar_labels(tmp_path,monkeypatch):
    tmp_path=tmp_path/'outputs';tmp_path.mkdir()
    manifest=manifest_fixture()|{'earliest_final_evaluation_date':'2026-11-27','review_fraction':.2}
    (tmp_path/'bundle.json').write_text(json.dumps(manifest))
    models={name:{'threshold':.5} for name in ['reference','challenger']}
    monkeypatch.setattr(p,'load_bundle',lambda output:(manifest,models))
    fixed=p.timestamp('2026-11-27T01:00:00+08:00')
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:fixed,fromisoformat=datetime.fromisoformat))
    row=json.loads(p.prepare_scoring_frame(raw_fixture().drop(columns=[b.TARGET])).to_json(orient='records',date_format='iso'))[0]
    row.update(reference=.25,challenger=.35)
    record={'logged_at_utc':'2026-09-28T11:02:00+08:00','bundle_sha256':p.digest(tmp_path/'bundle.json'),
            'row':row,'label_status':'awaiting_calendar_30d_outcome'}
    record['record_sha256']=p.record_digest(record)
    logs=tmp_path/'logs';logs.mkdir();(logs/'record.json').write_text(json.dumps(record))
    truth={k:row[k] for k in p.KEYS}|{b.TARGET:True}
    labels={'date_authority':'Calendar','cohort_complete':True,'calendar_coverage_through':'2026-11-26',
            'expected_cohort_anchors':1,'records':[truth]}
    path=tmp_path/'labels.json'
    path.write_text(json.dumps(labels|{'calendar_coverage_through':'2026-11-25'}))
    with pytest.raises(ValueError,match='incomplete'):
        p.evaluate(tmp_path,path,logs)
    path.write_text(json.dumps(labels|{'records':[truth|{b.TARGET:None}]}))
    with pytest.raises(ValueError,match='unknown is not negative'):
        p.evaluate(tmp_path,path,logs)
    path.write_text(json.dumps(labels))
    result=p.evaluate(tmp_path,path,logs)
    assert result['rows']==1
    assert result['results']['challenger']['priority_top20pct']['recall']==1
    with pytest.raises(ValueError,match='already recorded'):
        p.evaluate(tmp_path,path,logs)


def test_logged_feature_tampering_changes_integrity_digest():
    record={'row':{'service_number':1},'logged_at_utc':'2026-09-28T00:00:00Z'}
    record['record_sha256']=p.record_digest(record)
    assert record['record_sha256']==p.record_digest(record)
    record['row']['service_number']=2
    assert record['record_sha256']!=p.record_digest(record)


def scoring_setup(tmp_path,monkeypatch,raw=None):
    raw=raw if raw is not None else raw_fixture().drop(columns=[b.TARGET])
    path=tmp_path/'input.json';path.write_text(raw.to_json(orient='records'))
    manifest=manifest_fixture();(tmp_path/'bundle.json').write_text(json.dumps(manifest))
    class Pipeline:
        def predict_proba(self,frame):return np.tile([.75,.25],(len(frame),1))
    artifact={'features':['anchor_is_first','anchor_is_mixed_pest'],'pipeline':Pipeline(),'calibrator':None}
    monkeypatch.setattr(p,'load_bundle',lambda output:(manifest,{'model':artifact}))
    fixed=p.timestamp('2026-09-28T11:02:00+08:00')
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:fixed,fromisoformat=datetime.fromisoformat))
    return path,source_receipt(path),tmp_path/'outputs/logs'


def test_source_receipt_binds_exact_input_and_precedes_feature_snapshot(tmp_path,monkeypatch):
    path,receipt,logs=scoring_setup(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='Source receipt'):
        p.score(tmp_path,path,logs)
    with pytest.raises(ValueError,match='exact predictor'):
        p.score(tmp_path,path,logs,source_receipt=receipt|{'feature_input_sha256':'c'*64})
    with pytest.raises(ValueError,match='source receipt timing'):
        p.score(tmp_path,path,logs,source_receipt=receipt|{'extracted_at_utc':'2026-09-28T10:51:00+08:00'})
    assert not list(logs.glob('*.json'))


def test_score_rejects_public_logs_and_target_window_already_started(tmp_path,monkeypatch):
    raw=raw_fixture().drop(columns=[b.TARGET]).assign(service_start_at='2026-09-28T23:00:00+08:00',
      service_end_at='2026-09-29T00:00:00+08:00',prediction_at='2026-09-29T00:01:00+08:00',
      feature_snapshot_at='2026-09-29T00:00:30+08:00')
    path,receipt,logs=scoring_setup(tmp_path,monkeypatch,raw)
    receipt.update(extracted_at_utc='2026-09-29T00:00:00+08:00',prediction_generated_at_utc='2026-09-29T00:01:00+08:00')
    now=p.timestamp('2026-09-29T00:02:00+08:00')
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:now,fromisoformat=datetime.fromisoformat))
    with pytest.raises(ValueError,match='ignored'):
        p.score(tmp_path,path,tmp_path/'public',source_receipt=receipt)
    with pytest.raises(ValueError,match='first local day'):
        p.score(tmp_path,path,logs,source_receipt=receipt)


def test_failed_batch_commit_can_resume_without_overwriting_or_partial_json(tmp_path,monkeypatch):
    raw=raw_fixture().drop(columns=[b.TARGET]);other=raw.assign(sales_record_id='fixture-2')
    path,receipt,logs=scoring_setup(tmp_path,monkeypatch,pd.concat([raw,other],ignore_index=True))
    original=p.atomic_create_json;calls=0
    def interrupted(destination,payload):
        nonlocal calls
        calls+=1
        if calls==2:raise OSError('simulated process failure')
        original(destination,payload)
    monkeypatch.setattr(p,'atomic_create_json',interrupted)
    with pytest.raises(OSError,match='simulated'):p.score(tmp_path,path,logs,source_receipt=receipt)
    files=list(logs.glob('*.json'));assert len(files)==1
    preserved=files[0].read_bytes();json.loads(preserved)
    monkeypatch.setattr(p,'atomic_create_json',original)
    result=p.score(tmp_path,path,logs,source_receipt=receipt)
    assert result['logged_rows']==1 and result['already_logged_rows']==1
    assert files[0].read_bytes()==preserved
    assert len(list(logs.glob('*.json')))==2
    assert not list(logs.glob('.pending-*'))


def test_writer_lock_is_exclusive_and_releases_after_failure(tmp_path):
    directory=tmp_path/'outputs/logs'
    with p.append_lock(directory):
        with pytest.raises(ValueError,match='busy'):
            with p.append_lock(directory):pass
    with p.append_lock(directory):pass


def test_full_batch_is_validated_before_first_commit(tmp_path,monkeypatch):
    raw=raw_fixture().drop(columns=[b.TARGET]);other=raw.assign(sales_record_id='fixture-2',service_end_at='2026-09-28T10:00:00+08:00')
    path,receipt,logs=scoring_setup(tmp_path,monkeypatch,pd.concat([raw,other],ignore_index=True))
    with pytest.raises(ValueError,match='service end'):
        p.score(tmp_path,path,logs,source_receipt=receipt)
    assert not list(logs.glob('*.json'))


def test_inference_crossing_actual_commit_gate_rejects_before_logging(tmp_path,monkeypatch):
    path,receipt,logs=scoring_setup(tmp_path,monkeypatch)
    clock=[p.timestamp('2026-09-28T11:02:00+08:00')]
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:clock[0],fromisoformat=datetime.fromisoformat))
    def slow_inference(artifact,frame):
        clock[0]=p.timestamp('2026-09-28T11:06:00+08:00')
        return np.full(len(frame),.25)
    monkeypatch.setattr(p,'artifact_probability',slow_inference)
    with pytest.raises(ValueError,match='service end'):
        p.score(tmp_path,path,logs,source_receipt=receipt)
    assert not list(logs.glob('*.json'))


def test_prepare_labels_requires_mature_full_calendar_coverage_and_resolved_truth(tmp_path,monkeypatch):
    manifest=manifest_fixture()|{'version':'prospective_callback_v2_corrected','earliest_final_evaluation_date':'2026-11-27'}
    monkeypatch.setattr(p,'load_bundle',lambda output:(manifest,{}))
    fixed=p.timestamp('2026-11-27T12:00:00+08:00')
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:fixed,fromisoformat=datetime.fromisoformat))
    rows=[{'population':'matched_packages_recorded_callback_30d','sales_record_id':'x','anchor_date':'2026-09-28',
      'outcome_end_date':'2026-10-28',b.TARGET:True}]
    path=tmp_path/'labels_input.json';path.write_text(json.dumps(rows))
    receipt={'source':p.SOURCE_NAME,'extracted_at_utc':'2026-11-27T11:00:00+08:00',
      'snapshot_sha256':'a'*64,'feature_input_sha256':p.digest(path),'complete_calendar_inventory':True,
      'calendar_coverage_start':'2000-01-01','complete_outcomes_through':'2026-11-26'}
    out=tmp_path/'outputs/labels.json'
    with pytest.raises(ValueError,match='completed-day'):
        p.prepare_labels(tmp_path,path,receipt|{'complete_outcomes_through':'2026-11-25'},out)
    with pytest.raises(ValueError,match='completed-day'):
        p.prepare_labels(tmp_path,path,receipt|{'complete_calendar_inventory':False},out)
    path.write_text(json.dumps([rows[0]|{b.TARGET:None}]))
    receipt['feature_input_sha256']=p.digest(path)
    with pytest.raises(ValueError,match='Unresolved'):
        p.prepare_labels(tmp_path,path,receipt,out)
    path.write_text(json.dumps(rows));receipt['feature_input_sha256']=p.digest(path)
    result=p.prepare_labels(tmp_path,path,receipt,out)
    assert result['complete_cohort_anchors']==1 and result['positive_anchors']==1
    payload=json.loads(out.read_text());assert payload['records'][0][b.TARGET] is True
    with pytest.raises(ValueError,match='already exist'):p.prepare_labels(tmp_path,path,receipt,out)


def test_v2_source_linked_logs_join_final_labels_and_reject_modified_truth(tmp_path,monkeypatch):
    bundle=tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    manifest=manifest_fixture()|{'version':'prospective_callback_v2_corrected',
      'earliest_final_evaluation_date':'2026-11-27','review_fraction':.2}
    manifest['models']={name:{'features':['anchor_is_first','anchor_is_mixed_pest']}
      for name in ['reference','challenger']}
    (bundle/'bundle.json').write_text(json.dumps(manifest))
    class Pipeline:
        def predict_proba(self,frame):return np.tile([.75,.25],(len(frame),1))
    models={name:{'features':info['features'],'pipeline':Pipeline(),'calibrator':None,'threshold':.5}
      for name,info in manifest['models'].items()}
    monkeypatch.setattr(p,'load_bundle',lambda output:(manifest,models))
    clock=[p.timestamp('2026-09-28T11:02:00+08:00')]
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:clock[0],fromisoformat=datetime.fromisoformat))
    input_path=tmp_path/'predictors.json';raw=raw_fixture().drop(columns=[b.TARGET])
    input_path.write_text(raw.to_json(orient='records'))
    logs=tmp_path/'outputs/logs'
    p.score(bundle,input_path,logs,source_receipt=source_receipt(input_path))
    clock[0]=p.timestamp('2026-11-27T12:00:00+08:00')
    labeled=tmp_path/'truth.json';raw.assign(**{b.TARGET:True}).to_json(labeled,orient='records')
    receipt={'source':p.SOURCE_NAME,'extracted_at_utc':'2026-11-27T11:00:00+08:00',
      'snapshot_sha256':'a'*64,'feature_input_sha256':p.digest(labeled),'complete_calendar_inventory':True,
      'calendar_coverage_start':'2000-01-01','complete_outcomes_through':'2026-11-26'}
    labels=tmp_path/'outputs/labels.json';p.prepare_labels(bundle,labeled,receipt,labels)
    original=labels.read_bytes();payload=json.loads(original);payload['records'][0][b.TARGET]=False
    labels.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='labels changed'):
        p.evaluate(bundle,labels,logs)
    labels.write_bytes(original)
    result=p.evaluate(bundle,labels,logs)
    assert result['rows']==1 and result['results']['challenger']['priority_top20pct']['recall']==1
    with pytest.raises(ValueError,match='already recorded'):p.evaluate(bundle,labels,logs)


def test_repaired_protocol_preserves_bundle_and_requires_complete_new_cohort(tmp_path,monkeypatch):
    bundle=tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    manifest=manifest_fixture()|{'version':'prospective_callback_v2_corrected',
      'target':'recorded_corrective_calendar_callback_within_30d',
      'earliest_final_evaluation_date':'2026-11-27','review_fraction':.2}
    manifest['models']={name:{'features':['anchor_is_first','anchor_is_mixed_pest']}
      for name in ['reference','challenger']}
    (bundle/'bundle.json').write_text(json.dumps(manifest))
    class Pipeline:
        def predict_proba(self,frame):return np.tile([.75,.25],(len(frame),1))
    models={name:{'features':info['features'],'pipeline':Pipeline(),'calibrator':None,'threshold':.5}
      for name,info in manifest['models'].items()}
    monkeypatch.setattr(p,'load_bundle',lambda output:(manifest,models))
    protocol={'schema_version':1,'name':'cp2_repaired_2026',
      'declared_at_utc':'2026-09-29T13:00:00Z','cohort_start':'2026-09-30',
      'cohort_end':'2026-10-27','earliest_final_evaluation_date':'2026-11-27',
      'bundle_sha256':p.digest(bundle/'bundle.json'),'target':manifest['target'],
      'date_authority':'Calendar'}
    protocol['record_sha256']=p.record_digest(protocol)
    protocol_path=tmp_path/'protocol.json';protocol_path.write_text(json.dumps(protocol))
    clock=[p.timestamp('2026-09-28T11:02:00+08:00')]
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:clock[0],fromisoformat=datetime.fromisoformat))
    logs=tmp_path/'outputs/logs'
    raws=[]
    for day in ['28','30']:
        raw=raw_fixture().drop(columns=[b.TARGET]).assign(sales_record_id='sale-'+day)
        for column in ['anchor_date','outcome_end_date','prediction_at','feature_snapshot_at',
                'service_start_at','service_end_at']:
            raw[column]=raw[column].str.replace('2026-09-28','2026-09-'+day,regex=False)
        if day=='30':
            raw['outcome_end_date']='2026-10-30'
        raws.append(raw)
        clock[0]=p.timestamp(f'2026-09-{day}T11:02:00+08:00')
        input_path=tmp_path/f'input-{day}.json';input_path.write_text(raw.to_json(orient='records'))
        receipt=source_receipt(input_path)
        for field in ['extracted_at_utc','prediction_generated_at_utc']:
            receipt[field]=receipt[field].replace('2026-09-28','2026-09-'+day)
        assert p.score(bundle,input_path,logs,source_receipt=receipt)['logged_rows']==1
    clock[0]=p.timestamp('2026-11-27T12:00:00+08:00')
    truth=pd.concat([raw.assign(**{b.TARGET:True}) for raw in raws],ignore_index=True)
    truth_path=tmp_path/'truth.json';truth.to_json(truth_path,orient='records')
    receipt={'source':p.SOURCE_NAME,'extracted_at_utc':'2026-11-27T11:00:00+08:00',
      'snapshot_sha256':'a'*64,'feature_input_sha256':p.digest(truth_path),
      'complete_calendar_inventory':True,'calendar_coverage_start':'2000-01-01',
      'complete_outcomes_through':'2026-11-26'}
    labels=tmp_path/'outputs/repaired_labels.json'
    with pytest.raises(ValueError,match='completed-day'):
        p.prepare_labels(bundle,truth_path,receipt|{'complete_outcomes_through':'2026-11-25'},
          labels,protocol_path=protocol_path)
    assert p.prepare_labels(bundle,truth_path,receipt,labels,protocol_path=protocol_path)['complete_cohort_anchors']==1
    assert json.loads(labels.read_text())['records'][0]['sales_record_id']=='sale-30'
    changed=protocol|{'cohort_start':'2026-10-01'}
    protocol_path.write_text(json.dumps(changed))
    with pytest.raises(ValueError,match='protocol'):
        p.evaluate(bundle,labels,logs,protocol_path=protocol_path)
    protocol_path.write_text(json.dumps(protocol))
    (bundle/'bundle.json').write_text(json.dumps(manifest,indent=2))
    with pytest.raises(ValueError,match='protocol'):
        p.evaluate(bundle,labels,logs,protocol_path=protocol_path)
    (bundle/'bundle.json').write_text(json.dumps(manifest))
    new_log=next(path for path in logs.glob('*.json') if
      json.loads(path.read_text())['row']['sales_record_id']=='sale-30')
    record=json.loads(new_log.read_text());new_log.unlink()
    with pytest.raises(ValueError,match='coverage|No prospectively'):
        p.evaluate(bundle,labels,logs,protocol_path=protocol_path)
    record['logged_at_utc']='2026-09-30T11:07:00+08:00'
    record['record_sha256']=p.record_digest(record);new_log.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='backfill|service end'):
        p.evaluate(bundle,labels,logs,protocol_path=protocol_path)
    record['logged_at_utc']='2026-09-30T11:02:00+08:00'
    record['record_sha256']=p.record_digest(record);new_log.write_text(json.dumps(record))
    result=p.evaluate(bundle,labels,logs,protocol_path=protocol_path)
    assert result['rows']==1 and result['cohort_start']=='2026-09-30'
    assert (bundle/'prospective_repaired_evaluation.json').exists()
    assert not (bundle/'prospective_evaluation.json').exists()
    with pytest.raises(ValueError,match='already recorded'):
        p.evaluate(bundle,labels,logs,protocol_path=protocol_path)


def test_registered_repaired_protocol_hash_rejects_changed_file(tmp_path):
    bundle=tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    manifest=manifest_fixture()|{'target':'recorded_corrective_calendar_callback_within_30d',
      'earliest_final_evaluation_date':'2026-11-27'}
    (bundle/'bundle.json').write_text(json.dumps(manifest))
    protocol={'schema_version':1,'name':'cp2_repaired_2026',
      'declared_at_utc':'2026-09-29T13:00:00Z','cohort_start':'2026-09-30',
      'cohort_end':'2026-10-27','earliest_final_evaluation_date':'2026-11-27',
      'bundle_sha256':p.digest(bundle/'bundle.json'),'target':manifest['target'],
      'date_authority':'Calendar'}
    protocol['record_sha256']=p.record_digest(protocol)
    config=tmp_path/'config';config.mkdir()
    path=config/'cp2_repaired_cohort.json';path.write_text(json.dumps(protocol))
    (config/'cp2_model_current.json').write_text(json.dumps({
      'repaired_cohort_protocol_sha256':p.digest(path)}))
    assert p.cohort_contract(bundle,manifest,path)['cohort_start']=='2026-09-30'
    protocol['eligibility']='changed after declaration'
    protocol['record_sha256']=p.record_digest(protocol)
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError,match='registered immutable hash'):
        p.cohort_contract(bundle,manifest,path)


def test_registered_cloud_protocol_is_separate_and_immutable(tmp_path):
    bundle=tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    manifest=manifest_fixture()|{'target':'recorded_corrective_calendar_callback_within_30d',
      'earliest_final_evaluation_date':'2026-11-27'}
    (bundle/'bundle.json').write_text(json.dumps(manifest))
    protocol={'schema_version':1,'name':'cp2_cloud_2026',
      'declared_at_utc':'2026-09-30T03:55:43Z','cohort_start':'2026-10-01',
      'cohort_end':'2026-10-27','earliest_final_evaluation_date':'2026-11-27',
      'bundle_sha256':p.digest(bundle/'bundle.json'),'target':manifest['target'],
      'date_authority':'Calendar'}
    protocol['record_sha256']=p.record_digest(protocol)
    config=tmp_path/'config';config.mkdir()
    path=config/'cp2_cloud_cohort.json';path.write_text(json.dumps(protocol))
    (config/'cp2_model_current.json').write_text(json.dumps({
      'cloud_cohort_protocol_sha256':p.digest(path)}))
    contract=p.cohort_contract(bundle,manifest,path)
    assert contract['cohort_start']=='2026-10-01'
    assert contract['result_path'].name=='prospective_cloud_evaluation.json'
    protocol['eligibility']='changed after declaration'
    protocol['record_sha256']=p.record_digest(protocol)
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError,match='immutable hash'):
        p.cohort_contract(bundle,manifest,path)
