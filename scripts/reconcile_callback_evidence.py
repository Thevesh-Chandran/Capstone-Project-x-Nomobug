"""Read-only claim-date reconciliation and structured Calendar text coverage audit.

Raw titles/descriptions stay in ignored local outputs. No target is relabeled.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone, date
import hashlib
import json
from pathlib import Path
import re
import html

try:
    from scripts import benchmark_warranty_models as b
except ModuleNotFoundError:
    import benchmark_warranty_models as b

PESTS={'COCKROACH':r'\b(?:cockroach(?:es)?|roach(?:es)?|lipas)\b', 'ANT':r'\b(?:ants?|semut)\b',
       'RODENT':r'\b(?:rats?|rodents?|mice|mouse|tikus)\b',
       'TERMITE':r'\b(?:termites?|anai[ -]?anai)\b',
       'BED_BUG':r'\b(?:bed\s*bugs?|pepijat)\b',
       'MOSQUITO':r'\b(?:mosquito(?:es|s)?|nyamuk)\b',
       'FLY':r'\b(?:flies|fly|lalat)\b'}
METHODS={'FOGGING_OR_MISTING':r'\b(?:fogging|fog|misting|mist)\b',
         'GEL_OR_BAIT':r'\b(?:gel|bait(?:ing)?|umpan)\b',
         'SPRAY':r'\b(?:spray(?:ing)?|semburan|sembur)\b',
         'INSPECTION':r'\b(?:inspection|consultation|pemeriksaan)\b'}


def clean_text(text):
    text=html.unescape(text or '')
    text=re.sub(r'(?i)<br\s*/?>|</(?:p|div|li)>','\n',text)
    return re.sub(r'<[^>]+>','',text)


def structured_mentions(description):
    text=clean_text(description)
    # Parse named fields only: customer names and email addresses cannot become pests.
    fields={}
    for line in text.splitlines():
        match=re.match(r'^\s*(problem|pest|masalah|method|treatment|kaedah|severity|infestation severity)\s*:\s*(.*)$',line,re.I)
        if match:
            fields.setdefault(match[1].lower(),[]).append(match[2])
    problem=' '.join(v for k,values in fields.items() if k in ('problem','pest','masalah') for v in values)
    method=' '.join(v for k,values in fields.items() if k in ('method','treatment','kaedah') for v in values)
    return {'problem_field_present':bool(problem.strip()),
            'problem_prevention_mentioned':bool(re.search(r'\b(?:prevention|preventive|pencegahan)\b',problem,re.I)),
            'problem_pests':'|'.join(sorted(k for k,p in PESTS.items() if re.search(p,problem,re.I))) or 'UNSPECIFIED',
            'method_field_present':bool(method.strip()),
            'method_mentions':'|'.join(sorted(k for k,p in METHODS.items() if re.search(p,method,re.I))) or 'UNSPECIFIED',
            'severity_field_present':any(k in fields for k in ('severity','infestation severity'))}


def parse_service_dates(raw):
    """Conservative extraction; unresolved text never silently becomes no service."""
    raw=(raw or '').strip()
    if not raw:
        return [],'blank'
    tokens=re.findall(r'\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{4}\b',raw)
    parsed=[]
    for token in tokens:
        for fmt in ['%d %b %Y','%d %B %Y','%Y-%m-%d','%d/%m/%Y']:
            try:
                parsed.append(datetime.strptime(token,fmt).date().isoformat()); break
            except ValueError:
                pass
    remainder=raw
    for token in tokens:
        remainder=remainder.replace(token,'')
    unresolved=bool(re.sub(r'[\s,;|/\-]+','',remainder)) or len(parsed)!=len(tokens)
    return sorted(set(parsed)), 'needs_review' if unresolved or not parsed else 'parsed'


def dates_within(anchor,dates,start=1,end=30):
    return [d for d in dates if start <= (date.fromisoformat(d)-date.fromisoformat(anchor)).days <= end]


def snapshot_known_by_service_end(row):
    try:
        values=[datetime.fromisoformat(row[k].replace('Z','+00:00'))
                for k in ['created_raw','updated_raw','end_raw']]
        return all(v.tzinfo is not None for v in values) and values[0]<=values[1]<=values[2]
    except (ValueError,AttributeError,TypeError,KeyError):
        return False


def fetch(output):
    from google.cloud import bigquery
    c=bigquery.Client(project=b.PROJECT,location=b.LOCATION)
    v=c.get_table(f'{b.PROJECT}.silver.calendar_events')
    raws=set(re.findall(r'profound-keel-500007-s4\.bronze\.calendar_events_[0-9a-f]{64}',v.view_query.replace('`','')))
    if len(raws)!=1:
        raise ValueError('Ambiguous governing Calendar snapshot')
    raw=raws.pop()
    queries={
      'anchors':f'''select d.population,d.sales_record_id,cast(d.anchor_date as string) anchor_date,
 d.anchor_event_row,d.warranty_signal_within_30d as target,
 r.summary,r.description,r.created_raw,r.updated_raw,r.end_raw,
 e.calendar_service_method_category as title_method
from `{b.PROJECT}.analytics_ml.warranty_callback_fixed_horizon_dataset` d
join `{raw}` r on r.calendar_event_row=d.anchor_event_row
join `{b.PROJECT}.silver.calendar_events` e on e.calendar_event_row=d.anchor_event_row''',
      'claims':f'''select c.sales_record_id,c.warranty_claim_record_id,c.source_sheet_row,
 cast(c.recorded_claim_date as string) recorded_claim_date,c.claim_date_raw,
 w.warranty_claim_service_date_raw,w.complimentary_service_date_raw,c.source_refund_indicator
from `{b.PROJECT}.gold.warranty_claim_record_facts` c
join `{b.PROJECT}.silver.warranty_claim` w using(warranty_claim_record_id)
where c.sales_record_id in
 (select distinct sales_record_id from `{b.PROJECT}.analytics_ml.warranty_callback_fixed_horizon_dataset`)'''}
    receipt={'executed_at':datetime.now(timezone.utc).isoformat(),'queries':{},'rows':{}}
    for name,sql in queries.items():
        job=c.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=b.MAX_BYTES))
        receipt['rows'][name]=[dict(r) for r in job.result(timeout=300)]
        receipt['queries'][name]={'sql':sql,'job_id':job.job_id,'bytes_processed':job.total_bytes_processed}
    output.write_text(json.dumps(receipt,default=str,indent=2),encoding='utf-8')
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-json',type=Path)
    p.add_argument('--output-dir',type=Path,default=b.ROOT/'outputs/cp2-v2/callback_evidence_reconciliation')
    args=p.parse_args(); args.output_dir.mkdir(parents=True,exist_ok=True)
    r=json.loads(args.evidence_json.read_text()) if args.evidence_json else fetch(args.output_dir/'source_private.json')
    frozen=json.loads((b.ROOT/'outputs/cp2-v2/callback_error_analysis/source_evidence_private.json').read_text())
    key=lambda x:(x['population'],x['sales_record_id'],x['anchor_date'])
    anchors={key(x):x for x in r['rows']['anchors']}
    if len(anchors)!=len(r['rows']['anchors']):
        raise ValueError('Duplicate anchor source keys')
    model_input=b.load_dataset_input(b.ROOT/'outputs/cp2-v2/model_callback_normalized_pest/dataset_input.json')
    known={(x['population'],str(x['sales_record_id']),str(x['anchor_date'])[:10]):bool(x[b.TARGET])
           for x in model_input.to_dict('records')}
    if set(known)!=set(anchors) or any(known[k]!=anchors[k]['target'] for k in known):
        raise ValueError('Full frozen model cohort or labels drifted')
    if any(key(x) not in anchors or anchors[key(x)]['target']!=x['live_target'] for x in frozen['rows']):
        raise ValueError('Frozen diagnostic anchors or labels drifted')
    claims={}
    for row in r['rows']['claims']:
        ds,status=parse_service_dates(row['warranty_claim_service_date_raw'])
        row.update(service_dates=ds,service_date_parse_status=status)
        claims.setdefault(row['sales_record_id'],[]).append(row)
    coverage={}; feature_rows=[]
    for row in r['rows']['anchors']:
        f=structured_mentions(row['description'])
        # A current snapshot cannot establish historical text availability merely from
        # the service date. This conservative gate excludes any later edit.
        asof=snapshot_known_by_service_end(row)
        period='2026' if row['anchor_date']>='2026-01-01' else 'pre2026'
        stats=coverage.setdefault(period,Counter())
        stats['anchors']+=1
        for name in ['problem_field_present','method_field_present','severity_field_present']:
            stats[name]+=int(f[name])
            stats[name+'_asof']+=int(f[name] and asof)
        stats['recognized_method']+=int(f['method_mentions']!='UNSPECIFIED')
        stats['recognized_problem_pests']+=int(f['problem_pests']!='UNSPECIFIED')
        stats['timestamp_gate_pass']+=int(asof)
        stats['title_method_unspecified']+=int(row['title_method']=='UNSPECIFIED')
        feature_rows.append({k:row[k] for k in ['population','sales_record_id','anchor_date']}|f|{'snapshot_timestamp_gate_pass':asof})
    discrepancies=[]
    for row in frozen['rows']:
        records=[c for c in claims.get(row['sales_record_id'],[]) if c['recorded_claim_date'] and dates_within(row['anchor_date'],[c['recorded_claim_date']])]
        if row['live_target'] or not records:
            continue
        calendar_dates={e['event_date'] for e in row['following_events'] if e['is_callback']}
        service_dates=sorted({d for c in records for d in c['service_dates']})
        window=dates_within(row['anchor_date'],service_dates)
        later=dates_within(row['anchor_date'],service_dates,31,60)
        discrepancies.append({'anchor_date':row['anchor_date'],'anchor_calendar':row['anchor_calendar'],
          'anchor_title':row['anchor_title'],'sales_record_id':row['sales_record_id'],
          'claim_sheet_rows':[c['source_sheet_row'] for c in records],
          'claim_record_dates':[c['recorded_claim_date'] for c in records],
          'claim_service_dates':service_dates,'service_dates_within_30d':window,
          'service_dates_31_60d':later,'calendar_callback_dates':sorted(calendar_dates),
          'exact_service_calendar_date_overlap':sorted(set(service_dates)&calendar_dates),
          'all_service_fields_blank':all(c['service_date_parse_status']=='blank' for c in records),
          'any_service_field_needs_review':any(c['service_date_parse_status']=='needs_review' for c in records)})
    import pandas as pd
    pd.DataFrame(discrepancies).to_csv(args.output_dir/'private_claim_visit_review.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(feature_rows).to_csv(args.output_dir/'private_description_features.csv',index=False)
    counts={'discrepant_anchors':len(discrepancies),
      'unique_claim_sheet_rows':len({n for d in discrepancies for n in d['claim_sheet_rows']}),
      'anchors_with_service_date_within_30d':sum(bool(d['service_dates_within_30d']) for d in discrepancies),
      'anchors_with_service_date_31_60d':sum(bool(d['service_dates_31_60d']) for d in discrepancies),
      'anchors_with_exact_service_calendar_date_overlap':sum(bool(d['exact_service_calendar_date_overlap']) for d in discrepancies),
      'anchors_all_service_fields_blank':sum(d['all_service_fields_blank'] for d in discrepancies),
      'anchors_any_service_field_needs_review':sum(d['any_service_field_needs_review'] for d in discrepancies)}
    report={'executed_at':r['executed_at'],'queries':r['queries'],
      'source_sha256':hashlib.sha256(json.dumps(r['rows'],sort_keys=True).encode()).hexdigest(),
      'anchor_rows':len(anchors),'all_frozen_labels_reconciled':len(known),'frozen_2026_labels_reconciled':len(frozen['rows']),
      'claim_record_rows':len(r['rows']['claims']),
      'claim_service_date_parse_status':dict(Counter(c['service_date_parse_status'] for c in r['rows']['claims'])),
      'description_coverage':coverage,'claim_visit_reconciliation':counts,
      'limits':['Dates in claim service fields are recorded dates, not completion proof.',
        'Same-sale exact-date overlap does not independently identify a callback event.',
        'Post-service snapshot edits are excluded from as-of feature eligibility.',
        'Structured mentions are not verified treatment performed or infestation severity.',
        'No source records or outcome labels changed.']}
    (args.output_dir/'aggregate_results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='queries'},indent=2))


if __name__=='__main__':
    main()
