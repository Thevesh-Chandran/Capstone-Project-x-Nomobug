"""Authenticated cloud smoke checks; never print or persist the access code."""
import argparse,json,shutil,subprocess
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--output',required=True);p.add_argument('--allow-source-blocked',action='store_true');args=p.parse_args()
    session=requests.Session();base=args.url.rstrip('/')
    assert session.get(base+'/healthz',timeout=45).status_code==200
    assert session.get(base+'/api/planning',timeout=45).status_code==401
    result=subprocess.run([shutil.which('gcloud.cmd') or shutil.which('gcloud'),'secrets','versions','access','latest','--secret=cp2-portal-access-code','--project=profound-keel-500007-s4'],capture_output=True,check=True,timeout=60)
    secret=result.stdout.decode().strip()
    login=session.post(base+'/api/login',json={'token':secret},timeout=45);del secret,result
    assert login.status_code==200
    response=session.get(base+'/api/planning',timeout=90);response.raise_for_status();value=response.json()
    current=value['planning'];assert len(current['evidence']['models'])==2
    assert {r['id'] for r in current['evidence']['models']}=={'booking_entries_h2','booked_hours_h1'}
    expected=json.loads((ROOT/'webapp/models/planning_v1.json').read_text(encoding='utf-8'))
    assert current['evidence']['protocol_sha256']==expected['protocol_sha256']
    if not args.allow_source_blocked:assert current['live']['status']!='not_connected'
    assert not current['live'].get('forecasts'), 'Initial acceptance expects no backdated primary forecasts.'
    state=session.get(base+'/api/state',timeout=45).json()
    assert state['model']['bundle_sha256']=='6ace4314b4a5e170ea1bd6feee40dadbdd14eb3c986db9223d888b3c3ee302e0'
    html=session.get(base+'/',timeout=45).text
    assert 'Planning &amp; model evidence' in html
    js=session.get(base+'/tools.js',timeout=45).text;assert 'renderPlanningForecasts' in js
    assert 'Purple: four-week average estimate' not in js
    answer=session.post(base+'/api/assistant',json={'question':'Explain the weekly booking prediction model'},timeout=45).json()
    assert answer['provider']=='Verified project evidence'
    assert 'two weeks' in answer['answer'] and 'previous four complete weeks' not in answer['answer']
    receipt={'status':'PASS','url':base,'health':True,'unauthenticated_planning_denied':True,'two_models_present':True,
      'planning_source_status':current['live']['status'],'automatic_collection_verified':current['live']['status']!='not_connected','no_backdated_predictions':True,'original_frozen_hash_unchanged':True,
      'planning_ui_present':True,'assistant_uses_new_methods':True,'source_checked_at':current['live'].get('updated_at')}
    destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt))

if __name__=='__main__':main()
