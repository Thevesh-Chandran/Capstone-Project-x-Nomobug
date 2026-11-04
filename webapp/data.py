"""Fixed, bounded reads from approved aggregate Gold views."""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

PROJECT = 'profound-keel-500007-s4'
MAX_BYTES = 100*1024*1024
QUERIES = {
 'upcoming': "SELECT service_date, calendar_name, scheduled_event_rows, extracted_at FROM `{project}.gold.dashboard_upcoming_appointments` ORDER BY service_date, calendar_name LIMIT 1000",
 'business_areas': "SELECT district, source_release, SUM(sales_rm) AS sales_rm, SUM(sale_rows) AS sale_rows FROM `{project}.gold.dashboard_business_sales` WHERE EXTRACT(YEAR FROM month_start)=2026 GROUP BY district, source_release ORDER BY sales_rm DESC",
 'customer_segments': "SELECT segment, customer_groups, programmes, sales_rm, source_release FROM `{project}.gold.dashboard_business_customers` ORDER BY customer_groups DESC",
 'sales': "SELECT closed_month, countable_package_rows, recorded_package_face_value_rm FROM `{project}.gold.sales_monthly_recorded` WHERE EXTRACT(YEAR FROM closed_month)=2026 ORDER BY closed_month",
 'services': "SELECT service_month, scheduled_service_event_rows, normal_package_service_event_rows, warranty_claim_event_rows, matched_sales_event_rows, heatmap_eligible_event_rows FROM `{project}.gold.dashboard_service_monthly` ORDER BY service_month",
 'payments': "SELECT billing_arrangement, tracker_as_of_date, candidate_contract_rows, recorded_contract_value_rm, sales_total_recorded_paid_rm, positive_recorded_remaining_balance_rm, contracts_with_scheduled_reminders_next_7_days, contracts_without_source_schedule FROM `{project}.gold.dashboard_recurring_payment_quality` ORDER BY billing_arrangement",
 'reminders': "SELECT reminder_date, billing_arrangement, scheduled_contract_rows, scheduled_reminder_date_rows FROM `{project}.gold.dashboard_recurring_reminder_schedule` ORDER BY reminder_date LIMIT 500",
 'freshness': "SELECT source_name, extracted_at_utc, release_run_id FROM `{project}.gold.dashboard_source_freshness` ORDER BY source_name",
 'attention': "SELECT category, action_date, context, item_count, amount_rm, unit, next_action, meaning, source_view, source_updated_at, freshness_status FROM `{project}.gold.dashboard_attention` ORDER BY action_date, category LIMIT 200",
 'areas': "SELECT area_cell, area_centroid_latitude, area_centroid_longitude, scheduled_service_event_rows, repeat_signal_event_rows FROM `{project}.gold.dashboard_spatial_area` ORDER BY scheduled_service_event_rows DESC LIMIT 500",
 'clusters': "SELECT radius_km, cluster_id, distinct_service_properties, recorded_warranty_signal_rows, avg_prior_7d_precipitation_mm FROM `{project}.gold.dashboard_spatial_cluster_summary` ORDER BY radius_km, cluster_id LIMIT 500",
}

def json_default(v):
    if isinstance(v, Decimal): return float(v)
    if hasattr(v,'isoformat'): return v.isoformat()
    raise TypeError(type(v).__name__)

def load_snapshot(folder):
    p=Path(folder)/'business_snapshot.json'
    if not p.exists(): return {'status':'not_connected','tables':{},'message':'Run the aggregate data refresh to connect BigQuery.'}
    return json.loads(p.read_text(encoding='utf-8'))

def refresh(folder, client=None):
    from google.cloud import bigquery
    owned=client is None
    client=client or bigquery.Client(project=PROJECT,location='asia-southeast1')
    tables={};receipts={}
    try:
        for name, template in QUERIES.items():
            sql=template.format(project=PROJECT)
            dry=client.query(sql,job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False),location='asia-southeast1')
            if (dry.total_bytes_processed or 0)>MAX_BYTES: raise ValueError('Aggregate query exceeds 100 MiB')
            job=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES),location='asia-southeast1')
            tables[name]=[dict(r.items()) for r in job.result(timeout=120)]
            receipts[name]={'job_id':job.job_id,'bytes_processed':job.total_bytes_processed,'source':template.split('`')[1].format(project=PROJECT)}
        result={'status':'connected','fetched_at_utc':datetime.now(timezone.utc).isoformat(),'tables':tables,'receipts':receipts}
        # Publish only after every query succeeds. A failed refresh preserves last good snapshot.
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        temp=folder/'business_snapshot.next.json'
        temp.write_text(json.dumps(result,default=json_default,allow_nan=False),encoding='utf-8')
        os.replace(temp,folder/'business_snapshot.json')
        return result
    finally:
        if owned: client.close()

def totals(snapshot):
    tables=snapshot.get('tables',{})
    def total(table,field):
        rows=tables.get(table)
        if not rows:return None
        values=[r[field] for r in rows if r.get(field) is not None]
        return sum(values) if values else None
    return {name:total(table,field) for name,table,field in [
        ('sales_rm','sales','recorded_package_face_value_rm'),('packages','sales','countable_package_rows'),
        ('bookings','services','scheduled_service_event_rows'),('warranty_visits','services','warranty_claim_event_rows'),
        ('contract_sales_rm','payments','recorded_contract_value_rm'),('paid_rm','payments','sales_total_recorded_paid_rm'),
        ('remaining_rm','payments','positive_recorded_remaining_balance_rm'),
        ('reminders_next7','payments','contracts_with_scheduled_reminders_next_7_days'),
        ('missing_reminders','payments','contracts_without_source_schedule')]}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',default='outputs/portal');args=p.parse_args()
    result=refresh(args.output)
    print(json.dumps({'status':result['status'],'table_rows':{k:len(v) for k,v in result['tables'].items()}}))
