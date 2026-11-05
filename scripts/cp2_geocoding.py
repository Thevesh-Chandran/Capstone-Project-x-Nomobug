"""Bounded daily geocoding with an address-hash cache, separate from model training.

Only sanitised addresses are sent to Geoapify. The durable cache and receipts
never contain input addresses, descriptions, names, API keys or contact fields.
"""
from collections import Counter
from datetime import datetime,timedelta,timezone
import hashlib,json,math,os,re,time
from pathlib import Path
import sys

# The existing audited pilot helpers also support direct script execution.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0,str(Path(__file__).resolve().parent))
from scripts import pilot_geoapify_calendar as geo
from scripts.calendar_appointment_policy import is_confirmed_placeholder
from google.cloud import bigquery
from google.api_core.exceptions import NotFound

PROJECT='profound-keel-500007-s4'
LOCATION='asia-southeast1'
LIMIT=100*1024*1024
CACHE=PROJECT+'.quality.geocoding_address_cache'
BASELINE=PROJECT+'.quality.calendar_event_geocodes_all_v2'
USABLE={'precise_candidate','street_candidate','postcode_area_candidate','area_analysis_candidate','text_agreement_candidate','proximity_candidate','peer_address_candidate','google_hinted_area_candidate','manual_verified','area_reference_verified'}
MAP_TIERS={'precise_candidate','street_candidate','postcode_area_candidate','manual_verified','area_reference_verified'}
SIDE_FIELDS=['calendar_event_row','address_hash','latitude','longitude','geocode_provider','coordinate_source','manual_override_protected','precision_tier','provider_result_type','provider_confidence','postcode_agrees','geocoded_at_utc']

def clean_address(value):
    value=re.sub(r'(?i)\s+(?:nama|name|technician|remarks?|notes?|access\s+code|gate\s+code|password)\s*:.*$','',str(value or ''))
    value=re.sub(r'(?i)\s+TEAM\s+.*$','',value)
    text=geo.sanitized_address_candidate(value)
    if not text or geo.CONTACT.search(text) or geo.ADDRESS_PLACEHOLDER.fullmatch(text.strip()):return None
    return text

def clean_sales_address(value):
    # This value comes from the dedicated Sales address field, not a whole
    # Calendar description. An explicit field supports named premises and
    # unit-led addresses while retaining contact/secret-tail sanitisation.
    text=str(value or '').strip()
    return clean_address(text if geo.ADDRESS_LABEL.match(text) else 'Alamat: '+text)

def address_key(value,explicit_address_field=False):
    text=clean_sales_address(value) if explicit_address_field else clean_address(value)
    return hashlib.sha256(geo.normalized_candidate_key(text).encode()).hexdigest() if text else None

def sales_cache_record(cache,value):
    # Keep earlier valid mappings while introducing explicit-field parsing.
    # A verified manual result always outranks an automatic replacement.
    keys=list(dict.fromkeys([address_key(value,explicit_address_field=True),address_key(value)]))
    values=[cache[k] for k in keys if k in cache]
    protected=[r for r in values if r.get('manual_override_protected') or r.get('precision_tier')=='manual_verified']
    if protected:return protected[0]
    usable=[r for r in values if r.get('status')=='accepted' and r.get('precision_tier') in MAP_TIERS and valid_point(r)]
    return usable[0] if usable else (values[0] if values else None)

def service_candidate(event):
    title=str(event.get('summary') or '').upper()
    if str(event.get('status')).lower()!='confirmed' or re.match(r'^\s*CANCEL(?:L)?ED\b',title):return False
    if is_confirmed_placeholder(event):return False
    if re.search(r'\b(?:CHECK|REVIEW|CALCULATE)\b.*\bCONVERSION\s+RATE\b',title):return False
    warranty=re.search(r'\b(?:WARRANTY|CLAIMS?|CALLBACK)\b',re.sub(r'\b(?:NO|WITHOUT)\s+WARRANTY\b','',title))
    if warranty:return True
    if re.search(r'\b(?:CONSULTATION|INSPECTION)\b',title):return False
    return bool(re.search(r'\b\d{1,2}\s*/\s*\d{1,2}\b|\b(?:EXTRA|COMPLIMENTARY|FOLLOW[- ]?UP)\b',title))

def calendar_address(event):
    """Extract only a contiguous address block, never the whole description."""
    description=event.get('description') or ''
    lines=geo.clean_lines(description)
    for line in lines:
        label=geo.ADDRESS_LABEL.search(line)
        if label:
            first=line[label.end():].strip()
            block,_=geo.address_block(description,first)
            if block and clean_address('Alamat: '+block):return 'Alamat: '+block
    for line in lines:
        if geo.eligible_address(line):
            block,_=geo.address_block(description,line)
            if block and clean_address(block):return block
    return event.get('location')

def candidates(calendar_records,sales_records):
    found={};counts=Counter()
    def add(value,event_row=None,priority='',explicit_address_field=False):
        address=clean_sales_address(value) if explicit_address_field else clean_address(value)
        if not address:return False
        key=hashlib.sha256(geo.normalized_candidate_key(address).encode()).hexdigest();item=found.setdefault(key,{'address':address,'event_rows':[],'priority':''})
        if event_row is not None:item['event_rows'].append(int(event_row))
        item['priority']=max(item['priority'],priority)
        return True
    for event in calendar_records:
        if not service_candidate(event):continue
        counts['service_candidates']+=1
        if not add(calendar_address(event),event['calendar_event_row'],str(event.get('start_raw') or '')[:10]):counts['calendar_no_usable_address']+=1
    for sale in sales_records:
        if not re.search(r'\bCUST\d+\b',str(sale.get('source_column_007') or ''),re.I):continue
        counts['sales_address_rows']+=1
        # Priority only, not a reinterpretation of the authoritative sale date.
        # Prefer recent explicit years over older backlog; ambiguous dates keep
        # the lowest priority instead of being invented as current-year sales.
        years=re.findall(r'\b(20\d{2})\b',str(sale.get('source_column_004') or '')+' '+str(sale.get('source_column_003') or ''))
        priority=max(years)+'-01-01' if years else ''
        if not add(sale.get('source_column_011'),priority=priority,explicit_address_field=True):counts['sales_no_usable_address']+=1
    counts['distinct_address_candidates']=len(found)
    return found,dict(counts)

def query(client,sql):
    dry=client.query(sql,job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False),location=LOCATION)
    if (dry.total_bytes_processed or 0)>LIMIT:raise ValueError('Geocoding query exceeds 100 MiB')
    return [dict(r) for r in client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=LIMIT),location=LOCATION).result(timeout=120)]

def valid_point(row):
    lat,lon=row.get('latitude'),row.get('longitude')
    return all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in [lat,lon]) and .5<=lat<=7.6 and 99<=lon<=120

def baseline_cache(client):
    rows=query(client,f'SELECT * EXCEPT(calendar_event_row) FROM `{BASELINE}`')
    grouped={}
    for row in rows:
        if valid_point(row):grouped.setdefault(row['address_hash'],[]).append(row)
    result={}
    for key,values in grouped.items():
        manual=[r for r in values if r.get('manual_override_protected') or r.get('precision_tier')=='manual_verified']
        preferred=manual or values
        if len({(r['latitude'],r['longitude']) for r in preferred})!=1:continue
        row=preferred[0];row['status']='accepted';result[key]=row
    return result

def load_cache(client):
    saved=baseline_cache(client)
    try:rows=query(client,f'SELECT address_hash,record_json FROM `{CACHE}` QUALIFY ROW_NUMBER() OVER(PARTITION BY address_hash ORDER BY attempted_at DESC)=1')
    except NotFound:return saved
    for row in rows:
        value=json.loads(row['record_json']);old=saved.get(row['address_hash'])
        if old and (old.get('manual_override_protected') or value.get('status')!='accepted'):continue
        saved[row['address_hash']]=value
    return saved

def due(row,now):
    if not row:return True
    if row.get('status')!='error':return False
    return datetime.fromisoformat(row['retry_after'].replace('Z','+00:00'))<=now

def resolved_record(key,address,result,now):
    tier=geo.analysis_tier({'input_address':address,**result})
    row={'address_hash':key,'latitude':result.get('latitude'),'longitude':result.get('longitude'),'geocode_provider':'geoapify','coordinate_source':'geoapify','manual_override_protected':False,'precision_tier':tier,'provider_result_type':result.get('result_type'),'provider_confidence':result.get('confidence'),'postcode_agrees':result.get('postcode_agrees'),'geocoded_at_utc':now.isoformat()}
    row['status']='accepted' if tier in USABLE and valid_point(row) else ('no_result' if not result.get('result_count') else 'manual_review')
    return row

def perform(found,cache,key,max_requests=100,max_seconds=240,transport=None,sleep=time.sleep):
    now=datetime.now(timezone.utc);started=time.monotonic();pending=[(k,v) for k,v in found.items() if due(cache.get(k),now)]
    pending.sort(key=lambda item:(item[1]['priority'],len(item[1]['event_rows'])),reverse=True)
    summary=Counter({'pending_before':len(pending),'attempted':0,'accepted':0,'manual_review':0,'no_result':0,'errors':0});updates=[];failures=0
    for hashed,item in pending[:max_requests]:
        if time.monotonic()-started>=max_seconds:break
        attempted=datetime.now(timezone.utc)
        try:
            result=(transport or geo.geocode)(item['address'],key)
            row=resolved_record(hashed,item['address'],result,attempted);failures=0;summary[row['status']]+=1
        except geo.GeoapifyRequestError as error:
            tries=int(cache.get(hashed,{}).get('attempts',0))+1
            # Error classes contain no provider URL, address or API key.
            code=str(error);safe_code=code if re.fullmatch(r'HTTP \d{3}|network_or_response_error|unexpected_response',code) else 'provider_error'
            row={'address_hash':hashed,'status':'error','error_code':safe_code,'attempts':tries,'retry_after':(attempted+timedelta(days=min(7,2**min(tries-1,3)))).isoformat()}
            failures+=1;summary['errors']+=1
        row['attempted_at']=attempted.isoformat();cache[hashed]=row;updates.append(row);summary['attempted']+=1
        sleep(.3)
        if failures>=3 or row.get('error_code') in ('HTTP 401','HTTP 403','HTTP 429'):break
    summary['pending_after']=len(pending)-summary['attempted'];summary['reused_cached_addresses']=len(found)-len(pending)
    return updates,dict(summary)

def save_cache(client,updates):
    if not updates:return
    schema=[bigquery.SchemaField('address_hash','STRING',mode='REQUIRED'),bigquery.SchemaField('attempted_at','TIMESTAMP',mode='REQUIRED'),bigquery.SchemaField('status','STRING',mode='REQUIRED'),bigquery.SchemaField('record_json','STRING',mode='REQUIRED')]
    client.create_table(bigquery.Table(CACHE,schema=schema),exists_ok=True)
    rows=[{'address_hash':r['address_hash'],'attempted_at':r['attempted_at'],'status':r['status'],'record_json':json.dumps(r,sort_keys=True,allow_nan=False)} for r in updates]
    client.load_table_from_json(rows,CACHE,job_config=bigquery.LoadJobConfig(schema=schema,write_disposition='WRITE_APPEND'),location=LOCATION).result(timeout=120)

def refresh(client,calendar,sales,baseline):
    key=os.environ.get('NOMOBUG_GEOAPIFY_API_KEY')
    if not key:raise ValueError('Daily geocoding secret is not configured')
    found,counts=candidates(calendar['records'],sales['records']);cache=load_cache(client)
    maximum=int(os.environ.get('CP2_GEOCODING_MAX_REQUESTS','100'))
    if not 1<=maximum<=500:raise ValueError('Daily geocoding request bound must be 1–500')
    updates,summary=perform(found,cache,key,max_requests=maximum)
    save_cache(client,updates)
    rows=query(client,f"SELECT * FROM `{PROJECT}.quality.{baseline['table_name']}`")
    by_event={int(r['calendar_event_row']):r for r in rows}
    for hashed,item in found.items():
        record=cache.get(hashed,{})
        if record.get('status')!='accepted' or not valid_point(record):continue
        for event_row in item['event_rows']:
            if event_row in by_event:continue
            by_event[event_row]={name:record.get(name) for name in SIDE_FIELDS if name!='calendar_event_row'}|{'calendar_event_row':event_row}
    rows=sorted(by_event.values(),key=lambda r:r['calendar_event_row'])
    serial=json.dumps(rows,sort_keys=True,default=str,separators=(',',':'))
    name='calendar_geocodes_daily_'+calendar['table_name'].rsplit('_',1)[1][:16]+'_'+hashlib.sha256(serial.encode()).hexdigest()[:16]
    table_id=PROJECT+'.quality.'+name
    schema=client.get_table(PROJECT+'.quality.'+baseline['table_name']).schema
    metadata={'source_calendar_table':calendar['table_name'],'baseline_table':baseline['table_name'],'cache_table':CACHE,'rows':len(rows)}
    try:
        existing=client.get_table(table_id)
        if existing.num_rows!=len(rows) or json.loads(existing.description or '{}')!=metadata:raise ValueError('Daily geocode snapshot lineage mismatch')
    except NotFound:
        # BQ timestamp JSON values must be plain strings, never raw datetime.
        rows=json.loads(json.dumps(rows,default=str))
        client.load_table_from_json(rows,table_id,job_config=bigquery.LoadJobConfig(schema=schema,write_disposition='WRITE_EMPTY'),location=LOCATION).result(timeout=120)
        table=client.get_table(table_id);table.description=json.dumps(metadata,sort_keys=True);client.update_table(table,['description'])
    receipt={**counts,**summary,'status':'DEGRADED' if summary['errors'] else 'COMPLETED_WITH_BACKLOG' if summary['pending_after'] else 'COMPLETED','calendar_coordinates_before':baseline['rows'],'calendar_coordinates_after':len(rows),'cache_table':CACHE,'provider':'Geoapify / OpenStreetMap','retry_rule':'Transient errors retry after 1, 2, 4, then at most 7 days; ambiguous/no-result addresses require review or changed input'}
    return {'table_name':name,'rows':len(rows),'reuse_rule':'validated_same_sanitised_address_hash_and_protected_baseline_event_matches','daily_geocoding':receipt}
