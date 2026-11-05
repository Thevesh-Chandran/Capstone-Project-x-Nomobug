"""Inspect construction-date tag availability; proximity is not a building match."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib,json,os
from urllib.request import urlopen
from urllib.parse import urlencode
import pandas as pd
from scripts.fetch_environmental_context import load_dotenv
from scripts.collect_food_outlet_coverage import ROOT,OUT

def main():
    load_dotenv();key=os.environ['NOMOBUG_GEOAPIFY_API_KEY']
    cache=ROOT/'data/processed/environment/building_date_candidates_20261017.jsonl'
    locations=pd.read_json(ROOT/'data/processed/environment/geoapify_environment_places_v2.jsonl',lines=True).sort_values('location_id').sample(n=100,random_state=1700)
    existing={r['location_id']:r for r in map(json.loads,cache.read_text().splitlines())} if cache.exists() else {}
    def fetch(row):
        if row.location_id in existing:return existing[row.location_id]
        result={'location_id':row.location_id,'observed_at_utc':datetime.now(timezone.utc).isoformat(),'radius_m':100,'confirmed_building_match':False,'verified_age':None}
        url='https://api.geoapify.com/v2/places?'+urlencode({'categories':'building','filter':f'circle:{row.longitude},{row.latitude},100','bias':f'proximity:{row.longitude},{row.latitude}','limit':20,'apiKey':key})
        try:
            with urlopen(url,timeout=25) as response:data=json.load(response)
            features=data.get('features',[]);dates=[]
            for f in features:
                p=f.get('properties',{});raw=p.get('datasource',{}).get('raw',{})
                for field in ['start_date','year_of_construction','building:year_built']:
                    if field in raw and raw.get('building'):
                        dates.append({'place_id':p.get('place_id'),'date_field':field,'date_value':str(raw[field]),'meaning_unverified':True})
            return result|{'status':'ok','nearby_objects':len(features),'result_capped':len(features)>=20,'candidate_dates':dates}
        except Exception as exc:return result|{'status':'request_failed','error_type':type(exc).__name__}
    rows=[]
    with ThreadPoolExecutor(max_workers=2) as pool,cache.open('a',encoding='utf-8') as stream:
        for r in pool.map(fetch,locations.itertuples()):
            rows.append(r)
            if r['location_id'] not in existing:stream.write(json.dumps(r)+'\n');stream.flush()
    summary={'locations_checked':len(rows),'successful_requests':sum(r['status']=='ok' for r in rows),'locations_with_nearby_date_tag':sum(bool(r.get('candidate_dates')) for r in rows),'capped_responses':sum(r.get('result_capped',False) for r in rows),'verified_building_ages':0,'historically_usable_training_rows':0,'source':'https://apidocs.geoapify.com/docs/places/','cache_sha256':hashlib.sha256(cache.read_bytes()).hexdigest(),'limitation':'100 cached locations, not all customers. Nearby object or date tag does not verify customer building identity or construction date. Date may describe a business opening; unknown remains missing.'}
    (OUT/'building_date_coverage_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
