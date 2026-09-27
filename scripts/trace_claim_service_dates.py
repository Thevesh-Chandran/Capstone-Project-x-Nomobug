"""Read-only exact identity/date trace for unresolved claim-service cases."""
import json,re
import argparse
from pathlib import Path
from google.cloud import bigquery
from scripts.reconcile_callback_evidence import parse_service_dates,dates_within

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-json',type=Path)
    args=parser.parse_args()
    root=Path('outputs/cp2-v2/callback_evidence_reconciliation')
    r=json.loads((root/'source_private.json').read_text())
    f=json.loads(Path('outputs/cp2-v2/callback_error_analysis/source_evidence_private.json').read_text())
    anchors={(a['population'],a['sales_record_id'],a['anchor_date']):a for a in r['rows']['anchors']}
    lookups=[]
    for a in f['rows']:
     cs=[c for c in r['rows']['claims'] if c['sales_record_id']==a['sales_record_id'] and c['recorded_claim_date'] and dates_within(a['anchor_date'],[c['recorded_claim_date']])]
     ds={d for c in cs for d in parse_service_dates(c['warranty_claim_service_date_raw'])[0]}
     if not a['live_target']:
      for d in dates_within(a['anchor_date'],ds):
       lookups.append(bigquery.StructQueryParameter(None,bigquery.ScalarQueryParameter('anchor_event_row','INT64',int(a['anchor_event_row'])),bigquery.ScalarQueryParameter('service_date','DATE',d)))
    raw=re.search(r'profound-keel-500007-s4\.bronze\.calendar_events_[0-9a-f]{64}',r['queries']['anchors']['sql']).group()
    q=f'''with lookups as (select * from unnest(@lookups)),
    normalized as (select *,regexp_replace(regexp_extract(regexp_replace(description,r'<[^>]+>',''),r'(?i)(?:Phone|Telefon|No[.]? Tel):\\s*([^\\n<]+)'),r'[^0-9]','') phone_key,
     regexp_replace(upper(trim(regexp_extract(regexp_replace(description,r'<[^>]+>',''),r'(?i)(?:Nama|Name):\\s*([^\\n<]+)'))),r'[^A-Z0-9]','') name_key,
    date(safe_cast(start_raw as timestamp),'Asia/Kuala_Lumpur') event_date from `{raw}`)
    select l.anchor_event_row,cast(l.service_date as string) service_date,
     a.phone_key is not null and length(a.phone_key)>=9 as anchor_has_phone,
     a.name_key is not null and length(a.name_key)>=5 as anchor_has_name,
     r.calendar_event_row,cast(r.event_date as string) event_date,r.summary,r.status,
     e.event_category,e.warranty_claim_candidate,g.sales_record_id as linked_sale,
     date_diff(r.event_date,l.service_date,day) date_offset
    from lookups l join normalized a on a.calendar_event_row=l.anchor_event_row
    left join normalized r on ((a.phone_key=r.phone_key and length(a.phone_key)>=9)
     or (a.name_key=r.name_key and length(a.name_key)>=5))
     and r.event_date between date_sub(l.service_date,interval 14 day) and date_add(l.service_date,interval 14 day)
    left join `profound-keel-500007-s4.silver.calendar_events` e on e.calendar_event_row=r.calendar_event_row
    left join `profound-keel-500007-s4.gold.calendar_service_event_facts` g on g.calendar_event_row=r.calendar_event_row'''
    if args.evidence_json:
        evidence=json.loads(args.evidence_json.read_text())
    else:
        c=bigquery.Client(project='profound-keel-500007-s4',location='asia-southeast1')
        job=c.query(q,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=100*1024*1024,query_parameters=[bigquery.ArrayQueryParameter('lookups','STRUCT',lookups)]))
        evidence={'sql':q,'job_id':job.job_id,'bytes_processed':job.total_bytes_processed,'rows':[dict(x) for x in job.result(timeout=300)]}
        (root/'seven_case_trace_private.json').write_text(json.dumps(evidence,default=str,indent=2))
    rows=evidence['rows']
    summary=[]
    for l in lookups:
     key=l.struct_values['anchor_event_row']; ds=str(l.struct_values['service_date'])
     found=[x for x in rows if x['anchor_event_row']==key and x['service_date']==ds]
     summary.append({'has_phone':any(x['anchor_has_phone'] for x in found),'has_name':any(x['anchor_has_name'] for x in found),'same_identity_nearby_events':sum(x['calendar_event_row'] is not None for x in found),'exact_date_events':sum(x['date_offset']==0 for x in found),'nearby_offsets':[x['date_offset'] for x in found if x['date_offset'] is not None],'categories':[x['event_category'] for x in found if x['calendar_event_row']]})
    import pandas as pd
    private=[]
    for i,l in enumerate(lookups):
        key=l.struct_values['anchor_event_row']; ds=str(l.struct_values['service_date'])
        anchor=next(a for a in f['rows'] if int(a['anchor_event_row'])==int(key))
        matches=[x for x in rows if x['anchor_event_row']==key and x['service_date']==ds and x['calendar_event_row']]
        linked_claims=[c for c in r['rows']['claims'] if c['sales_record_id']==anchor['sales_record_id']
          and c['recorded_claim_date'] and dates_within(anchor['anchor_date'],[c['recorded_claim_date']])]
        private.append({'review_id':f'DATE-{i+1:03d}','anchor_date':anchor['anchor_date'],
          'calendar':anchor['anchor_calendar'],'search_title':anchor['anchor_title'],
          'claim_sheet_rows':[c['source_sheet_row'] for c in linked_claims],
          'claim_record_dates':[c['recorded_claim_date'] for c in linked_claims],
          'claim_sheet_service_date':ds,'nearby_calendar_dates':[x['event_date'] for x in matches],
          'nearby_categories':[x['event_category'] for x in matches],
          'review_action':'Check claim sheet service date against actual booking/reschedule; no label change inferred.'})
    pd.DataFrame(private).to_csv(root/'private_seven_date_cases.csv',index=False,encoding='utf-8-sig')
    aggregate={'cases':len(lookups),'cases_with_identity_key':sum(s['has_phone'] or s['has_name'] for s in summary),
      'cases_with_nearby_identity_candidate':sum(s['same_identity_nearby_events']>0 for s in summary),
      'cases_with_exact_date_match':sum(s['exact_date_events']>0 for s in summary),
      'cases_with_later_warranty_candidate':sum(any((x['date_offset'] or 0)>0 and bool(x['warranty_claim_candidate']) for x in rows
          if x['anchor_event_row']==l.struct_values['anchor_event_row']) for l in lookups),
      'job_id':evidence['job_id'],'bytes_processed':evidence['bytes_processed'],'sql':evidence['sql'],
      'limits':['Search is limited to +/-14 days and exact normalized phone/name fields.',
        'Identity candidates do not establish same property, completed visit, or fulfillment of a specific claim.',
        'No exact-date matches found does not prove the visit was never recorded elsewhere.']}
    (root/'seven_case_trace_aggregate.json').write_text(json.dumps(aggregate,indent=2))
    print(json.dumps(aggregate,indent=2))

if __name__ == "__main__":
    main()
