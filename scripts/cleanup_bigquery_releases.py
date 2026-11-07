"""Archive unreferenced release datasets; dry-run unless --apply. Metadata receipt required."""
import argparse,json,re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from google.cloud import bigquery
ROOT=Path(__file__).resolve().parents[1]
PROJECT='profound-keel-500007-s4'
OUT=ROOT/'outputs/project_audit/20261016_bigquery_cleanup'
ARCHIVE='archived_reporting_releases'
PAT=re.compile(r'cp2(?:r|qa)_[a-z0-9]+_(?:gold|silver)')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
 if args.apply:
  raise RuntimeError('The October cleanup receipt is historical. Build and review a fresh dependency/rollback inventory before any new deletion; this legacy command is dry-run only.')
 records=json.loads((OUT/'inventory_before_private.json').read_text())
 by_name={r['dataset']['datasetReference']['datasetId']:r for r in records}
 protected={n for n in by_name if not n.startswith(('cp2r_','cp2qa_'))}
 rollback=(OUT/'latest_rollback_private.json').read_text()
 protected.update(PAT.findall(rollback))
 protected.update(json.loads((OUT/'looker_dependencies.json').read_text()))
 for root in ['config','scripts','infra','webapp','dbt/target','.github']:
  for file in (ROOT/root).rglob('*'):
   if file.is_file() and file.suffix in ('.py','.json','.sql','.yml','.yaml','.toml'):
    text=file.read_text(encoding='utf-8',errors='ignore')
    protected.update(PAT.findall(text))
    for prefix in re.findall(r'cp2r_[0-9a-z]+',text):
     protected.update(n for n in by_name if n.startswith(prefix+'_'))
 # Protect dependencies transitively from every non-release dataset, pinned
 # configuration and recent rollback definitions, including physical tables.
 changed=True
 while changed:
  before=len(protected)
  for name in list(protected):
   if name in by_name:protected.update(PAT.findall(json.dumps(by_name[name]['tables'])))
  changed=len(protected)>before
 candidates=sorted(n for n in by_name if n.startswith(('cp2r_','cp2qa_')) and n not in protected)
 plan={'protected':sorted(protected),'archive_candidates':candidates,'archive_dataset':ARCHIVE,
       'removed':[],'snapshots':[],'metadata_backup':'inventory_before_private.json'}
 (OUT/'cleanup_plan_private.json').write_text(json.dumps(plan,indent=2))
 print(json.dumps({'protected':len(protected),'archive_candidates':len(candidates),'apply':args.apply}),flush=True)
 if not args.apply:return
 c=bigquery.Client(project=PROJECT)
 locations={by_name[n]['dataset']['location'] for n in candidates}
 if len(locations)!=1:raise ValueError('Archive candidates must share one location')
 d=bigquery.Dataset(PROJECT+'.'+ARCHIVE);d.location=locations.pop();d.friendly_name='Archive â€” old reporting releases'
 d.description='Recovery copies only. Use gold for current management reporting. View definitions and restoration inventory are in CP2 outputs/project_audit/20261016_bigquery_cleanup.'
 c.create_dataset(d,exists_ok=True)
 cfg=bigquery.QueryJobConfig(maximum_bytes_billed=104857600)
 tasks=[]
 for name in candidates:
  for t in by_name[name]['tables']:
   if t['type'] not in ('TABLE','VIEW'):raise ValueError('Unsupported archive object type')
   if t['type']=='TABLE':tasks.append((name,t['tableReference']['tableId']))
 def snapshot(pair):
  name,table=pair;dest=f'{PROJECT}.{ARCHIVE}.{name}__{table}'
  c.query(f'CREATE SNAPSHOT TABLE IF NOT EXISTS `{dest}` CLONE `{PROJECT}.{name}.{table}`',job_config=cfg).result()
  check=c.get_table(dest)
  original=next(t for t in by_name[name]['tables'] if t['tableReference']['tableId']==table)
  if check.num_rows!=int(original.get('numRows',0)):raise ValueError('Archive row-count mismatch')
  return dest
 with ThreadPoolExecutor(max_workers=8) as ex:
  for dest in ex.map(snapshot,tasks):
   plan['snapshots'].append(dest)
   (OUT/'cleanup_receipt_private.json').write_text(json.dumps(plan,indent=2))
 # Re-read all retained views just before deletion; new dependency means stop.
 for name in protected:
  if name not in by_name:continue
  for t in c.list_tables(PROJECT+'.'+name):
   if t.table_type=='VIEW':
    sql=c.get_table(t.reference).view_query or ''
    if set(PAT.findall(sql))&set(candidates):raise ValueError('Retained view acquired archive dependency')
 for name in candidates:
  c.delete_dataset(PROJECT+'.'+name,delete_contents=True,not_found_ok=False)
  plan['removed'].append(name)
  (OUT/'cleanup_receipt_private.json').write_text(json.dumps(plan,indent=2))
 print(json.dumps({'datasets_removed':len(plan['removed']),'tables_snapshotted':len(plan['snapshots'])}),flush=True)

if __name__=='__main__':main()
