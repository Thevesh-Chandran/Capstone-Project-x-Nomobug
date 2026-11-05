"""Apply readable BigQuery metadata and export an object guide without renaming IDs.

Backs up every modified resource before applying. No row edits, data queries,
permission changes, table deletion or model replacement. Creates a constant-only
analytics_ml.READ_ME view describing the existing research objects.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import pandas as pd
from google.cloud import bigquery

ROOT=Path(__file__).resolve().parents[1]
PROJECT='profound-keel-500007-s4'
OUT=ROOT/'outputs/project_audit/20261025_organisation'
ROLES={
 'gold':('01 - Management reporting','Approved management sources. Start with READ_ME. Sales are recorded package prices; Calendar visits are bookings; payment reminder dates do not establish payment or nonpayment.'),
 'silver':('02 - Data cleaning','Typed and linked source records produced by dbt. Transformation definitions: dbt/models. This layer is not a separate sales total.'),
 'bronze':('03 - Source snapshots','Immutable source extracts and supporting inputs. Retain snapshot lineage; do not edit raw records to change reports.'),
 'analytics_ml':('04 - Model research','Historical model data and comparison outputs. Start with READ_ME. Current frozen pest model is governed by config/cp2_model_current.json; these table versions are not automatically active models.'),
 'audit':('05 - Run and collection records','Reporting run, release and experimental collection evidence. A missed prediction remains missing; do not backfill it as timely evidence.'),
 'quality':('06 - Data checks','Coverage, source and reconciliation checks. Results describe the named snapshots and checks, not guaranteed source correctness.'),
 'archived_reporting_releases':('Archive - Reporting recovery','Recovery snapshots retained from prior release cleanup. Not a management dashboard data source.'),
}
TITLES={
 'READ_ME':'Start here - Source guide','sales':'Sales','customers':'Customers','appointments':'Scheduled appointments',
 'payment_reminders':'Payment reminder schedule','payment_data_checks':'Payment data checks','refunds':'Recorded refunds',
 'team_schedule':'Team booking schedule','area_sales':'Sales by location','model_results':'Model evaluation summary',
 'dashboard_recurring_reminder_schedule':'Contract payment reminders','dashboard_recurring_payment_summary':'Contract payment summary',
 'dashboard_upcoming_appointments':'Upcoming team bookings','dashboard_model_review':'Experimental model evidence',
 'warranty_callback_fixed_horizon_dataset':'Recorded return - Fixed 30-day service windows',
 'warranty_callback_flood_dataset':'Recorded return - Flood-context research data',
 'warranty_fixed_horizon_dataset':'Warranty research - Fixed outcome windows',
 'warranty_anchor_environment_features':'Service-date environmental inputs',
}

def title(name):
    return TITLES.get(name,name.replace('dashboard_','').replace('_',' ').capitalize().replace(' rm',' (RM)'))

def purpose(dataset,name):
    if name=='READ_ME': return 'Constant-only index of source names, roles and limitations. No customer records.'
    if name in {'sales','dashboard_sales_monthly','dashboard_sales_overview'}: return 'Recorded package sales; not cash receipts or profit. Preserve source grain and refund separation.'
    if 'recurring' in name or name=='payment_reminders': return 'Contract reminder/amount evidence at the named view grain. A date passing does not mean paid, unpaid or reminder sent; use recorded cumulative paid and remaining amounts.'
    if 'refund' in name: return 'Recorded refunds. Missing dates are unknown; do not silently remove them or net unrelated totals.'
    if 'appointment' in name or name=='team_schedule': return 'Scheduled Calendar service bookings/team-slot duration. Excludes events according to the governed classification; not independently verified completed treatments or staff productivity.'
    if dataset=='analytics_ml':
        detail='Historical research artifact. '
        if 'predictions' in name: detail+='Saved predictions for the named study; not automatically independent or prospective evidence. '
        elif 'dataset' in name or 'features' in name or 'episodes' in name: detail+='Study-specific labelled rows or inputs; verify horizon, source snapshot and as-of rules before use. '
        elif 'metrics' in name or 'evaluation' in name or 'summary' in name: detail+='Study-specific evaluation; compare only matching targets, periods and populations. '
        else: detail+='Study-specific inputs, selection or diagnostics. '
        return detail+'The current frozen model is identified in config/cp2_model_current.json. Project reading: notebooks/03_Outcome_Labels_and_Partitions.ipynb through 07_Model_Experiments.ipynb.'
    if dataset=='silver': return 'Cleaned/linked source model. SQL: dbt/models/'+name+'.sql. See notebooks/02_Data_Cleaning.ipynb. Source missingness and linking uncertainty remain material.'
    if dataset=='quality': return 'Data-quality or coverage check output. Check source release, denominator and freshness; absence of a flag is not proof of complete data.'
    if dataset=='audit': return 'Pipeline run/collection evidence. Keep original timing, statuses, release references and failures.'
    return title(name)+'. Consult dbt/models/gold and BUSINESS_ANALYTICS.md for the exact grain, calculation and filters.'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    client=bigquery.Client(project=PROJECT)
    datasets=list(client.list_datasets())
    metadata=[]
    for ds in datasets:
        if ds.dataset_id in ROLES or ds.dataset_id.startswith(('cp2r_','cp2qa_')):
            metadata.append(client.get_dataset(ds.reference))
    objects=[]
    for ds in ['gold','silver','analytics_ml','audit','quality']:
        objects.extend(client.list_tables(PROJECT+'.'+ds))
    with ThreadPoolExecutor(max_workers=6) as pool:
        tables=list(pool.map(lambda t:client.get_table(t.reference),objects))
    # Timestamped backup protects the previous metadata, including READ_ME SQL.
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=OUT/('bigquery_metadata_before_'+stamp+'.json')
    backup.write_text(json.dumps({'datasets':[d.to_api_repr() for d in metadata],
                                 'tables':[t.to_api_repr() for t in tables]},indent=2),encoding='utf-8')
    changes=[]
    for ds in metadata:
        name=ds.dataset_id
        if name in ROLES: friendly,description=ROLES[name]; role=name
        else:
            match=re.match(r'cp2r_(\d{8})(\d{6})',name)
            date=match.group(1) if match else 'unknown'
            layer='Gold' if name.endswith('_gold') else 'Silver'
            clock=match.group(2) if match else '000000'
            friendly='Release '+date[:4]+'-'+date[4:6]+'-'+date[6:8]+' '+clock[:2]+':'+clock[2:4]+' UTC - '+layer
            description='Versioned immutable reporting release. Technical ID '+name+'. Stable silver/gold views control which release is currently published. Preserve references and rollback dependencies; date alone is not permission to delete.'
            role='release'
        ds.friendly_name=friendly
        ds.description=description
        ds.labels={**(ds.labels or {}),'cp2_role':role,'cp2_project':'nomobug'}
        client.update_dataset(ds,['friendly_name','description','labels'])
        changes.append({'dataset':name,'name':friendly})
    rows=[]
    def update(t):
        ds=t.dataset_id;name=t.table_id
        friendly=title(name)
        if ds=='analytics_ml' and name!='READ_ME': friendly='Research - '+friendly
        explanation=purpose(ds,name)
        marker='\n\nCP2 FILE GUIDE (2026-10-25)\n'
        prior=(t.description or '').split(marker)[0]
        t.description=(prior+marker+explanation).strip()
        t.friendly_name=friendly[:1024]
        client.update_table(t,['friendly_name','description'])
        return {'Dataset':ds,'Table ID':name,'Readable name':friendly,'Type':t.table_type,'Purpose':explanation,
                'Use':'Historical research; check protocol' if ds=='analytics_ml' else 'Current stable layer; check source grain'}
    with ThreadPoolExecutor(max_workers=6) as pool: rows=list(pool.map(update,tables))
    research=[r for r in rows if r['Dataset']=='analytics_ml' and r['Table ID']!='READ_ME']
    parts=[]
    for r in research:
        parts.append('SELECT '+json.dumps(r['Readable name'])+' AS name, '+json.dumps('analytics_ml.'+r['Table ID'])+' AS use_this_source, '+json.dumps(r['Purpose'])+' AS meaning')
    guide=bigquery.Table(PROJECT+'.analytics_ml.READ_ME')
    guide.view_query='\nUNION ALL\n'.join(parts)
    guide.friendly_name='Start here - Model research guide'
    guide.description='Index only. Current frozen model: config/cp2_model_current.json. Main notebooks: notebooks. Research table versions are not new active models.'
    try: client.get_table(guide.reference); client.update_table(guide,['view_query','friendly_name','description'])
    except __import__('google.api_core.exceptions',fromlist=['NotFound']).NotFound: client.create_table(guide)
    (ROOT/'project_guide').mkdir(exist_ok=True)
    pd.DataFrame(rows).sort_values(['Dataset','Table ID']).to_csv(ROOT/'project_guide/BigQuery_Catalogue.csv',index=False)
    receipt={'at_utc':datetime.now(timezone.utc).isoformat(),'datasets':changes,'tables_described':len(rows),
             'guide':'analytics_ml.READ_ME','backup':str(backup.relative_to(ROOT)),'renamed_ids':[],
             'deleted_objects':[],'row_edits':[],'permissions_changed':False}
    (OUT/'bigquery_organisation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({'datasets':len(changes),'tables':len(rows),'guide':'analytics_ml.READ_ME','backup':str(backup)}))

if __name__=='__main__':main()
