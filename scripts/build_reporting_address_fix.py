"""Upload an explicit source allowlist and build the repaired reporting image."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,tarfile,uuid,yaml
import google.auth
from google.auth.transport.requests import AuthorizedSession

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/address_review/20261017'

def main():
    names={'deploy/Dockerfile','deploy/requirements-reporting.txt'}
    docker=(ROOT/'deploy/Dockerfile').read_text()
    names.update(re.findall(r'scripts/[a-zA-Z0-9_]+\.py',docker))
    for directory in ['dbt','webapp']:
        for p in (ROOT/directory).rglob('*'):
            if not p.is_file():continue
            rel=p.relative_to(ROOT);parts=set(rel.parts)
            if parts&{'__pycache__','target','logs','dbt_packages'} or p.suffix=='.pyc' or p.name=='.user.yml':continue
            if not p.resolve().is_relative_to(ROOT):raise ValueError('Build source escaped project')
            names.add(rel.as_posix())
    names.add('data/processed/boundaries/dosm_districts.geojson')
    for name in names:
        if any(word in name.lower() for word in ['.env','private','credentials','token.json','.joblib']):raise ValueError('Disallowed build path')
    archive=OUT/'reporting_address_fix_source.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for name in sorted(names):tar.add(ROOT/name,arcname=name,recursive=False)
    (OUT/'build_source_manifest.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'files':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(names)},'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'exclusions':'No outputs, address caches, .env, credentials or private customer exports'},indent=2))
    session=AuthorizedSession(google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])[0])
    bucket='profound-keel-500007-s4_cloudbuild';obj='source/cp2-address-field-fix-'+uuid.uuid4().hex+'.tar.gz'
    response=session.post(f'https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o',params={'uploadType':'media','name':obj,'ifGenerationMatch':'0'},data=archive.read_bytes(),headers={'Content-Type':'application/gzip'},timeout=90);response.raise_for_status()
    spec=yaml.safe_load((ROOT/'deploy/cloudbuild.reporting.yaml').read_text());spec['source']={'storageSource':{'bucket':bucket,'object':obj}}
    response=session.post('https://cloudbuild.googleapis.com/v1/projects/profound-keel-500007-s4/locations/global/builds',json=spec,timeout=60);response.raise_for_status()
    d=response.json();build=d.get('metadata',{}).get('build',{})
    receipt={'operation':d['name'],'build_id':build.get('id'),'status':build.get('status'),'source_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'file_count':len(names)}
    (OUT/'reporting_build_operation.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
