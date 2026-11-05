"""Bounded, read-only reconstruction of changed Calendar keys from Bronze."""
import json
import re
from pathlib import Path
from google.cloud import bigquery
from scripts.cp2_pipeline_tick import event_key


def run():
    root=Path('outputs/project_audit/20261015_resolution')
    report=json.loads((root/'candidate_review_private.json').read_text(encoding='utf-8'))
    targets=[r['event_key'] for r in report['reviews'] if r['current_reconstruction']=='current_calendar_key_missing']
    inventory=json.loads((root/'reporting_calendar_inventory.json').read_text(encoding='utf-8'))
    client=bigquery.Client(project='profound-keel-500007-s4',location='asia-southeast1');matches=[]
    try:
        for run_id,table in inventory:
            if not re.fullmatch('calendar_events_[a-f0-9]{64}',table):raise ValueError('Invalid immutable table')
            sql=f'''SELECT calendar_id,event_id,start_raw,end_raw,summary,status,created_raw,updated_raw
                FROM `profound-keel-500007-s4.bronze.{table}`
                WHERE LOWER(TO_HEX(SHA256(CONCAT(calendar_id,'|',event_id,'|',start_raw,'|',end_raw)))) IN UNNEST(@keys)'''
            params=[bigquery.ArrayQueryParameter('keys','STRING',targets)]
            dry=client.query(sql,job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False,query_parameters=params))
            if (dry.total_bytes_processed or 0)>104857600:raise ValueError('Query exceeds 100 MiB')
            job=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=104857600,query_parameters=params))
            matches.extend({'reporting_run':run_id,'source_table':table,'event_key':event_key(dict(row)),**dict(row)}
                for row in job.result(timeout=120))
    finally:client.close()
    current=json.loads(Path('outputs/project_audit/20261015_non_dashboard/source_check/calendar_private.json').read_text(encoding='utf-8'))
    by_id={(r['calendar_id'],r['event_id']):r for r in current['records']}
    changes=[]
    for key in targets:
        found=[r for r in matches if r['event_key']==key]
        if not found:changes.append({'event_key':key,'status':'no_retained_snapshot_match'});continue
        original=found[0];latest=by_id.get((original['calendar_id'],original['event_id']))
        changes.append({'event_key':key,'status':'same_event_rescheduled' if latest and event_key(latest)!=key
            else 'event_absent_now' if not latest else 'unchanged',
            'original':original,'current':latest,'matching_snapshot_count':len(found)})
    (root/'calendar_key_changes_private.json').write_text(json.dumps(changes,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'reviewed_missing_keys':len(targets),'statuses':[r['status'] for r in changes]}))


if __name__=='__main__':run()
