"""Resolve the private review queue using existing conservative geocoding methods."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os,time,sys
from google.cloud import bigquery
from scripts import cp2_geocoding as g
from scripts.fetch_environmental_context import load_dotenv
from scripts.resolve_geocode_review_by_peer_address import peer_score
from scripts.annotate_geoapify_postcode_proximity import haversine_km
from scripts import retry_geocodes_with_google_place_hints as hints

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/address_review/20261017'

def rank(record):
    return {'manual_review':0,'area_analysis_candidate':1,'text_agreement_candidate':1,'proximity_candidate':1,
            'google_hinted_area_candidate':1,'peer_address_candidate':1,'postcode_area_candidate':2,
            'street_candidate':3,'precise_candidate':4,'manual_verified':5,'area_reference_verified':3}.get(record.get('precision_tier'),0)

def safe_peer(address,trusted):
    target={'input_address':address};words,ids=g.geo.normalized_address_tokens(address)
    ranked=[]
    for peer in trusted:
        score=peer_score(target,peer)
        if score is None or score<.9:continue
        other,other_ids=g.geo.normalized_address_tokens(peer['input_address'])
        # Peer reuse cannot silently change house/unit/road identifiers.
        if ids!=other_ids:continue
        if len(words&other)<4 or len(words&other)/max(1,len(words))<.9:continue
        ranked.append((score,peer))
    ranked.sort(key=lambda x:x[0],reverse=True)
    if not ranked:return None
    best=ranked[0][1]
    for score,peer in ranked[1:]:
        if ranked[0][0]-score>.05:break
        if haversine_km(best['latitude'],best['longitude'],peer['latitude'],peer['longitude'])>1:return None
    return best

def main():
    load_dotenv();key=os.environ['NOMOBUG_GEOAPIFY_API_KEY'];google=os.environ.get('NOMOBUG_GOOGLE_MAPS_API_KEY')
    before=json.loads((ROOT/'outputs/model_validation/20261017_predictor_value/protocol.json').read_text())['frozen_hashes']
    targets=json.loads((OUT/'unmapped_purchase_review_private.json').read_text())
    receipt=json.loads((OUT/'business_receipt.json').read_text());prefix=receipt['published_release']
    client=bigquery.Client(project=g.PROJECT,location=g.LOCATION);cache=g.load_cache(client)
    sales=g.query(client,f'SELECT address_raw FROM `{g.PROJECT}.{prefix}_silver.sales` WHERE address_raw IS NOT NULL')
    found={}
    for row in targets:
        address=g.clean_sales_address(row['Address in Sales'])
        if address:found[g.address_key(address,explicit_address_field=True)]={'address':address,'priority':'2026-10-17','event_rows':[]}
    pending_cache=dict(cache)
    pending=[(k,v) for k,v in found.items() if g.due(cache.get(k),datetime.now(timezone.utc))]
    summary=Counter({'pending_before':len(pending),'attempted':0,'accepted':0,'manual_review':0,'no_result':0,'errors':0})
    print(f'Loaded cache; {len(found)} target addresses, {len(pending)} pending provider lookups.',flush=True)
    for offset in range(0,len(pending),20):
        batch=dict(pending[offset:offset+20])
        updates,part=g.perform(batch,pending_cache,key,max_requests=20,max_seconds=120)
        g.save_cache(client,updates);cache.update(pending_cache)
        for name in ['attempted','accepted','manual_review','no_result','errors']:summary[name]+=part[name]
        print('Saved pending batch: '+json.dumps(dict(summary)),flush=True)
        if part['errors']>=3 or any(r.get('error_code') in ('HTTP 401','HTTP 403','HTTP 429') for r in updates):break
    summary['pending_after']=summary['pending_before']-summary['attempted'];summary=dict(summary)
    print('Pending lookups: '+json.dumps(summary),flush=True)
    (OUT/'pending_lookup_receipt.json').write_text(json.dumps(summary,indent=2))
    if '--pending-only' in sys.argv:
        client.close();return
    trusted=[]
    for row in sales:
        address=g.clean_sales_address(row['address_raw']);record=cache.get(g.address_key(address,explicit_address_field=True)) if address else None
        if record and record.get('status')=='accepted' and record.get('precision_tier') in ('precise_candidate','street_candidate','manual_verified') and g.valid_point(record):
            trusted.append(dict(record,input_address=address))
    counts=Counter();applied=[];reviews=[];failures=0;stopped=bool(summary['errors'])
    for index,(hashed,item) in enumerate(found.items()):
        old=cache.get(hashed,{})
        if old.get('manual_override_protected'):counts['manual_protected']+=1;continue
        if old.get('status')=='accepted' and old.get('precision_tier') in g.MAP_TIERS:continue
        address=item['address'];best=None;method=None
        peer=safe_peer(address,trusted)
        if peer:
            best={k:peer.get(k) for k in ['latitude','longitude','geocode_provider','provider_result_type','provider_confidence','postcode_agrees']}
            best.update({'precision_tier':'street_candidate','status':'accepted','coordinate_source':'trusted_address_peer','peer_address_hash':peer['address_hash'],'manual_override_protected':False})
            method='strict_trusted_address_peer'
        if best is None and not stopped:
            queries=list(dict.fromkeys([address,g.geo.without_leading_premise(address)]))
            for text in queries:
                try:
                    result=g.geo.geocode(text,key,20);counts['rerank_provider_requests']+=1
                    candidate=g.resolved_record(hashed,address,result,datetime.now(timezone.utc));failures=0
                    if candidate.get('status')=='accepted' and candidate.get('precision_tier') in g.MAP_TIERS and rank(candidate)>rank(old):best=candidate;method='original_address_validated_rerank';break
                except g.geo.GeoapifyRequestError as exc:
                    failures+=1;counts['provider_failures']+=1
                    if str(exc) in ('HTTP 401','HTTP 403','HTTP 429') or failures>=3:stopped=True;break
                time.sleep(.3)
        if best is None and google and not stopped:
            try:
                places=hints.google_places(address,google);counts['transient_hint_requests']+=1
                hint=hints.select_place_hint(address,places)
                if hint:
                    query,fields=hints.enriched_query(address,hint)
                    if fields:
                        result=g.geo.geocode(query,key,20);counts['hinted_geoapify_requests']+=1
                        proposed=hints.proposed_record({'input_address':address,'address_hash':hashed,'calendar_event_rows':[]},result,fields,hints.geoapify_matches_hint(hint,result))
                        tier=g.geo.analysis_tier(proposed)
                        candidate=g.resolved_record(hashed,address,result,datetime.now(timezone.utc))
                        if tier in g.MAP_TIERS and candidate.get('precision_tier') in g.MAP_TIERS and rank(candidate)>rank(old):
                            candidate['precision_tier']=tier
                            candidate['postcode_agrees']=proposed.get('postcode_agrees')
                            best=candidate;best['coordinate_source']='geoapify_after_transient_google_place_hint';method='validated_transient_locality_hint'
            except (hints.GooglePlacesRequestError,g.geo.GeoapifyRequestError) as exc:
                counts['hint_failures']+=1
                if str(exc) in ('HTTP 401','HTTP 403','HTTP 429'):stopped=True
        if best:
            now=datetime.now(timezone.utc).isoformat();best.update({'address_hash':hashed,'attempted_at':now,'geocoded_at_utc':now})
            cache[hashed]=best;applied.append(best);counts[method]+=1
        else:reviews.append({'address_hash':hashed,'reason':'No safely more precise match obtained'})
        if len(applied)>=20:
            g.save_cache(client,applied);applied=[]
        if index%25==0:print(f'Reviewed {index+1}/{len(found)} addresses; '+json.dumps(counts),flush=True)
    g.save_cache(client,applied);client.close()
    frozen=ROOT/'outputs/cp2-v2/prospective_callback_v2'
    assert all(hashlib.sha256((frozen/name).read_bytes()).hexdigest()==digest for name,digest in before.items())
    result={'finished_utc':datetime.now(timezone.utc).isoformat(),'input_purchase_rows':len(targets),'distinct_usable_addresses':len(found),'pending_stage':summary,'refinement':dict(counts),'unresolved_distinct_addresses':len(reviews),'provider_circuit_stopped':stopped,'frozen_unchanged':True,'publication':'Cache updated append-only; published map must be refreshed and reconciled separately.','safety':'Existing manual matches protected. No Google responses/coordinates cached. No source Sheets/Calendar edits. No model changes.'}
    (OUT/'automatic_resolution_receipt.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
