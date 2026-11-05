"""Read-only stratified Calendar evidence audit; never changes labels or scores."""
from pathlib import Path
from datetime import datetime,timezone
import json,re,hashlib
import pandas as pd
import nbformat
from google.cloud import bigquery
from scripts.research_callback_targets import digest
from scripts.reconcile_callback_evidence import clean_text,PESTS
from scripts.build_supervisor_model_review import execute,export_html

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261017_outcome_label_audit'
KEY=['population','sales_record_id','anchor_date']

def assess_event(row):
    title=clean_text(row.get('summary')).upper()
    if row.get('status')=='cancelled' or re.search(r'\b(?:CANCEL\w*|POSTPON\w*|RESCHEDUL\w*)\b',title):return 'schedule_change_needs_review'
    if re.search(r'\b(?:FREE|COMPLIMENTARY|FOC)\b',title):return 'free_visit_needs_review'
    if re.search(r'\b(?:WARRANTY|CLAIM|CALLBACK)\b',title):return 'explicit_return_title'
    stages=re.findall(r'\b(\d{1,2})\s*/\s*(\d{1,2})\b',title)
    if len(stages)==1:
        current,total=map(int,stages[0])
        if total>0 and current>total:return 'beyond_paid_sequence_needs_review'
        if 0<current<=total:return 'within_paid_sequence_needs_review'
    return 'unclear_return_evidence'

def main():
    OUT.mkdir(parents=True,exist_ok=True);assert not (OUT/'protocol.json').exists()
    predpath=ROOT/'outputs/model_validation/20261017_larger_frozen_test/test_predictions_private.csv'
    apath=ROOT/'outputs/cp2-v2/callback_evidence_reconciliation/source_private.json'
    fpath=ROOT/'outputs/model_validation/20261016_target_research/archived_facts_private.json'
    frozen=ROOT/'outputs/cp2-v2/prospective_callback_v2';before={p.name:digest(p) for p in frozen.iterdir() if p.is_file()}
    p=pd.read_csv(predpath);p.anchor_date=pd.to_datetime(p.anchor_date)
    anchors=pd.DataFrame(json.loads(apath.read_text())['rows']['anchors']);anchors.anchor_date=pd.to_datetime(anchors.anchor_date)
    assert not anchors.duplicated(KEY).any()
    joined=p.merge(anchors,on=KEY,how='inner',validate='one_to_one')
    consistent=joined.warranty_signal_within_30d.astype(bool).eq(joined.target.astype(bool))
    incompatible=int((~consistent).sum());joined=joined[consistent].copy()
    joined['stratum']=['TP' if y and z else 'FN' if y else 'FP' if z else 'TN' for y,z in zip(joined.target,joined.predicted_return)]
    joined['sample_order']=[hashlib.sha256(('|'.join(map(str,row))+'|label-audit-17017').encode()).hexdigest() for row in joined[KEY].itertuples(index=False,name=None)]
    sample=joined.sort_values('sample_order').groupby('stratum',group_keys=False).head(10).copy()
    facts=pd.read_json(fpath);facts.event_date_local=pd.to_datetime(facts.event_date_local)
    assert not facts.calendar_event_row.duplicated().any()
    cases=[];rowids=set()
    for idx,r in enumerate(sample.itertuples(),1):
        events=facts[(facts.sales_record_id==r.sales_record_id)&facts.event_date_local.gt(r.anchor_date)&facts.event_date_local.le(r.anchor_date+pd.Timedelta(days=30))]
        cases.append((f'CASE-{idx:02d}',r,events));rowids.add(int(r.anchor_event_row));rowids.update(events.calendar_event_row.astype(int))
    pin=json.loads((ROOT/'config/cp2_historical_callback_validation.json').read_text())
    protocol={'declared_utc':datetime.now(timezone.utc).isoformat(),'code_sha256':digest(Path(__file__)),'source_hashes':{str(x.relative_to(ROOT)):digest(x) for x in [predpath,apath,fpath]},'selection':'10 per TP/FN/FP/TN using deterministic SHA256 order; source/target-consistent subset only','sample_rows':len(sample),'matched_prediction_rows':len(joined),'unmatched_prediction_rows':len(p)-len(joined)-incompatible,'target_incompatible_rows':incompatible,'no_retraining_or_relabeling':True,'frozen_hashes':before}
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    client=bigquery.Client(project=pin['project'],location=pin['location'])
    sql=f"SELECT * FROM `{pin['project']}.{pin['calendar_table']}` WHERE calendar_event_row IN UNNEST(@rows)"
    config=bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter('rows','INT64',sorted(rowids))],maximum_bytes_billed=104857600)
    dry=client.query(sql,job_config=bigquery.QueryJobConfig(dry_run=True,query_parameters=config.query_parameters));assert dry.total_bytes_processed<=104857600
    job=client.query(sql,job_config=config);raw=[dict(row) for row in job.result(timeout=60)];client.close()
    assert len(raw)==len(rowids);byrow={r['calendar_event_row']:r for r in raw}
    (OUT/'calendar_evidence_private.json').write_text(json.dumps({'query':sql,'job_id':job.job_id,'bytes_processed':job.total_bytes_processed,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'rows':raw},indent=2))
    records=[];details=[]
    for case,r,events in cases:
        anchor=byrow[int(r.anchor_event_row)]
        assert anchor['summary']==r.summary
        assert pd.to_datetime(anchor['start_raw'],utc=True).tz_convert('Asia/Kuala_Lumpur').date()==r.anchor_date.date()
        assert anchor['end_raw']==r.end_raw
        returns=events[events.warranty_claim_candidate.eq(True)]
        replay=bool(len(returns));assert replay==bool(r.target)
        signals=[];same_pest=0;unknown_pest=0
        anchor_pests={name for name,pat in PESTS.items() if re.search(pat,clean_text(anchor['summary'])+' '+clean_text(anchor['description']),re.I)}
        all_events=[]
        for e in events.itertuples():
            raw_event=byrow[int(e.calendar_event_row)]
            assert pd.to_datetime(raw_event['start_raw'],utc=True).tz_convert('Asia/Kuala_Lumpur').date()==e.event_date_local.date()
            evidence=assess_event(raw_event)
            if bool(e.warranty_claim_candidate):
                signals.append(evidence)
                pests={name for name,pat in PESTS.items() if re.search(pat,clean_text(raw_event['summary'])+' '+clean_text(raw_event['description']),re.I)}
                same_pest+=int(bool(pests&anchor_pests));unknown_pest+=int(not pests or not anchor_pests)
            all_events.append({'date':str(e.event_date_local.date()),'candidate_return':bool(e.warranty_claim_candidate),'evidence':evidence,'title':raw_event['summary'],'raw_status':raw_event['status']})
        flags=[x for x in signals if x!='explicit_return_title']
        unlabelled_explicit=sum(not e['candidate_return'] and e['evidence']=='explicit_return_title' for e in all_events)
        state='Review needed' if flags or unlabelled_explicit else ('Explicit return record supports positive' if replay else 'No flagged return in archived 30-day records')
        records.append({'Case':case,'Model result':r.stratum,'Recorded return':bool(r.target),'Evidence finding':state,'Flagged return events':len(returns),'Other bookings in window':len(events)-len(returns),'Same-pest text overlap events':same_pest,'Unknown-pest evidence events':unknown_pest,'Unlabelled explicit returns':int(unlabelled_explicit),'Reasons':'; '.join(sorted(set(flags)))})
        details.append({'case':case,'sales_record_id':r.sales_record_id,'anchor_date':str(r.anchor_date.date()),'anchor_title':r.summary,'following_events':all_events})
    pd.DataFrame(records).to_csv(OUT/'sample_findings.csv',index=False)
    (OUT/'case_details_private.json').write_text(json.dumps(details,indent=2))
    summary={'checked_utc':datetime.now(timezone.utc).isoformat(),'sample':len(records),'by_prediction_stratum':pd.Series([r['Model result'] for r in records]).value_counts().to_dict(),'source_identity_checks_passed':True,'label_replay_all_matched':True,'findings':pd.Series([r['Evidence finding'] for r in records]).value_counts().to_dict(),'original_model_unchanged':before=={p.name:digest(p) for p in frozen.iterdir() if p.is_file()},'scope':'Archive source audit. Does not establish actual completion, same-pest causality, formal warranty eligibility, or absence of unrecorded returns. Stratified sample not population error rate.'}
    assert summary['original_model_unchanged'];(OUT/'audit_summary.json').write_text(json.dumps(summary,indent=2))
    count=pd.DataFrame(records).groupby(['Model result','Evidence finding']).size().reset_index(name='Cases')
    md=nbformat.v4.new_markdown_cell;code=nbformat.v4.new_code_cell
    nb=nbformat.v4.new_notebook(cells=[md('# Are the recorded model outcomes believable?\n\nWe checked 40 service windows: ten correct return warnings, ten missed returns, ten false warnings and ten correct no-return predictions. Selection was deterministic, rather than choosing interesting examples. This audit checks source evidence; it cannot prove that a visit happened or that an unrecorded return did not occur.'),code('import pandas as pd\nfrom io import StringIO\n'+f'display(pd.read_json(StringIO({count.to_json(orient="records")!r})))'),md('## Case findings\n\nCase numbers avoid customer names. “Explicit return record” supports a recorded return outcome; it does not establish a formal warranty claim. Sequence-only, cancelled/rescheduled and free visits require review. Same-pest text overlap is a screening clue only.'),code(f'display(pd.read_json(StringIO({pd.DataFrame(records).to_json(orient="records")!r})))'),md('## Verdict\n\nThe event-based labels replay correctly when joined to their archived source identities. That is a consistency check, not an independent proof of correct labels. Any flagged cases must be resolved before making a clean-label performance claim. No labels, predictions or frozen model files were changed. Results apply to this stratified source-matched sample; do not quote an overall population label-accuracy percentage.\n\nThe outcome should be described as a **recorded pest-related return candidate within 30 days** until same-pest purpose, completion and warranty status are sufficiently verified. Calendar booking evidence cannot establish biological recurrence or actual completion.\n\nFresh current records and later owner corrections are separate evidence; they cannot silently rewrite this frozen historical experiment. Original prediction gaps also remain recorded. Notebook executed in Python; native Jupyter kernel unavailable.')])
    nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
    execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'Outcome_Label_Audit.ipynb');export_html(nb,OUT/'Outcome_Label_Audit.html')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
