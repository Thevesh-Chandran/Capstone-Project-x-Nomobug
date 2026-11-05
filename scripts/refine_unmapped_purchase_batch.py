"""Bounded three-worker refinement, reusing audited selection and match guards."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,os,threading,time,sys
from google.cloud import bigquery
from scripts.resolve_unmapped_purchase_batch import ROOT,OUT,g,load_dotenv,safe_peer,rank,hints

def main():
    load_dotenv();key=os.environ['NOMOBUG_GEOAPIFY_API_KEY'];google=os.environ.get('NOMOBUG_GOOGLE_MAPS_API_KEY')
    receipt=json.loads((OUT/'business_receipt.json').read_text());prefix=receipt['published_release']
    targets=json.loads((OUT/'unmapped_purchase_review_private.json').read_text())
    client=bigquery.Client(project=g.PROJECT,location=g.LOCATION);cache=g.load_cache(client)
    raw=g.query(client,f'SELECT address_raw FROM `{g.PROJECT}.{prefix}_silver.sales` WHERE address_raw IS NOT NULL')
    trusted=[]
    for row in raw:
        address=g.clean_sales_address(row['address_raw']);old=g.sales_cache_record(cache,row['address_raw']) if address else None
        if old and old.get('status')=='accepted' and old.get('precision_tier') in ('precise_candidate','street_candidate','manual_verified') and g.valid_point(old):trusted.append(dict(old,input_address=address))
    work={}
    for row in targets:
        if '--only-new-address-shapes' in sys.argv and g.address_key(row['Address in Sales'],explicit_address_field=True)==g.address_key(row['Address in Sales']):continue
        address=g.clean_sales_address(row['Address in Sales']);hashed=g.address_key(address,explicit_address_field=True) if address else None;old=g.sales_cache_record(cache,row['Address in Sales']) or {}
        if hashed and not old.get('manual_override_protected') and not (old.get('status')=='accepted' and old.get('precision_tier') in g.MAP_TIERS):work[hashed]=(address,old)
    stop=threading.Event();peer_only='--peer-only' in sys.argv
    if peer_only:stop.set()
    def resolve(item):
        hashed,(address,old)=item;counts=Counter();best=None;method=None
        peer=safe_peer(address,trusted)
        if peer:
            best={k:peer.get(k) for k in ['latitude','longitude','geocode_provider','provider_result_type','provider_confidence','postcode_agrees']}
            best.update({'precision_tier':'street_candidate','status':'accepted','coordinate_source':'trusted_address_peer','peer_address_hash':peer['address_hash'],'manual_override_protected':False});method='strict_trusted_address_peer'
        if best is None and not stop.is_set():
            for query in dict.fromkeys([address,g.geo.without_leading_premise(address)]):
                if stop.is_set():break
                try:
                    result=g.geo.geocode(query,key,20);counts['rerank_requests']+=1
                    proposed=g.resolved_record(hashed,address,result,datetime.now(timezone.utc))
                    if proposed['status']=='accepted' and proposed['precision_tier'] in g.MAP_TIERS and rank(proposed)>rank(old):best=proposed;method='validated_rerank';break
                except g.geo.GeoapifyRequestError as exc:
                    counts['provider_errors']+=1
                    if str(exc) in ('HTTP 401','HTTP 403','HTTP 429'):stop.set()
                time.sleep(.4)
        if best is None and google and not stop.is_set():
            try:
                places=hints.google_places(address,google);counts['transient_google_requests']+=1
                hint=hints.select_place_hint(address,places)
                if hint:
                    query,fields=hints.enriched_query(address,hint)
                    if fields:
                        result=g.geo.geocode(query,key,20);counts['hinted_geoapify_requests']+=1
                        proposed=hints.proposed_record({'input_address':address,'address_hash':hashed,'calendar_event_rows':[]},result,fields,hints.geoapify_matches_hint(hint,result))
                        tier=g.geo.analysis_tier(proposed)
                        candidate=g.resolved_record(hashed,address,result,datetime.now(timezone.utc))
                        if tier in g.MAP_TIERS and rank({'precision_tier':tier})>rank(old):
                            candidate['precision_tier']=tier;candidate['postcode_agrees']=proposed.get('postcode_agrees');candidate['coordinate_source']='geoapify_after_transient_google_place_hint';best=candidate;method='validated_locality_hint'
            except (hints.GooglePlacesRequestError,g.geo.GeoapifyRequestError) as exc:
                counts['hint_errors']+=1
                if str(exc) in ('HTTP 401','HTTP 403','HTTP 429'):stop.set()
        if best:
            now=datetime.now(timezone.utc).isoformat();best.update({'address_hash':hashed,'attempted_at':now,'geocoded_at_utc':now});counts[method]+=1
        return best,dict(counts),hashed
    print(f'Refining {len(work)} remaining distinct addresses with at most three workers.',flush=True)
    counts=Counter();updates=[];reviewed=0;unresolved=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(resolve,item) for item in work.items()]
        for future in as_completed(futures):
            row,stats,hashed=future.result();counts.update(stats);reviewed+=1
            if row:updates.append(row)
            else:unresolved.append(hashed)
            if len(updates)>=10:g.save_cache(client,updates);updates=[]
            if reviewed%10==0:print(f'Reviewed {reviewed}/{len(work)}; '+json.dumps(dict(counts)),flush=True)
    g.save_cache(client,updates);client.close()
    result={'completed_utc':datetime.now(timezone.utc).isoformat(),'input_addresses':len(work),'reviewed':reviewed,'methods':dict(counts),'remaining_distinct_addresses':len(unresolved),'provider_circuit_stopped':stop.is_set() and not peer_only,'mode':'offline_peer_only' if peer_only else 'provider_refinement','no_google_response_or_coordinate_storage':True,'manual_overrides_preserved':True,'publication':'Validated cache improvements saved; website refresh follows separately.'}
    name='new_shape_refinement_receipt.json' if '--only-new-address-shapes' in sys.argv else ('peer_reuse_receipt.json' if peer_only else 'refinement_receipt.json')
    (OUT/name).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
