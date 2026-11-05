"""Publish reconciled spatial sidecars and private runtime data after queue repair."""
from datetime import datetime,timezone
import hashlib,json
from urllib.parse import quote
from google.cloud import bigquery
from scripts.release_business_analytics import run
from scripts.resolve_unmapped_purchase_batch import ROOT,OUT
from webapp.spatial import location
from webapp import data,storage

def main():
    folder=ROOT/'outputs/address_review/20261017_after'
    before=json.loads((OUT/'business_records_private.json').read_text())
    previous=json.loads((folder/'business_records_private.json').read_text()) if (folder/'business_records_private.json').exists() else before
    protected={r['sale_id'] for r in previous['sales'] if location(r.get('location'))}
    candidate=run(folder,publish=False)
    records=json.loads((folder/'business_records_private.json').read_text())
    def year(rows):return [r for r in rows['sales'] if str(r.get('date') or '').startswith('2026-')]
    old,new=year(before),year(records)
    assert {r['sale_id'] for r in old}=={r['sale_id'] for r in new},'Published source changed; reconcile first'
    old_mapped=sum(location(r.get('location')) is not None for r in old)
    new_mapped=sum(location(r.get('location')) is not None for r in new)
    assert new_mapped>=old_mapped,'Mapping regression; do not publish'
    assert protected.issubset({r['sale_id'] for r in records['sales'] if location(r.get('location'))}),'Previously mapped purchase lost; do not publish'
    # run() reconciles source-to-Gold sale totals before changing any sidecar view.
    release=run(folder,publish=True)
    assert release['published_release']==candidate['published_release']
    client=bigquery.Client(project=data.PROJECT,location='asia-southeast1')
    data.refresh(folder,client=client);client.close()
    session=storage.authorized_session()
    endpoint='https://run.googleapis.com/v2/projects/profound-keel-500007-s4/locations/asia-southeast1/jobs/cp2-reporting-daily'
    response=session.get(endpoint,timeout=30);response.raise_for_status()
    env=response.json()['template']['template']['containers'][0]['env']
    uri=next(e['value'] for e in env if e['name']=='CP2_PORTAL_GCS_URI')
    bucket,prefix=storage.location(uri)
    backup=folder/'cloud_previous';backup.mkdir(exist_ok=True)
    for name in ['business_snapshot.json','business_tools_private.json']:
        obj='/'.join(filter(None,[prefix,name]));url=f'https://storage.googleapis.com/storage/v1/b/{quote(bucket,safe="")}/o/{quote(obj,safe="")}?alt=media'
        previous=session.get(url,timeout=30);previous.raise_for_status();(backup/name).write_bytes(previous.content)
    published={}
    for name in ['business_snapshot.json','business_tools_private.json']:
        published[name]=storage.publish_business(uri,folder,session=session,name=name)
        obj='/'.join(filter(None,[prefix,name]));url=f'https://storage.googleapis.com/storage/v1/b/{quote(bucket,safe="")}/o/{quote(obj,safe="")}?alt=media'
        check=session.get(url,timeout=30);check.raise_for_status()
        assert hashlib.sha256(check.content).hexdigest()==hashlib.sha256((folder/name).read_bytes()).hexdigest()
    result={'finished_utc':datetime.now(timezone.utc).isoformat(),'source_release':release['published_release'],'purchases_2026':len(new),'mapped_before':old_mapped,'mapped_after':new_mapped,'unmapped_before':len(old)-old_mapped,'unmapped_after':len(new)-new_mapped,'mapped_gain':new_mapped-old_mapped,'KPI_reconciliation':'passed in both candidate and published export','private_cloud_files_verified':list(published),'dashboard_editor_changed':False,'frozen_model_changed':False}
    (folder/'publication_acceptance.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
