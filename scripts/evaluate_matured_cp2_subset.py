"""Read-only partial outcome assessment; never calls or writes final evaluation.
Use only immutable, timely receipts and verified mature source-derived outcomes.
"""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
from scripts import cp2_pipeline as pipeline
from scripts import freeze_callback_prospective as prospective
from scripts import audit_callback_evidence as audit
from scripts import benchmark_warranty_models as b
ROOT=pipeline.ROOT
OUT=ROOT/'outputs/project_audit/20261101_outcome_repair'

def is_mature(anchor_date,complete_through):
    return pd.Timestamp(anchor_date).normalize()+pd.Timedelta(days=30)<=pd.Timestamp(complete_through).normalize()

def check_entry(entry,manifest,bundle,collection=None):
    if entry.get('record_sha256')!=prospective.record_digest(entry):raise ValueError('Prediction receipt hash changed')
    if entry.get('bundle_sha256')!=prospective.digest(bundle/'bundle.json'):raise ValueError('Model bundle differs')
    if entry.get('schema_version')!=2 or entry['source_receipt'].get('source')!=prospective.SOURCE_NAME:raise ValueError('Source-bound receipt required')
    if b.TARGET in entry['row']:raise ValueError('Prediction includes outcome')
    row=entry['row'];source=entry['source_receipt'];logged=prospective.timestamp(entry['logged_at_utc'])
    if not prospective.timestamp(source['extracted_at_utc'])<=prospective.timestamp(row['feature_snapshot_at'])<=prospective.timestamp(row['prediction_at'])<=logged:raise ValueError('Source/prediction ordering changed')
    if prospective.timestamp(source['prediction_generated_at_utc'])!=prospective.timestamp(row['prediction_at']):raise ValueError('Prediction timestamps differ')
    if collection is not None and source.get('collection_protocol_sha256')!=collection['protocol_sha256']:raise ValueError('Collection hash differs')
    frame=pd.DataFrame([row]);frame.anchor_date=pd.to_datetime(frame.anchor_date)
    prospective.validate_prediction_times(frame,manifest,entry['logged_at_utc'],collection_protocol=collection)

def main():
    registry=pipeline.read(ROOT/'config/cp2_model_current.json');bundle=ROOT/registry['bundle_relative_path']
    manifest,_=prospective.load_bundle(bundle)
    contract=prospective.cohort_contract(bundle,manifest,ROOT/'config/cp2_october10_cohort.json');collection=contract['collection_protocol']
    source=pipeline.read(OUT/'source_receipt.json');features=pipeline.read(OUT/'feature_receipt.json')
    if source['complete_calendar_inventory'] is not True:raise ValueError('Incomplete Calendar inventory')
    extracted=prospective.timestamp(source['extracted_at_utc'])
    if extracted>pipeline.utcnow() or pd.Timestamp(source['complete_outcomes_through']).date()>=extracted.astimezone(pipeline.LOCAL).date():raise ValueError('Outcome watermark includes an incomplete day')
    if source['complete_outcomes_through']!=features['complete_outcomes_through']:raise ValueError('Watermarks differ')
    for key,file in [('calendar_sha256','calendar_private.json'),('sheets_sha256','sheets_private.json')]:
        if source[key]!=pipeline.digest(OUT/file):raise ValueError('Fresh source changed')
    inp=OUT/'features/mature_labels/dataset_input.json'
    if features['mature_input_sha256']!=pipeline.digest(inp):raise ValueError('Labels changed')
    truth=b.load_dataset_input(inp);truth_by_key={audit.service_key(r):r for r in truth.to_dict('records')}
    if len(truth_by_key)!=len(truth):raise ValueError('Duplicate label keys')
    events=pipeline.read(OUT/'calendar_private.json')['records'];windows={audit.calendar_window_key(r):r for r in events}
    old=pipeline.read(ROOT/'outputs/cp2-v2/source_refresh_20260927/old_calendar_private.json')['records']
    stable={(r['calendar_id'],r['event_id']):r['calendar_event_row'] for r in old}
    receipts=pipeline.read(ROOT/'outputs/project_audit/20261101_evaluation_status/receipts_private.json')
    seen=set();kept=[];excluded=[]
    for entry in receipts:
        key=audit.service_key(entry['row'])
        if not is_mature(key[2],source['complete_outcomes_through']):continue
        reason=None
        try:
            check_entry(entry,manifest,bundle,collection if entry['source_receipt'].get('collection_protocol_sha256') else None)
            if key in seen:raise ValueError('Duplicate service prediction')
            seen.add(key)
            event=windows.get(audit.bound_window_key(entry,key))
            if event is None:raise ValueError('Original Calendar window missing or moved')
            if str(event.get('status','')).lower()=='cancelled' or str(event.get('summary','')).upper().startswith(('CANCELLED','CANCELED','HOLD')):raise ValueError('Source now cancelled or on hold')
            row=truth_by_key.get(key)
            if row is None or pd.isna(row.get(b.TARGET)):raise ValueError('No resolved mature label')
            identity=(event['calendar_id'],event['event_id'])
            event_row=stable.get(identity,-int(hashlib.sha256(json.dumps(identity,separators=(',',':')).encode()).hexdigest()[:15],16)-1)
            if int(row['anchor_event_row'])!=event_row:raise ValueError('Outcome anchor differs from original prediction appointment')
            kept.append({'service_key':key,'outcome':bool(row[b.TARGET]),'probability':float(entry['row'][registry['primary_bundle_model']])})
        except ValueError as e:excluded.append({'service_key':key,'reason':str(e)})
    result={'scope':'Partial matured receipt subset; not complete-cohort evaluation','complete_outcomes_through':source['complete_outcomes_through'],'valid_matched_receipts':len(kept),'excluded_mature_receipts':len(excluded),'excluded_private':excluded,'bundle_sha256':registry['bundle_sha256'],'source_sha256':pipeline.digest(OUT/'source_receipt.json'),'label_input_sha256':pipeline.digest(inp),'final_evaluation_run':False,'backfill':False}
    if kept:
        y=np.array([r['outcome'] for r in kept]);prob=np.array([r['probability'] for r in kept]);threshold=manifest['models'][registry['primary_bundle_model']]['threshold'];pred=prob>=threshold
        result['metrics']={'rows':len(y),'positives':int(y.sum()),'accuracy':float(np.mean(y==pred)),'precision':float(np.sum(y&pred)/pred.sum()) if pred.any() else None,'recall':float(np.sum(y&pred)/y.sum()) if y.any() else None,'always_no_return_accuracy':float(np.mean(~y)),'true_positive':int(np.sum(y&pred)),'false_positive':int(np.sum(~y&pred)),'false_negative':int(np.sum(y&~pred)),'true_negative':int(np.sum(~y&~pred)),'frozen_threshold':threshold}
    pipeline.atomic_json(OUT/'partial_evaluation.json',result);pipeline.atomic_json(OUT/'partial_matched_private.json',kept)
    print(json.dumps({k:v for k,v in result.items() if k!='excluded_private'},indent=2))
if __name__=='__main__':main()
