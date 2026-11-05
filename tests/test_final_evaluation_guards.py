from datetime import datetime, timezone
import json
import pandas as pd
import pytest

from scripts import cp2_pipeline as pipeline
from scripts import cp2_model
from scripts import freeze_callback_prospective as prospective
from scripts import cp2_cloud_collector as cloud
from types import SimpleNamespace


def final_case(tmp_path, monkeypatch, *, missing=False, late=False, altered=False):
    base=tmp_path/'outputs/live';run_dir=base/'runs/case';run_dir.mkdir(parents=True)
    bundle=tmp_path/'outputs/bundle';bundle.mkdir(parents=True)
    (bundle/'bundle.json').write_text('{}')
    manifest={'cohort_start':'2026-10-01','cohort_end':'2026-10-27',
              'frozen_at_utc':'2026-09-30T00:00:00Z'}
    contract={'cohort_start':'2026-10-01','cohort_end':'2026-10-27',
        'earliest_final_evaluation_date':'2026-11-27','result_path':bundle/'result.json'}
    monkeypatch.setattr(pipeline,'ROOT',tmp_path);monkeypatch.setattr(pipeline,'BASE',base)
    monkeypatch.setattr(pipeline,'utcnow',lambda:datetime(2026,11,28,tzinfo=timezone.utc))
    monkeypatch.setattr(cp2_model,'current_bundle',lambda:({},bundle))
    monkeypatch.setattr(prospective,'load_bundle',lambda path:(manifest,{}))
    monkeypatch.setattr(prospective,'cohort_contract',lambda *args:contract)
    row={'population':'all_services','sales_record_id':'sale','anchor_date':'2026-10-01',
         'prediction_at':'2026-10-01T03:01:00Z','feature_snapshot_at':'2026-10-01T03:00:00Z',
         'service_start_at':'2026-10-01T02:00:00Z','service_end_at':'2026-10-01T03:00:00Z'}
    if late:row['prediction_at']='2026-10-01T03:08:00Z'
    event={'calendar_id':'calendar','event_id':'event','status':'confirmed','summary':'GPC 1/3',
           'start_raw':row['service_start_at'],'end_raw':row['service_end_at']}
    pipeline.atomic_json(run_dir/'calendar_private.json',{'records':[event]})
    source={'complete_outcomes_through':'2026-11-27','earliest_extraction_at_utc':'2026-11-28T00:00:00Z',
            'extracted_at_utc':'2026-11-28T00:01:00Z'}
    pipeline.atomic_json(run_dir/'source_receipt.json',source)
    pipeline.atomic_json(run_dir/'feature_receipt.json',{'complete_outcomes_through':'2026-11-27'})
    input_path=run_dir/'features/mature_labels/dataset_input.json'
    pipeline.atomic_json(input_path,{'fixture':True})
    monkeypatch.setattr(prospective.b,'load_dataset_input',lambda path:pd.DataFrame([row]))
    state={'status':'succeeded','run_id':'case','artifact_hashes':pipeline.artifacts(run_dir)}
    monkeypatch.setattr(pipeline,'run',lambda **kwargs:state)
    if altered:input_path.write_text('{"altered":true}')
    if not missing:
        key='all_services|sale|2026-10-01'
        entry={
               'schema_version':2,'bundle_sha256':pipeline.digest(bundle/'bundle.json'),
               'row':row,'logged_at_utc':row['prediction_at'],
               'source_receipt':{'source':prospective.SOURCE_NAME}}
        from scripts.audit_callback_evidence import calendar_window_key
        entry['source_receipt']['calendar_event_keys_by_prediction_key']={key:calendar_window_key(event)}
        entry['record_sha256']=prospective.record_digest(entry)
        pipeline.atomic_json(base/'prospective_logs/entry.json',entry)
    calls=[]
    monkeypatch.setattr(prospective,'prepare_labels',lambda *a,**k:calls.append('labels') or {'complete_cohort_anchors':1})
    monkeypatch.setattr(prospective,'evaluate',lambda *a,**k:calls.append('evaluate') or {'rows':1})
    return run_dir,calls,contract


@pytest.mark.parametrize('case', ['missing','late','altered'])
def test_final_evaluation_rejects_bad_evidence_before_labels(tmp_path,monkeypatch,case):
    run_dir,calls,_=final_case(tmp_path,monkeypatch,**{case:True})
    with pytest.raises(ValueError):pipeline.final_evaluation(cloud=True)
    assert calls==[]
    audit=json.loads((run_dir/'eligibility_drift_private.json').read_text())
    assert audit['status'].startswith('rejected')


def test_final_evaluation_audits_before_one_time_labels(tmp_path,monkeypatch):
    run_dir,calls,contract=final_case(tmp_path,monkeypatch)
    result=pipeline.final_evaluation(cloud=True)
    assert calls==['labels','evaluate'] and result['eligibility_drift_services']==0
    assert json.loads((run_dir/'eligibility_drift_private.json').read_text())['coverage_keys_agree']
    contract['result_path'].write_text('{}')
    with pytest.raises(ValueError,match='already recorded'):pipeline.final_evaluation(cloud=True)


def test_cloud_keeps_full_drift_audit_private_and_journal_sanitized(tmp_path):
    run_dir=tmp_path/'20261004T030000Z_01234567';run_dir.mkdir()
    (run_dir/'run.json').write_text(json.dumps({'run_id':run_dir.name,'status':'succeeded','stages':{}}))
    private={'status':'rejected_eligibility_drift','changed_services':1,
             'changes_private':[{'service_key':['private_customer','sale','2026-10-01']}]}
    (run_dir/'eligibility_drift_private.json').write_text(json.dumps(private))
    objects={}
    def blob(name):
        item=objects.setdefault(name,SimpleNamespace(payload=None))
        def upload(payload,**kwargs):
            assert kwargs['if_generation_match']==0
            item.payload=payload
        item.upload_from_string=upload
        return item
    bucket=SimpleNamespace(blob=blob,objects=objects)
    cloud.persist_run_journal(bucket,run_dir)
    full=[b.payload for key,b in bucket.objects.items() if '/eligibility_audit/' in key]
    journals=[b.payload for key,b in bucket.objects.items() if '/journal/' in key]
    assert len(full)==len(journals)==1
    assert b'private_customer' in full[0] and b'private_customer' not in journals[0]
