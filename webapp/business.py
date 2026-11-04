"""Business reporting at sale, programme and appointment grains.

Private identity fields never belong in the aggregate reporting snapshot.
"""
from collections import defaultdict
from decimal import Decimal
import hashlib
import re
import unicodedata



def pest_group(raw):
    """Standard pest category for a free-text Sales entry ('Lipas dan semut' -> 'Cockroach + Ant')."""
    if not str(raw or '').strip():
        return 'Unspecified'
    from webapp.analytics import pest_labels
    return ' + '.join(pest_labels(raw))

def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', str(value or '')).casefold() if c.isalnum())


def validate_period(start, end):
    from datetime import date
    for index,value in enumerate((start, end)):
        if index==0 and value=='':continue
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            raise ValueError('Use valid From and To dates')
        date.fromisoformat(value)
    if start and start>end:raise ValueError('From date must not be after To date')
    return start,end


def commercial_identity(row, name):
    address=normalized(row.get('address_raw'))
    plausible=bool(re.search(r'\b(?:jalan|jln|taman|lorong|persiaran|road|street|lot|block|blok)\b|\b\d{5}\b',str(row.get('address_raw') or ''),re.I))
    if row.get('premise_type')=='COMMERCIAL' and len(name)>=6 and len(address)>=20 and plausible:
        return 'commercial|' + name + '|' + address
    return None


def customer_key(row):
    raw_name = str(row.get('customer_name_raw') or '')
    # Remove only explicit billing annotations; branch/unit labels remain identity-bearing.
    raw_name = re.sub(r'\(\s*(?:payment|paid|rm\s*\d|\d+\s*%)[^)]*\)', '', raw_name, flags=re.I)
    name = normalized(raw_name)
    commercial=commercial_identity(row,name)
    if commercial:return hashlib.sha256(commercial.encode()).hexdigest(),True
    phone = re.sub(r'[^0-9]', '', str(row.get('phone_raw') or ''))
    # Only one unambiguous Malaysian number; shared contacts alone never merge companies.
    raw = str(row.get('phone_raw') or '')
    if any(c in raw for c in '/,;'):
        phone = ''
    if phone.startswith('0060'): phone = phone[2:]
    if phone.startswith('0'): phone = '60' + phone[1:]
    reliable = bool(name and phone.startswith('60') and 10 <= len(phone) <= 12)
    identity = name + '|' + phone if reliable else 'sale|' + str(row['sales_row_id'])
    return hashlib.sha256(identity.encode()).hexdigest(), reliable


def build(sales, events, memberships, district_lookup):
    """Reconcile every included sale once; retain unknown dates/locations explicitly."""
    groups = {}; rows = []; seen = set()
    linked = defaultdict(set)
    for sale in sales:
        if sale['sales_record_id'] in memberships:
            key, reliable = customer_key(sale)
            if reliable: linked[memberships[sale['sales_record_id']]].add(key)
    for sale in sales:
        sid = sale['sales_row_id']
        if sid in seen: raise ValueError('Duplicate sale grain')
        seen.add(sid)
        if not sale['include_in_sale_count']: continue
        key, reliable = customer_key(sale)
        programme = memberships.get(sale['sales_record_id'], 'SALE_' + str(sid))
        # Explicit owner-approved programme links take precedence over incomplete contacts.
        if sale['sales_record_id'] in memberships:
            candidates = linked[programme]
            if len(candidates) == 1:
                key = next(iter(candidates)); reliable = True
            else:
                key = 'programme:' + programme
                reliable = False
        amount = sale.get('sale_total_rm')
        amount = Decimal(str(amount)) if amount is not None else None
        district = district_lookup(sale) or 'Unassigned'
        closed = str(sale.get('closed_date') or '')[:10] or None
        item = {'sale_key': str(sid), 'sale_id': sale['sales_record_id'], 'customer_key': key,
                'programme_id': programme, 'date': closed, 'district': district,
                'sales_rm': float(amount) if amount is not None else None,
                # Free-text pest names (144 spellings) grouped into standard categories, e.g. 'Cockroach + Ant'.
                'pest': pest_group(sale.get('pest_type_raw')),
                'package': sale.get('package_type_raw') or 'Unspecified',
                'premise': sale.get('premise_type') or 'Unspecified', 'location':sale.get('_location')}
        rows.append(item)
        evidence='exact_name_and_address' if commercial_identity(sale,normalized(sale.get('customer_name_raw'))) else 'exact_name_and_phone'
        c = groups.setdefault(key, {'customer_key': key, 'name': sale.get('customer_name_raw') or 'Unnamed customer',
             'identity_status': evidence if reliable else 'needs_review', 'sales_rm': Decimal(0),
             'unknown_sale_values': 0, 'programmes': set(), 'sales': []})
        c['programmes'].add(programme); c['sales'].append(item)
        if amount is None: c['unknown_sale_values'] += 1
        else: c['sales_rm'] += amount
    customers = []
    for c in groups.values():
        c['purchase_count'] = len(c.pop('programmes'))
        c['repeat_customer'] = c['purchase_count'] >= 2 and c['identity_status'].startswith('exact_')
        c['sales_rm'] = float(c['sales_rm']); customers.append(c)
    appointments = []; seen_events = set()
    for e in events:
        identity = (e['calendar_name'], e['event_id'])
        if identity in seen_events: raise ValueError('Duplicate appointment grain')
        seen_events.add(identity)
        appointments.append({'date': str(e['event_date_local'])[:10], 'district': district_lookup(e) or 'Unassigned', 'location':e.get('_location'),
            'pest': e.get('calendar_pest_text_category') or 'Unspecified',
            'warranty_signal': bool(e.get('warranty_claim_candidate'))})
    total = sum(Decimal(str(r['sales_rm'])) for r in rows if r['sales_rm'] is not None)
    return {'sales': rows, 'appointments': appointments,
        'coverage': {'sale_rows': len(rows), 'appointment_rows': len(appointments), 'sales_rm': float(total),
          'unassigned_sales': sum(r['district'] == 'Unassigned' for r in rows),
          'unassigned_appointments': sum(r['district'] == 'Unassigned' for r in appointments),
          'customer_groups': len(customers), 'identity_review_groups': sum(c['identity_status']=='needs_review' for c in customers)}}, customers


def aggregate(snapshot):
    """Remove individual identifiers before any dashboard or AI publication."""
    grouped = defaultdict(lambda: {'sales_rm': Decimal(0), 'sale_rows': 0, 'unknown_sale_values': 0})
    for row in snapshot['sales']:
        k = (row['date'][:7] if row['date'] else 'Unknown date', row['district'], row['pest'], row['package'], row['premise'])
        g = grouped[k]; g['sale_rows'] += 1
        if row['sales_rm'] is None: g['unknown_sale_values'] += 1
        else: g['sales_rm'] += Decimal(str(row['sales_rm']))
    visits = defaultdict(lambda: {'appointments':0,'warranty_signals':0})
    for row in snapshot['appointments']:
        key = (row['date'][:7],row['district'],row['pest'])
        visits[key]['appointments'] += 1
        visits[key]['warranty_signals'] += int(row['warranty_signal'])
    return {'coverage': snapshot['coverage'], 'sales': [dict(zip(('month','district','pest','package','premise'), k),
             **{**v, 'sales_rm': float(v['sales_rm'])}) for k,v in grouped.items()],
             'services':[dict(zip(('month','district','pest'),k),**v) for k,v in visits.items()]}


def radius(snapshot, latitude, longitude, km, start='', end='9999-12-31'):
    import math
    from webapp.geography import haversine
    validate_period(start,end)
    if not all(math.isfinite(v) for v in (latitude,longitude,km)) or not (-1<=latitude<=8 and 99<=longitude<=120 and 1<=km<=50):
        raise ValueError('Choose a Malaysian centre and radius from 1 to 50 km')
    result={'sales_rm':0.0,'sale_rows':0,'appointments':0,'ambiguous_sales':0,'ambiguous_appointments':0,
            'unlocated_sales':0,'unlocated_appointments':0,'unknown_sale_values':0}
    for kind in ('sales','appointments'):
        for row in snapshot[kind]:
            if not row['date'] or not start<=row['date']<=end:continue
            loc=row.get('location')
            if not loc:result['unlocated_'+kind]+=1;continue
            distance=haversine(latitude,longitude,loc['latitude'],loc['longitude'])
            if distance+loc['uncertainty_km']<=km:
                if kind=='sales':
                    result['sale_rows']+=1
                    if row['sales_rm'] is None:result['unknown_sale_values']+=1
                    else:result['sales_rm']+=row['sales_rm']
                else:result['appointments']+=1
            elif distance-loc['uncertainty_km']<=km:result['ambiguous_'+kind]+=1
    return result
