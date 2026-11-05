"""Restore one archived release from the 16 October cleanup receipt."""
import argparse,json
from pathlib import Path
from google.cloud import bigquery
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/project_audit/20261016_bigquery_cleanup'
PROJECT='profound-keel-500007-s4'
def main():
 p=argparse.ArgumentParser();p.add_argument('--dataset',required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
 receipt=json.loads((OUT/'cleanup_receipt_private.json').read_text())
 if a.dataset not in receipt['removed']:raise ValueError('Dataset is not in the removal receipt')
 records=json.loads((OUT/'inventory_before_private.json').read_text())
 r=next(r for r in records if r['dataset']['datasetReference']['datasetId']==a.dataset)
 print(json.dumps({'restore_dataset':a.dataset,'objects':len(r['tables']),'apply':a.apply}))
 if not a.apply:return
 c=bigquery.Client(project=PROJECT);raw=r['dataset'];d=bigquery.Dataset(PROJECT+'.'+a.dataset)
 d.location=raw['location'];d.friendly_name=raw.get('friendlyName');d.description=raw.get('description');d.labels=raw.get('labels',{})
 c.create_dataset(d,exists_ok=True)
 for t in r['tables']:
  if t['type']=='TABLE':
   table=t['tableReference']['tableId'];source=f"{PROJECT}.{receipt['archive_dataset']}.{a.dataset}__{table}"
   c.copy_table(source,f'{PROJECT}.{a.dataset}.{table}',job_config=bigquery.CopyJobConfig(write_disposition='WRITE_EMPTY')).result()
 for t in r['tables']:
  if t['type']=='VIEW':
   table=bigquery.Table.from_api_repr(t);c.create_table(table,exists_ok=True)
 print('Restored. Restore paired silver/gold datasets as needed before querying views.')
if __name__=='__main__':main()
