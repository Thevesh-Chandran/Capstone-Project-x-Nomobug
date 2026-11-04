"""Private, optimistic-concurrency ledger; separate from financial/source facts."""
import json,os,re,threading
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
from webapp import storage

class Conflict(ValueError):pass

class Store:
    def __init__(self,folder):self.folder=Path(folder);self.lock=threading.Lock()
    def load(self):
        uri=os.environ.get('CP2_ACTIONS_GCS_URI')
        if os.environ.get('K_SERVICE') and not uri:raise ValueError('Durable progress storage is not configured')
        if uri:
            bucket,prefix=storage.location(uri);obj=quote(prefix+'/state.json',safe='')
            session=storage.authorized_session();url=f'https://storage.googleapis.com/storage/v1/b/{bucket}/o/{obj}'
            meta=session.get(url,params={'fields':'generation'},timeout=15)
            if meta.status_code==404:return {'version':1,'records':{}},'0'
            meta.raise_for_status();generation=meta.json()['generation']
            response=session.get(url,params={'alt':'media','generation':generation},timeout=15);response.raise_for_status()
            if len(response.content)>1024*1024:raise ValueError('Action ledger exceeds its bound')
            value=response.json()
        else:
            p=self.folder/'workspace_actions.json'
            value=json.loads(p.read_text()) if p.exists() else {'version':1,'records':{}}
            generation=str(value.get('revision',0))
        if value.get('version')!=1 or not isinstance(value.get('records'),dict):raise ValueError('Invalid action ledger')
        return value,generation
    def update(self,key,change,expected,actor):
        if not re.fullmatch(r'[a-f0-9]{64}|capacity:\d{4}-\d{2}-\d{2}',key):raise ValueError('Invalid workspace item')
        with self.lock:
            state,generation=self.load()
            if str(expected)!=generation:raise Conflict('Another staff update arrived. Refresh before saving.')
            if key not in state['records'] and len(state['records'])>=1500:raise ValueError('Action ledger needs archival before adding items')
            state['records'][key]={**change,'updated_at':datetime.now(timezone.utc).isoformat(),'updated_by':actor}
            state['revision']=int(state.get('revision',0))+1
            raw=json.dumps(state,allow_nan=False).encode()
            if len(raw)>1024*1024:raise ValueError('Action ledger exceeds its bound')
            uri=os.environ.get('CP2_ACTIONS_GCS_URI')
            if uri:
                bucket,prefix=storage.location(uri)
                response=storage.authorized_session().post(f'https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o',
                    params={'uploadType':'media','name':prefix+'/state.json','ifGenerationMatch':generation},
                    data=raw,headers={'Content-Type':'application/json'},timeout=20)
                if response.status_code==412:raise Conflict('Another staff update arrived. Refresh before saving.')
                response.raise_for_status()
            else:
                self.folder.mkdir(parents=True,exist_ok=True);p=self.folder/'workspace_actions.json';temp=p.with_suffix('.next');temp.write_bytes(raw);os.replace(temp,p)
        return self.load()
