"""Reconcile frozen callback errors and audit source evidence without relabeling."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts import benchmark_warranty_models as b
    from scripts.compare_flood_models import configure_contracts
    from scripts.analyze_warranty_label_review import wilson_interval
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    from compare_flood_models import configure_contracts
    from analyze_warranty_label_review import wilson_interval

ROOT=b.ROOT
SOURCE=f'{b.PROJECT}.analytics_ml.warranty_callback_fixed_horizon_dataset'
SQL=f'''with events as (
select d.population, d.sales_record_id, cast(d.anchor_date as string) anchor_date,
 d.anchor_event_row, d.warranty_signal_within_30d as live_target,
 d.warranty_claim_count_30d, cast(d.observed_through as string) observed_through,
 a.calendar_name as anchor_calendar, a.match_status as anchor_match_status,
 a.location_precision_tier, a.completion_evidence,
 raw.summary as anchor_title,
 array_agg(if(w.calendar_event_row is null, null, struct(
   w.calendar_event_row as event_row, cast(w.event_date_local as string) as event_date,
   date_diff(w.event_date_local,d.anchor_date,day) as days_after_anchor,
   w.calendar_name as calendar_name, return_raw.summary as title,
   w.warranty_claim_candidate as is_callback, w.warranty_claim_reason as reason,
   w.event_category as event_category, w.match_status as match_status,
   w.session_current as session_current, w.session_total as session_total,
   r.warranty_label_provenance as label_provenance,
   r.warranty_label_review_status as review_status,
   if(a.address_hash is null or w.address_hash is null, null,
      a.address_hash=w.address_hash) as same_property_hash,
   if(a.service_geography is null or w.service_geography is null,null,
      st_distance(a.service_geography,w.service_geography)) as geocode_distance_m,
   a.location_uncertainty_radius_m as anchor_uncertainty_m,
   w.location_uncertainty_radius_m as return_uncertainty_m
 )) ignore nulls) as following_events
from `{SOURCE}` d
join `{b.PROJECT}.gold.calendar_service_event_facts` a
 on a.calendar_event_row=d.anchor_event_row
join `__CALENDAR_RAW_TABLE__` raw
 on raw.calendar_event_row=a.calendar_event_row
left join `{b.PROJECT}.gold.calendar_service_event_facts` w
 on w.sales_record_id=d.sales_record_id and w.event_date_local>d.anchor_date
 and w.event_date_local<=date_add(d.anchor_date, interval 60 day)
 and w.event_date_local<=d.observed_through
left join `{b.PROJECT}.silver.calendar_events` r on r.calendar_event_row=w.calendar_event_row
left join `__CALENDAR_RAW_TABLE__` return_raw on return_raw.calendar_event_row=w.calendar_event_row
where d.anchor_date>='2026-01-01'
group by 1,2,3,4,5,6,7,8,9,10,11,12
), records as (
select d.population,d.sales_record_id,cast(d.anchor_date as string) anchor_date,
 countif(c.recorded_claim_date>d.anchor_date and c.recorded_claim_date<=d.outcome_end_date
   and not c.claim_date_needs_review) as dated_claim_record_count
from `{SOURCE}` d
left join `{b.PROJECT}.gold.warranty_claim_record_facts` c using(sales_record_id)
where d.anchor_date>='2026-01-01'
group by 1,2,3)
select events.*,records.dated_claim_record_count from events join records using(population,sales_record_id,anchor_date)'''


def classify_errors(y, probability, threshold):
    y=np.asarray(y,dtype=bool); alert=np.asarray(probability)>=threshold
    return np.select([y & alert,y & ~alert,~y & alert],['TP','FN','FP'],default='TN')


def top_budget(probability, fraction=0.2):
    values=np.asarray(probability,dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('Nonempty finite scores required')
    cutoff=np.sort(values)[-max(1,int(np.ceil(len(values)*fraction)))]
    return values>=cutoff


def summarize(group, alert_col):
    y=group[b.TARGET].astype(bool); alert=group[alert_col].astype(bool)
    tp=int((y&alert).sum()); fn=int((y&~alert).sum())
    fp=int((~y&alert).sum()); tn=int((~y&~alert).sum())
    return {'rows':len(group),'positive_rows':int(y.sum()),'TP':tp,'FN':fn,'FP':fp,'TN':tn,
            'callback_rate':float(y.mean()),'alert_rows':tp+fp,
            'recall':tp/(tp+fn) if tp+fn else None,
            'precision':tp/(tp+fp) if tp+fp else None,
            'false_positive_rate':fp/(fp+tn) if fp+tn else None,
            'recall_wilson_95':wilson_interval(tp,tp+fn) if tp+fn else None,
            'false_positive_rate_wilson_95':wilson_interval(fp,fp+tn) if fp+tn else None}


def evidence_flags(row):
    events=row.get('following_events') or []
    within=[e for e in events if 1<=e['days_after_anchor']<=30]
    callbacks=[e for e in within if e['is_callback']]
    distant=[]
    for e in callbacks:
        if (e['geocode_distance_m'] is not None and e['anchor_uncertainty_m'] is not None
                and e['return_uncertainty_m'] is not None
                and e['geocode_distance_m']>max(2000,e['anchor_uncertainty_m']+e['return_uncertainty_m'])):
            distant.append(e)
    return {'callback_events_30d':len(callbacks),
            'reconstructed_target':bool(callbacks),
            'post_package_only_positive':bool(callbacks) and all(e['reason']=='post_package_sequence' for e in callbacks),
            'manual_review_positive':any(e['label_provenance']=='manual_review_2026_09_27' for e in callbacks),
            'different_hash_positive':any(e['same_property_hash'] is False for e in callbacks),
            'distant_location_positive':bool(distant),
            'unreviewed_extra_30d':any(e['event_category']=='extra_visit_candidate' and e['review_status']=='Not reviewed' for e in within),
            'complimentary_30d':any(e['event_category']=='complimentary' for e in within),
            'later_callback_31_60d':any(e['is_callback'] and 31<=e['days_after_anchor']<=60 for e in events),
            'dated_claim_record_without_calendar_callback':row['dated_claim_record_count']>0 and not callbacks}


def fetch_evidence(output):
    from google.cloud import bigquery
    client=bigquery.Client(project=b.PROJECT,location=b.LOCATION)
    view=client.get_table(f'{b.PROJECT}.silver.calendar_events')
    raw_tables=set(re.findall(r'profound-keel-500007-s4\.bronze\.calendar_events_[0-9a-f]{64}',(view.view_query or '').replace('`','')))
    if len(raw_tables)!=1:
        raise ValueError('Cannot resolve the governing Calendar snapshot')
    sql=SQL.replace('__CALENDAR_RAW_TABLE__',raw_tables.pop())
    job=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=b.MAX_BYTES))
    rows=[dict(row) for row in job.result(timeout=300)]
    receipt={'source':SOURCE,'sql':sql,'job_id':job.job_id,'bytes_processed':job.total_bytes_processed,
             'executed_at':datetime.now(timezone.utc).isoformat(),'rows':rows}
    output.write_text(json.dumps(receipt,default=str,indent=2),encoding='utf-8')
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'outputs/cp2-v2/callback_error_analysis')
    parser.add_argument('--evidence-json',type=Path)
    args=parser.parse_args(); output=args.output_dir; output.mkdir(parents=True,exist_ok=True)
    configure_contracts(False)
    model_dir=ROOT/'outputs/cp2-v2/model_callback_normalized_pest'
    frame=b.prepare_frame(b.load_dataset_input(model_dir/'dataset_input.json'))
    frame=frame[frame.anchor_date.ge('2026-01-01')].copy()
    keys=['population','sales_record_id','anchor_date']
    predictions=pd.read_csv(model_dir/f'{frame.population.iloc[0]}_diagnostic_predictions.csv',dtype={'sales_record_id':str})
    predictions.anchor_date=pd.to_datetime(predictions.anchor_date)
    joined=frame.merge(predictions[keys+['probability','threshold',b.TARGET]],on=keys,validate='one_to_one',suffixes=('','_saved'),how='outer',indicator=True)
    if not joined['_merge'].eq('both').all() or not joined[b.TARGET].eq(joined[b.TARGET+'_saved']).all():
        raise ValueError('Frozen predictions differ from model input')
    joined['threshold_alert']=joined.probability>=joined.threshold
    joined['budget_alert']=top_budget(joined.probability)
    joined['error_type']=classify_errors(joined[b.TARGET],joined.probability,joined.threshold)
    joined['budget_error_type']=np.select([joined[b.TARGET]&joined.budget_alert,joined[b.TARGET]&~joined.budget_alert,~joined[b.TARGET]&joined.budget_alert],['TP','FN','FP'],default='TN')
    receipt=json.loads(args.evidence_json.read_text()) if args.evidence_json else fetch_evidence(output/'source_evidence_private.json')
    evidence=pd.DataFrame(receipt['rows']); evidence.anchor_date=pd.to_datetime(evidence.anchor_date)
    flags=pd.DataFrame([evidence_flags(row) for row in receipt['rows']])
    evidence=pd.concat([evidence,flags],axis=1)
    joined=joined.merge(evidence,on=keys,how='outer',indicator='evidence_join',validate='one_to_one')
    if not joined.evidence_join.eq('both').all() or not joined[b.TARGET].eq(joined.live_target).all():
        raise ValueError('Live cohort/labels drifted from frozen input')
    if not joined[b.TARGET].eq(joined.reconstructed_target).all() or not joined.warranty_claim_count_30d.eq(joined.callback_events_30d).all():
        raise ValueError('Calendar evidence does not reconstruct every outcome')
    joined['package_tier']=joined.package_sessions_recorded.astype(int).astype(str)+'x'
    joined['service_stage']=np.select([joined.service_number.eq(1),joined.service_number.eq(joined.package_sessions_recorded)],['first','final'],default='middle')
    joined['weather_14d_missing']=np.where(joined.prior_14d_precipitation_mm.isna(),'missing','available')
    joined['waterway_missing']=np.where(joined.hotosm_nearest_waterway_m.isna(),'missing','available')
    joined['geocode_quality']=np.select([joined.location_uncertainty_radius_m.isna(),joined.location_uncertainty_radius_m.le(500),joined.location_uncertainty_radius_m.le(2000)],['missing','<=500m','501-2000m'],default='>2000m')
    joined['prior_property_callback']=np.where(joined.prior_property_warranty_claims.gt(0),'previous_recorded_callback','none_recorded')
    joined['month']=joined.anchor_date.dt.strftime('%Y-%m')
    cuts=['normalized_pest_category','package_tier','premise_type','service_stage','calendar_service_method_category',
          'calendar_pest_text_category','weather_14d_missing','waterway_missing','geocode_quality','prior_property_callback','month']
    segments=[]
    for dimension in cuts:
        for value,g in joined.groupby(dimension,dropna=False):
            summary=summarize(g,'threshold_alert'); budget=summarize(g,'budget_alert')
            segments.append({'dimension':dimension,'segment':str(value),**summary,
                             'share_of_all_FN':summary['FN']/int((joined.error_type=='FN').sum()),
                             'share_of_all_FP':summary['FP']/int((joined.error_type=='FP').sum()),
                             'supported':summary['rows']>=50 and summary['positive_rows']>=10,
                             'budget':budget})
    flag_names=list(flags.columns.difference(['callback_events_30d','reconstructed_target']))
    flags_summary={flag:{kind:int(joined.loc[joined.error_type.eq(kind),flag].sum()) for kind in ['TP','FN','FP','TN']} for flag in flag_names}
    positive_events=[]
    for _,row in joined[joined[b.TARGET]].iterrows():
        positive_events.extend(e['event_row'] for e in row.following_events if e['is_callback'] and e['days_after_anchor']<=30)
    segment_frame=pd.DataFrame([{k:v for k,v in s.items() if k!='budget'} for s in segments])
    segment_frame.to_csv(output/'aggregate_segments.csv',index=False)
    queue=joined[joined.error_type.isin(['FN','FP'])].copy()
    queue['review_reason']=queue.apply(lambda r: '; '.join([flag for flag in flag_names if r[flag]]) or 'model_error_no_structural_label_flag',axis=1)
    queue['review_priority']=queue.apply(lambda r: int(r.distant_location_positive)*100+int(r.dated_claim_record_without_calendar_callback)*80+int(r.unreviewed_extra_30d)*60+int(r.post_package_only_positive)*40+(1-r.probability if r.error_type=='FN' else r.probability),axis=1)
    # Preserve both missed positives and false alarms in the searchable queue.
    queue=pd.concat([queue[queue.error_type.eq(kind)].sort_values('review_priority',ascending=False).head(15)
                     for kind in ['FN','FP']])
    queue['review_id']=['ERR-'+str(i+1).zfill(3) for i in range(len(queue))]
    queue[['review_id','anchor_date','anchor_calendar','anchor_title','error_type','probability','normalized_pest_category','package_tier','review_reason']].to_csv(output/'private_owner_review_queue.csv',index=False,encoding='utf-8-sig')
    report={'input_sha256':'464bb51386c1bcce9744f74f61b4d0b4265be4a4631c1ede97063b62346914d9',
            'source':SOURCE,'source_job_id':receipt['job_id'],'source_bytes_processed':receipt['bytes_processed'],
            'source_executed_at':receipt['executed_at'],'source_evidence_sha256':hashlib.sha256(json.dumps(receipt['rows'],sort_keys=True).encode()).hexdigest(),
            'source_sql':receipt['sql'],'start':str(joined.anchor_date.min().date()),'end':str(joined.anchor_date.max().date()),
            'threshold_summary':summarize(joined,'threshold_alert'),'top20pct_summary':summarize(joined,'budget_alert'),
            'segments':segments,'label_evidence_flags':flags_summary,
            'distinct_callback_events':len(set(positive_events)),'callback_event_anchor_links':len(positive_events),
            'positive_anchor_rows':int(joined[b.TARGET].sum()),
            'all_frozen_labels_and_counts_reconstructed':True,'private_review_queue_rows':len(queue),
            'limits':['Recorded scheduled corrective visits are not completion or biological recurrence proof',
                      'A negative means no qualifying linked calendar visit in 30 days, not no actual pest problem',
                      'Segments overlap across dimensions and small subgroup estimates are unstable',
                      'Wilson intervals are descriptive anchor-level bounds; package/property dependence is not accounted for',
                      '31–60 day follow-up is censored at observed_through; absence is not a mature 60-day negative',
                      'Flags are candidates for review, not confirmed mislabeled records; no labels changed']}
    (output/'error_analysis_results.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    joined.drop(columns=['following_events','anchor_title']).to_csv(output/'private_error_detail.csv',index=False)
    print(json.dumps({k:v for k,v in report.items() if k not in ['segments','source_sql']},indent=2))


if __name__=='__main__':
    main()
