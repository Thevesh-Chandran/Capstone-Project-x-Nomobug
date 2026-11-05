"""Update only the existing reporting job image after successful cloud smoke."""
import hashlib,json
from datetime import datetime,timezone
import google.auth
from google.auth.transport.requests import AuthorizedSession
from scripts.resolve_unmapped_purchase_batch import OUT

def main():
    built=json.loads((OUT/'reporting_build_operation.json').read_text())
    if built.get('status')!='SUCCESS' or not built.get('image_digest'):raise ValueError('Build and smoke must succeed first')
    session=AuthorizedSession(google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])[0])
    name='projects/profound-keel-500007-s4/locations/asia-southeast1/jobs/cp2-reporting-daily';url='https://run.googleapis.com/v2/'+name
    response=session.get(url,timeout=30);response.raise_for_status();old=response.json()
    containers=old['template']['template']['containers'];old_image=containers[0]['image']
    image=built['image'].rsplit(':',1)[0]+'@'+built['image_digest'];containers[0]['image']=image
    # Jobs.patch accepts the Job resource (no updateMask parameter). Preserve
    # its full execution template, including identity, limits and secret refs.
    body={k:old[k] for k in ['name','description','labels','annotations','launchStage','binaryAuthorization','etag','template'] if k in old}
    response=session.patch(url,json=body,timeout=60);response.raise_for_status();operation=response.json()
    receipt={'requested_utc':datetime.now(timezone.utc).isoformat(),'job':name,'old_image':old_image,'new_image':image,'operation':operation['name'],'build_id':built['build_id'],'scope':'Existing reporting job image only; credentials, schedules, task limits and frozen collector unchanged'}
    (OUT/'reporting_deployment_operation.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
