"""Collect public OSM candidate context; never treat current mapping as past truth."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,time
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261017_new_environment_sources'
RAW=ROOT/'data/processed/environment/candidate_osm_20261017.json'
URL='https://overpass.kumi.systems/api/interpreter'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    locations=pd.read_json(ROOT/'data/processed/environment/geoapify_environment_places_v2.jsonl',lines=True)
    south,west=float(locations.latitude.min())-.025,float(locations.longitude.min())-.025
    north,east=float(locations.latitude.max())+.025,float(locations.longitude.max())+.025
    bbox=f'{south},{west},{north},{east}'
    query=f'''[out:json][timeout:90];(
      nwr[amenity~"^(restaurant|cafe|fast_food|food_court|marketplace)$"]({bbox});
      nwr[man_made~"^(wastewater_plant|water_works)$"]({bbox});
      nwr[building][start_date]({bbox});
      nwr[building][year_of_construction]({bbox});
      nwr[building]["building:year_built"]({bbox});
    );out center tags;'''
    receipt={'queried_at_utc':datetime.now(timezone.utc).isoformat(),'endpoint':URL,'bbox':[south,west,north,east],
      'query':query,'scope':'Current public-map coverage audit. Not aligned to historical service dates; not trained.',
      'cached_location_population':len(locations),'location_scope':'Existing archived environmental cache; not every current customer'}
    (OUT/'request_receipt.json').write_text(json.dumps(receipt,indent=2))
    if not RAW.exists():
        try:
            req=Request(URL,data=urlencode({'data':query}).encode(),headers={'User-Agent':'Nomobug-capstone-source-audit/1.0'})
            with urlopen(req,timeout=115) as response:raw=response.read()
            data=json.loads(raw)
            if data.get('remark'):raise ValueError('Overpass returned an incomplete result')
            RAW.write_bytes(raw)
        except Exception as exc:
            (OUT/'fetch_failure.json').write_text(json.dumps({'type':type(exc).__name__,'message':'Public endpoint request failed; no model data changed','time_utc':datetime.now(timezone.utc).isoformat()},indent=2));raise
    data=json.loads(RAW.read_text());assert not data.get('remark')
    points=[]
    for e in data.get('elements',[]):
        tags=e.get('tags',{});pos=e.get('center',e)
        if 'lat' not in pos or 'lon' not in pos:continue
        kind='food_outlet' if tags.get('amenity') in ['restaurant','cafe','fast_food','food_court','marketplace'] else ('sewage_treatment' if tags.get('man_made')=='wastewater_plant' else ('drinking_water_treatment' if tags.get('man_made')=='water_works' else 'building_date_tag'))
        date=tags.get('start_date') or tags.get('year_of_construction') or tags.get('building:year_built')
        points.append({'osm_id':f"{e['type']}/{e['id']}",'kind':kind,'latitude':pos['lat'],'longitude':pos['lon'],'date_tag':date,
            'date_validated':False,'geometry':'representative_point_or_centre','historical_validity':'not_verified'})
    points=pd.DataFrame(points)
    if points.empty:raise ValueError('No usable points returned')
    points.to_csv(OUT/'public_candidate_points.csv',index=False)
    coverage=[];location_context=locations[['location_id','latitude','longitude']].copy()
    for kind,part in points.groupby('kind'):
        tree=BallTree(np.radians(part[['latitude','longitude']].to_numpy()),metric='haversine')
        distances,_=tree.query(np.radians(locations[['latitude','longitude']].to_numpy()),k=1);distances=distances[:,0]*6371008.8
        counts=tree.query_radius(np.radians(locations[['latitude','longitude']].to_numpy()),r=500/6371008.8,count_only=True)
        location_context[kind+'_nearest_m']=distances;location_context[kind+'_mapped_objects_500m']=counts
        coverage.append({'candidate':kind,'mapped_objects_in_bbox':len(part),'cached_locations_with_object_within_500m':int((counts>0).sum()),'cached_locations':len(locations),'historically_usable_training_rows':0,
          'limitation':'Building proximity does not establish building identity or age. Map objects may duplicate one business. Current map snapshot is not historical evidence.'})
    location_context.to_csv(OUT/'location_context_private.csv',index=False)
    pd.DataFrame(coverage).to_csv(OUT/'coverage_summary.csv',index=False)
    receipt.update({'raw_sha256':hashlib.sha256(RAW.read_bytes()).hexdigest(),'osm_timestamp':data.get('osm3s',{}).get('timestamp_osm_base'),'objects':len(points),'frozen_model_modified':False})
    (OUT/'source_receipt.json').write_text(json.dumps(receipt,indent=2))
    print(pd.DataFrame(coverage).drop(columns=['limitation']).to_string(index=False))

if __name__=='__main__':main()
