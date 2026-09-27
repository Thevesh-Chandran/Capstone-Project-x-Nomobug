"""Derive a private refreshed callback candidate using temporary BigQuery tables.

Production tables and frozen model inputs remain unchanged. Stable old event
row IDs retain reviewed labels/geocodes; new rows get distinct IDs. Complete
outcome coverage ends on the day BEFORE extraction, never an in-progress day.
"""
from __future__ import annotations
import argparse
from datetime import date,datetime,timedelta
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
try:
    from scripts import benchmark_warranty_models as b
    from scripts.load_calendar_bronze import FIELDS
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    from load_calendar_bronze import FIELDS

OLD_TABLE='calendar_events_78147d417f3d97d3c1d9ef0be59638fd7850e4195108e1fc7b879483c7f35b66'
LOCAL=ZoneInfo('Asia/Kuala_Lumpur')


def compare_replay(expected,actual,tolerance=1e-12):
    keys=['population','sales_record_id','anchor_date']
    if set(expected)!=set(actual):raise ValueError('Corrected replay schema differs')
    a=expected.sort_values(keys,kind='stable').reset_index(drop=True)
    z=actual.sort_values(keys,kind='stable').reset_index(drop=True)
    if len(a)!=len(z) or not a[keys].equals(z[keys]):raise ValueError('Corrected replay cohort differs')
    variations={}
    for column in a:
        if pd.api.types.is_float_dtype(a[column]) and pd.api.types.is_numeric_dtype(z[column]):
            if not np.allclose(a[column],z[column],rtol=0,atol=tolerance,equal_nan=True):
                raise ValueError('Corrected replay numeric features differ')
            difference=float((a[column]-z[column]).abs().max())
            if difference>0:variations[column]=difference
        elif not a[column].equals(z[column]):
            raise ValueError('Corrected replay keys, labels or categorical/count features differ')
    return {'numeric_absolute_tolerance':tolerance,'floating_variations':variations}


def complete_through(metadata):
    extracted=datetime.fromisoformat(metadata['extracted_at'].replace('Z','+00:00'))
    if extracted.tzinfo is None:
        raise ValueError('Source extraction timestamp must have timezone')
    return min(date.fromisoformat(metadata['window_end']),extracted.astimezone(LOCAL).date()-timedelta(days=1))


def source_delta(old,new):
    key=lambda row:(row['calendar_id'],row['event_id'])
    a={key(row):row for row in old['records']}; z={key(row):row for row in new['records']}
    if len(a)!=len(old['records']) or len(z)!=len(new['records']):
        raise ValueError('Duplicate Calendar identity')
    if old['metadata']['window_start']!=new['metadata']['window_start']:
        raise ValueError('Snapshots must cover the same historical start')
    if new['metadata']['calendar_count']!=old['metadata']['calendar_count'] or {k[0] for k in a}!={k[0] for k in z}:
        raise ValueError('Approved source Calendar inventory differs')
    if len({row['calendar_event_row'] for row in a.values()})!=len(a):
        raise ValueError('Old source row IDs are not unique')
    maximum=max(row['calendar_event_row'] for row in a.values())
    delta=[]; invalid_geocodes=[]; changed=[]
    for k in sorted(z):
        row=dict(z[k])
        if k in a:
            row['calendar_event_row']=a[k]['calendar_event_row']
            if all(row.get(field)==a[k].get(field) for field in FIELDS):
                continue
            changed.append(k)
            if any(row.get(f)!=a[k].get(f) for f in ['description','location']):
                invalid_geocodes.append(row['calendar_event_row'])
        else:
            maximum+=1;row['calendar_event_row']=maximum
        delta.append(row)
    replaced=[a[k]['calendar_event_row'] for k in set(a)-set(z)]+[r['calendar_event_row'] for r in delta if r['calendar_event_row']<=max(v['calendar_event_row'] for v in a.values())]
    return delta,replaced,invalid_geocodes,{'old_rows':len(a),'new_rows':len(z),'new_event_ids':len(set(z)-set(a)),
        'absent_event_ids':len(set(a)-set(z)),'updated_event_ids':len(changed),'invalidated_old_geocodes':len(invalid_geocodes)}


def candidate_sql(delta,replaced,invalid_geocodes,watermark):
    compiled=b.ROOT/'dbt/target/compiled/nomobug/models'
    columns=[]
    for field in FIELDS:
        expression=f"JSON_VALUE(item,'$.{field}')"
        if field=='calendar_event_row':expression=f'CAST({expression} AS INT64)'
        if field=='is_all_day':expression=f'CAST({expression} AS BOOL)'
        columns.append(f'{expression} AS {field}')
    raw=f"CREATE TEMP TABLE fresh_raw AS SELECT {','.join(FIELDS)} FROM `{b.PROJECT}.bronze.{OLD_TABLE}` WHERE calendar_event_row NOT IN UNNEST(@replaced) UNION ALL SELECT "+','.join(columns)+" FROM UNNEST(JSON_QUERY_ARRAY(@delta)) AS item;"
    replacements={f'`{b.PROJECT}`.`bronze`.`{OLD_TABLE}`':'fresh_raw'}
    statements=[raw];hashes={}
    stages=[('calendar_events','calendar_events.sql','silver'),('calendar_event_matches','calendar_event_matches.sql','silver'),
        ('calendar_event_locations','calendar_event_locations.sql','silver'),('calendar_service_event_facts','gold/calendar_service_event_facts.sql','gold'),
        ('warranty_anchor_environment_features','analytics_ml/warranty_anchor_environment_features.sql','analytics_ml'),
        ('warranty_callback_fixed_horizon_dataset','analytics_ml/warranty_callback_fixed_horizon_dataset.sql','analytics_ml')]
    for name,path,schema in stages:
        source=(compiled/path).read_text(encoding='utf-8');hashes[path]=hashlib.sha256(source.encode()).hexdigest()
        for old_name,new_name in replacements.items():source=source.replace(old_name,new_name)
        if name=='calendar_event_locations':
            source+= '\n AND e.calendar_event_row NOT IN UNNEST(@invalid_geocodes)'
        if name=='calendar_service_event_facts':
            source=f'SELECT f.*, ST_GEOHASH(f.service_geography,4) AS _area_geohash4 FROM ({source}) f'
        if name=='warranty_callback_fixed_horizon_dataset':
            source,count=re.subn(r'with observation as \(.*?\), uncertain_packages as \(',
                f"with observation as (select DATE '{watermark.isoformat()}' as observed_through), uncertain_packages as (",source,flags=re.S)
            if count!=1:raise ValueError('Unexpected observation watermark SQL; stop for review')
            if 'h.event_created_ts <= a.event_end_ts' not in source:
                source,count=re.subn(r'on h\.event_date_local < a\.event_date_local',
                    'on h.event_date_local < a.event_date_local\n     and h.event_created_ts <= a.event_end_ts',source)
                if count!=1:raise ValueError('Unexpected history SQL; stop for review')
            # Equi-joins avoid the expensive package/property/area OR join.
            # UNION DISTINCT counts each linked event once even when it shares
            # more than one key with an anchor.
            source=re.sub(r'st_geohash\((h|a)\.service_geography, 4\)',r'\1._area_geohash4',source)
            if 'history_links as (' not in source:
                availability='h.event_date_local < a.event_date_local AND h.event_created_ts <= a.event_end_ts'
                links=[]
                for relation in ['h.sales_record_id = a.sales_record_id',
                        'h.address_hash = a.address_hash',
                        'h._area_geohash4 = a._area_geohash4 AND h.event_date_local >= DATE_SUB(a.event_date_local, INTERVAL 90 DAY)']:
                    links.append(f'SELECT a.calendar_event_row AS anchor_row,h.calendar_event_row AS history_row FROM anchors a JOIN fresh_calendar_service_event_facts h ON {relation} AND {availability}')
                source,count=source.replace('), histories as (', '), history_links as ('+' UNION DISTINCT '.join(links)+'), histories as ('),source.count('), histories as (')
                if count!=1:raise ValueError('Unexpected history CTE')
                source,count=re.subn(r'left join fresh_calendar_service_event_facts h\s+on h\.event_date_local < a\.event_date_local.*?group by a\.calendar_event_row, a\.event_date_local',
                    'LEFT JOIN history_links hl ON hl.anchor_row=a.calendar_event_row LEFT JOIN fresh_calendar_service_event_facts h ON h.calendar_event_row=hl.history_row\n    group by a.calendar_event_row, a.event_date_local',source,flags=re.S)
                if count!=1:raise ValueError('Unexpected history join')
        temporary='fresh_'+name
        statements.append(f'CREATE TEMP TABLE {temporary} AS\n{source.rstrip().rstrip(";")};')
        replacements[f'`{b.PROJECT}`.`{schema}`.`{name}`']=temporary
    statements.append('SELECT * FROM fresh_warranty_callback_fixed_horizon_dataset;')
    return '\n'.join(statements),hashes


def main():
    from google.cloud import bigquery
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir',type=Path,default=b.ROOT/'outputs/cp2-v2/source_refresh_20260927')
    p.add_argument('--verify-existing',action='store_true',help='Replay corrected compiled SQL without overwriting frozen evidence')
    args=p.parse_args();out=args.source_dir.resolve()
    if not out.is_relative_to((b.ROOT/'outputs').resolve()):raise ValueError('Private outputs required')
    if (out/'refreshed/dataset_input.json').exists() and not args.verify_existing:raise ValueError('Refreshed snapshot already derived')
    if args.verify_existing and not (out/'receipt.json').exists():raise ValueError('Existing source receipt required')
    old=json.loads((out/'old_calendar_private.json').read_text(encoding='utf-8'))
    new=json.loads((out/'calendar_private.json').read_text(encoding='utf-8'))
    if old['metadata']['snapshot_id']!=OLD_TABLE.split('_')[-1]:raise ValueError('Unexpected old source snapshot')
    delta,replaced,invalid_geocodes,summary=source_delta(old,new)
    watermark=complete_through(new['metadata'])
    sql,hashes=candidate_sql(delta,replaced,invalid_geocodes,watermark)
    query_path=out/('candidate_query_replay.sql' if args.verify_existing else 'candidate_query.sql')
    query_path.write_text(sql,encoding='utf-8')
    client=bigquery.Client(project=b.PROJECT,location=b.LOCATION)
    parameters=[
        bigquery.ScalarQueryParameter('delta','STRING',json.dumps(delta,ensure_ascii=False)),
        bigquery.ArrayQueryParameter('replaced','INT64',replaced),
        bigquery.ArrayQueryParameter('invalid_geocodes','INT64',invalid_geocodes)]
    # Sequential session statements retain the existing 100 MiB guard per
    # query. Record every stage; never raise a failed query's billing limit.
    starts=[m.start() for m in re.finditer(r'^CREATE TEMP TABLE|^SELECT \* FROM fresh_warranty',sql,re.M)]+[len(sql)]
    stages=[sql[starts[i]:starts[i+1]].strip() for i in range(len(starts)-1)]
    session_id=None;stage_receipts=[]
    try:
        for stage in stages:
            config=bigquery.QueryJobConfig(maximum_bytes_billed=b.MAX_BYTES,query_parameters=parameters,
                create_session=session_id is None)
            if session_id:config.connection_properties=[bigquery.ConnectionProperty('session_id',session_id)]
            job=client.query(stage,job_config=config)
            try:rows=job.result(timeout=300)
            except Exception:
                job.cancel()
                try:job.result(timeout=30)
                except Exception:pass
                raise
            if session_id is None:session_id=job.session_info.session_id
            title=stage.splitlines()[0].split(' AS')[0]
            stage_receipts.append({'job_id':job.job_id,'bytes_processed':job.total_bytes_processed,
                'bytes_billed':job.total_bytes_billed,'statement':title})
            print(json.dumps({'completed_stage':title,'bytes_processed':job.total_bytes_processed}),flush=True)
        frame=pd.DataFrame(dict(row) for row in rows)
        receipt={'calendar_refresh':summary,'source_snapshot_id':new['metadata']['snapshot_id'],
            'source_extracted_at':new['metadata']['extracted_at'],'complete_outcomes_through':watermark.isoformat(),
            'query_jobs':stage_receipts,'bytes_processed':sum(r['bytes_processed'] or 0 for r in stage_receipts),'compiled_query_hashes':hashes,
            'query_sha256':hashlib.sha256(sql.encode()).hexdigest(),'temporary_tables_only':True}
    finally:
        if session_id:
            cleanup=bigquery.QueryJobConfig(maximum_bytes_billed=b.MAX_BYTES,
                connection_properties=[bigquery.ConnectionProperty('session_id',session_id)])
            client.query('CALL BQ.ABORT_SESSION();',job_config=cleanup).result(timeout=30)
        client.close()
    if frame.empty or frame.duplicated(['population','sales_record_id','anchor_date']).any():
        raise ValueError('Empty or duplicate refreshed anchors')
    if args.verify_existing:
        replay_dir=b.ROOT/'tmp/cp2_corrected_source_replay'
        actual=b.persist_dataset_input(frame,replay_dir)
        expected=json.loads((out/'receipt.json').read_text(encoding='utf-8'))['refreshed_input_sha256']
        verification=compare_replay(b.load_dataset_input(out/'refreshed/dataset_input.json'),
            b.load_dataset_input(replay_dir/'dataset_input.json'))
        receipt.update(replay_input_sha256=actual,rows=len(frame),source_replay_match=True,
            byte_hash_match=actual==expected,verification=verification)
        (out/'receipt_replay.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        print(json.dumps({'source_replay_match':True,'rows':len(frame),'sha256':actual}));return
    receipt['refreshed_input_sha256']=b.persist_dataset_input(frame,out/'refreshed')
    holdout=frame[pd.to_datetime(frame.anchor_date)>pd.Timestamp('2026-08-14')].copy()
    receipt['holdout_input_sha256']=b.persist_dataset_input(holdout,out/'new_mature_holdout')
    receipt.update(refreshed_rows=len(frame),refreshed_positive_rows=int(frame[b.TARGET].sum()),
        holdout_rows=len(holdout),holdout_positive_rows=int(holdout[b.TARGET].sum()))
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
