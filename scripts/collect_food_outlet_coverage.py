"""Bounded coverage check using the existing approved Geoapify connection."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import json,os,hashlib,sys
import pandas as pd
from scripts.fetch_environmental_context import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261017_new_environment_sources'
CACHE=ROOT/'data/processed/environment/food_outlet_context_20261017.jsonl'

def main():
    OUT.mkdir(parents=True,exist_ok=True);load_dotenv()
    key=os.environ.get('NOMOBUG_GEOAPIFY_API_KEY','').strip()
    if not key:raise ValueError('Existing Geoapify credential unavailable')
    all_locations=pd.read_json(ROOT/'data/processed/environment/geoapify_environment_places_v2.jsonl',lines=True)
    full='--all-cached-locations' in sys.argv
    selected=all_locations.sort_values('location_id').sample(n=len(all_locations) if full else min(100,len(all_locations)),random_state=1700)
    existing={json.loads(line)['location_id']:json.loads(line) for line in CACHE.read_text().splitlines()} if CACHE.exists() else {}
    def fetch(row):
        if row.location_id in existing:return existing[row.location_id]
        base={'location_id':row.location_id,'observed_at_utc':datetime.now(timezone.utc).isoformat(),'historical_validity':'unverified; do not use for past-service model evaluation','radius_m':500,'provider':'geoapify_openstreetmap','categories':'catering.restaurant,catering.cafe,catering.fast_food,catering.food_court'}
        params={'categories':base['categories'],'filter':f'circle:{row.longitude},{row.latitude},500','bias':f'proximity:{row.longitude},{row.latitude}','limit':200,'apiKey':key}
        try:
            request=Request('https://api.geoapify.com/v2/places?'+urlencode(params),headers={'User-Agent':'Nomobug-capstone-source-audit/1.0'})
            with urlopen(request,timeout=30) as response:data=json.load(response)
            features=data.get('features')
            if not isinstance(features,list):return base|{'status':'invalid_response'}
            ids={p.get('properties',{}).get('place_id') for p in features};ids.discard(None)
            distances=[p['properties']['distance'] for p in features if isinstance(p.get('properties',{}).get('distance'),(int,float))]
            return base|{'status':'ok','mapped_objects_500m':len(features),'distinct_provider_place_ids':len(ids),'result_capped':len(features)>=200,'nearest_mapped_outlet_within_500m_m':min(distances) if distances else None,'count_interpretation':'Mapped objects; not independently deduplicated business outlets or verified absence when zero'}
        except Exception as exc:return base|{'status':'request_failed','error_type':type(exc).__name__}
    with ThreadPoolExecutor(max_workers=4) as pool:
        with CACHE.open('a',encoding='utf-8') as stream:
            rows=[]
            for row in pool.map(fetch,selected.itertuples()):
                rows.append(row)
                if row['location_id'] not in existing:stream.write(json.dumps(row)+'\n');stream.flush()
    successful=[r for r in rows if r['status']=='ok']
    summary={'observed_utc':datetime.now(timezone.utc).isoformat(),'cache_population':len(all_locations),'sampled_locations':len(rows),'selection':'Deterministic random sample, seed 1700; archived cache only, not every customer','successful_requests':len(successful),'failed_requests':len(rows)-len(successful),'locations_with_mapped_food_within_500m':sum(r['mapped_objects_500m']>0 for r in successful),'capped_results':sum(r['result_capped'] for r in successful),'historically_validated_training_rows':0,'frozen_model_changed':False,'cache_sha256':hashlib.sha256(CACHE.read_bytes()).hexdigest(),'source':'https://apidocs.geoapify.com/docs/places/','remaining':'Full population collection, historical opening/closing dates, mapping completeness and business deduplication. Current observations do not support a claimed historical accuracy improvement.'}
    if full:
        summary['selection']='All locations in the archived environmental cache; not every current customer'
        summary['remaining']='Historical opening/closing dates, current-customer alignment, geolocation precision and business deduplication. Capped counts are lower bounds; no historical accuracy claim.'
    (OUT/'food_coverage_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
