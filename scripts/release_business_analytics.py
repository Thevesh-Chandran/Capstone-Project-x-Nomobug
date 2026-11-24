"""Build actual business analytics from one published immutable reporting release.

Writes private records only to ignored outputs. No model training or experiment writes.
"""
import argparse
import csv
import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from google.cloud import bigquery
from webapp import business
from webapp.geography import district_for
from webapp.data import PROJECT, MAX_BYTES, json_default


def business_output_version(root, reviewed, segments):
    """Bind immutable sidecars to their data as well as their generating code.

    A later validated geocode can change district aggregates without changing
    the underlying Sales/Calendar release. Never overwrite the old sidecars.
    """
    code=b''.join((root/p).read_bytes() for p in ('scripts/release_business_analytics.py','webapp/business.py','webapp/geography.py'))
    rows={name:sorted(json.dumps(r,sort_keys=True,default=json_default) for r in values)
          for name,values in [('sales',reviewed['sales']),('services',reviewed['services']),('customers',segments)]}
    return hashlib.sha256(code+json.dumps(rows,sort_keys=True).encode()).hexdigest()[:12]



# Public district lists and DBKL's 2040 locality map support these names.
# Shared postal names (Shah Alam, Ampang, Cheras, Puchong) are excluded.
DISTRICT_LOCALITIES = {
    'Selangor / Petaling': r'petaling jaya|kota damansara|subang jaya',
    'Selangor / Sepang': r'cyberjaya|dengkil|bandar baru salak tinggi|sungai merab luar',
    'Selangor / Gombak': r'batu caves|selayang baru|bandar baru selayang',
    'Selangor / Ulu Langat': r'bandar baru bangi|semenyih',
    'W.P. Kuala Lumpur / W.P. Kuala Lumpur': r'sentul pasar|mont kiara|bukit ceylon|bangsar south|(?:5[0-9]|60)[0-9]{3}[ ,]+kuala lumpur|w\.?p\.?k\.?l\.?',
}


# Named localities documented by the Putrajaya licensing directory, Selangor
# State Assembly, Klang City Council and DBKL. Postal city names are not used.
PUBLIC_DISTRICT_LOCALITIES = {
    'W.P. Putrajaya / W.P. Putrajaya': r'ppam seruling',
    'Selangor / Ulu Langat': r'bandar seri putra|bandar mahkota cheras|permai puteri.*ampang',
    'Selangor / Klang': r'(?:kampung|kg\.?) dele[kq] kanan',
    'Selangor / Petaling': (
        r'sri alam.*(?:kelab golf|sek(?:syen)?[ .]*13).*shah alam'
        r'|vista prima.*(?:bukit puchong|47100.*puchong)'
        r'|(?:taman|tmn) lestari putra'
    ),
    'W.P. Kuala Lumpur / W.P. Kuala Lumpur': (
        r'damai impian.*alam damai|alam damai.*56000|the hipster.*taman desa'
        r'|legasi (?:kg\.?|kampung|kampong) ba[hr]*ru|pandan\s*mas\s*2'
        r'|mercu jalil|(?:ppam.*)?metropolitan kepong'
        # DBKL 2040 development plan and branch directory identify these areas.
        r'|wangsa maju|bandar menjalara|bandar sri permaisuri|desa sri hartamas'
        r'|taman tun dr\.? ismail|bandar tasik selatan|danau kota|pantai dalam'
        r'|taman salak selatan|desa petaling|sri petaling|bukit jalil'
    ),
    'Negeri Sembilan / Seremban': r'residensi klia.*(?:71800|nilai)',
}


def public_locality_district(address):
    matches = {
        district for district, names in PUBLIC_DISTRICT_LOCALITIES.items()
        if re.search(rf'(?<![a-z])(?:{names})(?![a-z])', address, re.IGNORECASE)
    }
    return next(iter(matches)) if len(matches) == 1 else None


def corroborated_district(address, point_district):
    matches = {
        name for name, places in DISTRICT_LOCALITIES.items()
        if re.search(rf'(?<![a-z])(?:{places})(?![a-z])', address, re.IGNORECASE)
    }
    return point_district if point_district and matches == {point_district} else None


def run(folder, publish=False, approved_districts=None):
    root = Path(__file__).resolve().parents[1]
    folder = Path(folder).resolve()
    if not folder.is_relative_to(root/'outputs'): raise ValueError('Private exports require ignored outputs')
    folder.mkdir(parents=True, exist_ok=True)
    client = bigquery.Client(project=PROJECT, location='asia-southeast1')
    receipts = []
    def query(sql):
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
        if (dry.total_bytes_processed or 0) > MAX_BYTES: raise ValueError('Query exceeds 100 MiB')
        job = client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES))
        rows = [dict(r.items()) for r in job.result(timeout=120)]
        receipts.append({'job_id': job.job_id, 'bytes_processed': job.total_bytes_processed})
        return rows
    try:
        definition = client.get_table(PROJECT+'.gold.sales_monthly_recorded').view_query
        match = re.search(r'\.(cp2r_[a-zA-Z0-9_]+)_gold\.', definition)
        if not match: raise ValueError('Cannot resolve published release')
        prefix = match.group(1)
        silver = client.get_table(PROJECT+'.silver.sales').view_query
        if f'.{prefix}_silver.' not in silver: raise ValueError('Published source releases differ')
        sales = query(f'''SELECT f.sales_row_id,f.sales_record_id,f.include_in_sale_count,f.sale_total_rm,
          f.closed_date,f.pest_type_raw,f.package_type_raw,f.premise_type,s.customer_name_raw,s.phone_raw,s.address_raw
          FROM `{PROJECT}.{prefix}_gold.sales_package_facts` f
          JOIN `{PROJECT}.{prefix}_silver.sales` s USING(sales_row_id)''')
        events = query(f'''SELECT calendar_name,event_id,event_date_local,latitude,longitude,address_hash,sales_record_id,
          location_uncertainty_radius_m,location_precision_tier,calendar_pest_text_category,warranty_claim_candidate
          FROM `{PROJECT}.{prefix}_gold.calendar_programme_service_facts`''')
        contracts = query(f'''SELECT sales_record_id,sale_total_rm,sales_total_recorded_paid_rm,
          sales_remaining_balance_rm,next_scheduled_reminder_date,schedule_confirmation_status,next_action
          FROM `{PROJECT}.{prefix}_silver.recurring_contract_payment_tracker`''')
        with (root/'dbt/seeds/service_programme_memberships.csv').open(encoding='utf-8-sig') as h:
            memberships = {r['sales_record_id']: r['programme_id'] for r in csv.DictReader(h)}
        features = json.loads((root/'data/processed/boundaries/dosm_districts.geojson').read_text())['features']
        cache = {}
        geocodes = {}; conflicted=set()
        for e in events:
            if e.get('location_precision_tier') not in ('precise_candidate','street_candidate','manual_verified','area_reference_verified','postcode_area_candidate'):continue
            if e.get('address_hash') and e.get('latitude') is not None and e.get('location_uncertainty_radius_m') is not None:
                old=geocodes.get(e['address_hash'])
                if old and (old['latitude'],old['longitude'])!=(e['latitude'],e['longitude']):conflicted.add(e['address_hash'])
                geocodes[e['address_hash']] = e
        for key in conflicted:geocodes.pop(key,None)
        from scripts.cp2_geocoding import load_cache,address_key,MAP_TIERS,sales_cache_record,calendar_address
        address_cache=load_cache(client)
        def district(row):
            original=row
            if row.get('address_raw'):
                key = hashlib.sha256(business.normalized(row['address_raw']).encode()).hexdigest()
                g = geocodes.get(key)
                if not g:
                    # A Sales address does not need a matching Calendar visit.
                    # It remains a sales location; never propagate it to a visit.
                    candidate=sales_cache_record(address_cache,row['address_raw'])
                    if candidate and candidate.get('status')=='accepted' and candidate.get('precision_tier') in MAP_TIERS:
                        uncertainty={'precise_candidate':250,'street_candidate':1000,'postcode_area_candidate':5000,'manual_verified':250,'area_reference_verified':5000}
                        g={**candidate,'location_precision_tier':candidate['precision_tier'],'location_uncertainty_radius_m':uncertainty[candidate['precision_tier']]}
                if not g: return None
                row = g
            if row.get('location_precision_tier') not in ('precise_candidate','street_candidate','manual_verified','area_reference_verified','postcode_area_candidate'):return None
            lat, lon = row.get('latitude'), row.get('longitude')
            if lat is None or lon is None or row.get('location_uncertainty_radius_m') is None: return None
            key = (float(lat),float(lon),float(row['location_uncertainty_radius_m']))
            original['_location']={'latitude':key[0],'longitude':key[1],'uncertainty_km':key[2]/1000}
            if key not in cache: cache[key] = district_for(features,key[0],key[1],key[2]/1000)
            return cache[key]
        approved = {}
        matched = set()
        changed = set()
        evidence = {'sales_locality': 0, 'calendar_exact_address': 0, 'calendar_locality': 0, 'sales_exact_peer': 0, 'calendar_exact_peer': 0, 'sales_public_locality': 0, 'calendar_public_locality': 0}
        calendar_addresses = {}
        if approved_districts:
            run_id = prefix.removeprefix('cp2r_')
            calendar_table = query(f'''SELECT JSON_VALUE(manifest_json, '$.snapshot_tables.calendar') AS name
              FROM `{PROJECT}.audit.release_runs`
              WHERE run_id = '{run_id}' AND status = 'BRONZE_VERIFIED'
              ORDER BY event_at DESC LIMIT 1''')
            if not calendar_table or not re.fullmatch(r'calendar_events_[0-9a-f]{64}', calendar_table[0]['name'] or ''):
                raise ValueError('Published Calendar Bronze source could not be verified')
            event_keys = {(event['calendar_name'], event['event_id']) for event in events}
            for event in query(f'''SELECT calendar_name,event_id,description,location
              FROM `{PROJECT}.bronze.{calendar_table[0]['name']}`'''):
                key = (event['calendar_name'], event['event_id'])
                if key in event_keys:
                    raw = calendar_address(event)
                    if raw:
                        calendar_addresses[key] = raw
        if approved_districts:
            labels = {}
            for feature in features:
                state = feature['properties']['state']
                name = feature['properties']['district']
                labels.setdefault(name.casefold(), set()).add(f'{state} / {name}')
            with Path(approved_districts).open(encoding='utf-8-sig', newline='') as handle:
                for entry in csv.DictReader(handle):
                    sale_id = entry['Sale ID']
                    address = entry['Address SHA256']
                    label = entry['Approved district'].strip().casefold()
                    if label.startswith('hulu '):
                        label = 'ulu ' + label[5:]
                    canonical = labels.get(label, set())
                    if not sale_id or not re.fullmatch(r"[0-9a-f]{64}", address) or len(canonical) != 1 or sale_id in approved:
                        raise ValueError('Invalid, ambiguous or duplicate approved district row')
                    approved[sale_id] = (address, next(iter(canonical)))

        approved_by_address = {}
        for sale in sales:
            entry = approved.get(sale['sales_record_id'])
            raw = sale.get('address_raw') or ''
            if entry and hashlib.sha256(business.normalized(raw).encode()).hexdigest() == entry[0]:
                key = address_key(raw, explicit_address_field=True)
                if key:
                    approved_by_address.setdefault(key, set()).add(entry[1])

        def recorded_address(row):
            if 'sales_row_id' in row:
                return row.get('address_raw') or ''
            return calendar_addresses.get((row['calendar_name'], row['event_id']), '')

        def peer_key(row):
            raw = recorded_address(row)
            # Locality-only strings are too broad to establish a same-address match.
            if not (re.search(r'\d', raw) and re.search(r'\b(?:jalan|jln|lorong|persiaran|lebuh)\b', raw, re.I)):
                return None
            return address_key(raw, explicit_address_field='sales_row_id' in row)

        trusted_peers = {}
        for row in [*sales, *events]:
            key = peer_key(row)
            if not key:
                continue
            mapped = district(row)
            if mapped:
                trusted_peers.setdefault(key, set()).add(mapped)
            trusted_peers.setdefault(key, set()).update(approved_by_address.get(key, ()))

        def sales_district(row):
            mapped = district(row)
            is_sale = 'sales_row_id' in row
            if is_sale:
                sale_id = row['sales_record_id']
                raw = row.get('address_raw') or ''
                entry = approved.get(sale_id)
                if entry and hashlib.sha256(business.normalized(raw).encode()).hexdigest() == entry[0]:
                    matched.add(sale_id)
                    if mapped != entry[1]:
                        changed.add(sale_id)
                    return entry[1]
            else:
                raw = calendar_addresses.get((row['calendar_name'], row['event_id']), '')
                keys = {key for key in (address_key(raw), row.get('address_hash')) if key}
                direct = set().union(*(approved_by_address.get(key, set()) for key in keys))
                if not mapped and len(direct) == 1:
                    evidence['calendar_exact_address'] += 1
                    return next(iter(direct))
            if not mapped:
                peer = trusted_peers.get(peer_key(row), set())
                if len(peer) == 1:
                    evidence['sales_exact_peer' if is_sale else 'calendar_exact_peer'] += 1
                    return next(iter(peer))
            if not mapped:
                public = public_locality_district(raw)
                if public:
                    evidence['sales_public_locality' if is_sale else 'calendar_public_locality'] += 1
                    return public
            point = row.get('_location')
            if not mapped and point:
                centre_key = (point['latitude'], point['longitude'], 0)
                if centre_key not in cache:
                    cache[centre_key] = district_for(features, centre_key[0], centre_key[1], 0)
                supported = corroborated_district(raw, cache[centre_key])
                if supported:
                    evidence['sales_locality' if is_sale else 'calendar_locality'] += 1
                    return supported
            return mapped

        snapshot, customers = business.build(sales, events, memberships, sales_district)
        if publish and approved_districts and not matched:
            raise ValueError('No approved Sales addresses match the current release')
        by_sale={}
        for c in customers:
            c['contracts']=[];c['appointment_count']=0
            for s in c['sales']:by_sale[s['sale_id']]=c
        for contract in contracts:
            if contract['sales_record_id'] in by_sale:by_sale[contract['sales_record_id']]['contracts'].append(contract)
        for e in events:
            if e.get('sales_record_id') in by_sale:by_sale[e['sales_record_id']]['appointment_count']+=1
        expected = query(f'SELECT SUM(recorded_package_face_value_rm) AS sales_rm, SUM(countable_package_rows) AS sale_rows FROM `{PROJECT}.gold.sales_monthly_recorded` WHERE EXTRACT(YEAR FROM closed_month)=2026')[0]
        actual = [r for r in snapshot['sales'] if r['date'] and r['date'].startswith('2026-')]
        from decimal import Decimal
        if abs(sum(Decimal(str(r['sales_rm'] or 0)) for r in actual)-Decimal(str(expected['sales_rm']))) > Decimal('.01') or len(actual)!=expected['sale_rows']:
            raise ValueError('Business sale totals do not reconcile to published Gold')
        receipt = {'published_release': prefix, 'built_at_utc': datetime.now(timezone.utc).isoformat(),
                   'queries': receipts, 'coverage': snapshot['coverage'],
                   'sales_location_status': 'Reviewed district labels and validated coordinates use separate evidence',
                   'approved_district_rows': len(approved),
                   'matched_district_rows': len(matched),
                   'changed_district_rows': len(changed), 'additional_district_evidence': evidence}
        segments={}
        for c in customers:
            segment='Identity needs review' if c['identity_status']=='needs_review' else 'Repeat customer' if c['repeat_customer'] else 'One programme'
            item=segments.setdefault(segment,{'segment':segment,'customer_groups':0,'programmes':0,'sales_rm':0.0})
            item['customer_groups']+=1;item['programmes']+=c['purchase_count'];item['sales_rm']+=c['sales_rm']
        for name, value in [('business_records_private.json',snapshot),('customers_private.json',customers),
                            ('business_tools_private.json',{'records':snapshot,'customers':customers,'receipt':receipt}),
                            ('business_analytics.json',business.aggregate(snapshot)),('business_receipt.json',receipt)]:
            temp = folder/(name+'.next'); temp.write_text(json.dumps(value,default=json_default,allow_nan=False),encoding='utf-8'); temp.replace(folder/name)
        if publish:
            reviewed=business.aggregate(snapshot)
            version=business_output_version(root,reviewed,list(segments.values()))
            backups={}; pending=[]
            for name, rows in [('dashboard_business_sales',reviewed['sales']),('dashboard_business_services',reviewed['services']),('dashboard_business_customers',list(segments.values()))]:
                table_id=f'{PROJECT}.{prefix}_gold.{name}_{version}'
                from google.api_core.exceptions import NotFound
                try:
                    existing=client.get_table(table_id)
                    saved=query(f'SELECT * FROM `{table_id}`')
                    canonical=lambda values: sorted(json.dumps(r,sort_keys=True,default=json_default) for r in values)
                    if canonical(saved)!=canonical(rows): raise ValueError('Immutable business release differs')
                except NotFound:
                    client.load_table_from_json(rows,table_id,job_config=bigquery.LoadJobConfig(autodetect=True,write_disposition='WRITE_EMPTY')).result(timeout=120)
                view_id=f'{PROJECT}.gold.{name}'
                try: old=client.get_table(view_id);backups[view_id]=old.view_query
                except NotFound: old=None;backups[view_id]=None
                pending.append((view_id,table_id,old))
            safe=folder/'view_backups.json';safe.write_text(json.dumps(backups),encoding='utf-8')
            changed=[]
            try:
                for view_id,table_id,old in pending:
                    extras=f", '{prefix}' AS source_release"
                    if not view_id.endswith('customers'):extras+=", SAFE.PARSE_DATE('%Y-%m',month) AS month_start"
                    view=old or bigquery.Table(view_id);view.view_query=f'SELECT *{extras} FROM `{table_id}`'
                    if old:client.update_table(view,['view_query'])
                    else:client.create_table(view)
                    changed.append(view_id)
            except Exception:
                for view_id in reversed(changed):
                    if backups[view_id] is None:client.delete_table(view_id)
                    else:
                        view=client.get_table(view_id);view.view_query=backups[view_id];client.update_table(view,['view_query'])
                raise
        print(json.dumps(receipt))
        return receipt
    finally: client.close()


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='outputs/business_implementation/current');p.add_argument('--publish',action='store_true')
    p.add_argument('--approved-districts', type=Path)
    args=p.parse_args();run(args.output,args.publish,args.approved_districts)
