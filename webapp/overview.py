"""Management overview: package scorecard and area summary.

Plain counts and rates from the published sales and appointment records.
Nothing here is a trained model; every figure can be checked by hand in the
Sales sheet. Customer names and locations never leave this module.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta

MIN_SALES = 10   # a package needs at least this many sales to be shown
TREND_DAYS = 91  # recent quarter compared with the quarter before


def package_family(raw):
    """Group the free-text Sales package labels into a few families a manager recognises."""
    text = str(raw or '').upper().replace(' ', '')
    if not text or text == 'UNSPECIFIED':
        return 'Not recorded'
    if 'CONSULT' in text or 'INSPECTION' in text:
        return 'Consultation or inspection'
    if 'TBS' in text or 'TRBS' in text:
        return 'Termite baiting (TBS)'
    if text.startswith('B2B'):
        visits = re.match(r'B2B(\d+)X', text)
        n = int(visits.group(1)) if visits else 0
        if n >= 12:
            return 'Business contract, monthly (12+ visits)'
        if n >= 3:
            return 'Business contract, 3 to 6 visits'
        return 'Business, 1 to 2 visits'
    if text.startswith('PROMO') or text.startswith('GPC42') or 'RM799' in text:
        return 'Home promotion package'
    if text.startswith('GPC1X'):
        return 'Home, single visit'
    if re.match(r'GPC[3-6]X', text):
        return 'Home programme, 3 to 6 visits'
    return 'Other or add-on'


def _anchor(sales, as_of):
    dated = [s['date'] for s in sales if s.get('date')]
    return date.fromisoformat(max(dated)) if dated else as_of


def _returning(sales, customers):
    """Sale keys bought by a customer who already had an earlier programme with Nomobug."""
    reliable = {c['customer_key'] for c in customers if str(c.get('identity_status', '')).startswith('exact_')}
    first = {}
    for s in sales:
        if s.get('date') and s['customer_key'] in reliable:
            key = (s['customer_key'])
            if key not in first or s['date'] < first[key][0]:
                first[key] = (s['date'], s['programme_id'])
    return {s['sale_key'] for s in sales
            if s['customer_key'] in first and s.get('date')
            and s['programme_id'] != first[s['customer_key']][1] and s['date'] > first[s['customer_key']][0]}


def _main_pest(pest):
    from webapp.analytics import pest_labels
    labels = pest_labels(str(pest).replace(' + ', ' '))
    if labels == ['Cockroach']:
        return 'Cockroach only'
    return 'Cockroach with ant or rat' if 'Cockroach' in labels else 'Other pests'


def packages(value, as_of):
    sales = value['records']['sales']
    anchor = _anchor(sales, as_of)
    recent_start = (anchor - timedelta(days=TREND_DAYS)).isoformat()
    earlier_start = (anchor - timedelta(days=2 * TREND_DAYS)).isoformat()
    returning = _returning(sales, value['customers'])

    groups = defaultdict(lambda: {'sales': 0, 'sales_rm': 0.0, 'valued': 0, 'returning': 0, 'recent': 0, 'earlier': 0})
    jobs = defaultdict(lambda: defaultdict(int))
    first_recorded = None
    for s in sales:
        family = package_family(s.get('package'))
        if family == 'Not recorded':
            continue
        if s.get('date') and (first_recorded is None or s['date'] < first_recorded):
            first_recorded = s['date']
        g = groups[family]
        g['sales'] += 1
        g['returning'] += s['sale_key'] in returning
        if s.get('sales_rm') is not None:
            g['sales_rm'] += float(s['sales_rm'])
            g['valued'] += 1
        if s.get('date') and s['date'] > recent_start:
            g['recent'] += 1
        elif s.get('date') and s['date'] > earlier_start:
            g['earlier'] += 1
        jobs[(str(s.get('premise') or 'Unspecified').title(), _main_pest(s.get('pest') or ''))][family] += 1

    recorded = sum(g['sales'] for g in groups.values())
    total_rm = sum(g['sales_rm'] for g in groups.values())
    rows = []
    for family, g in groups.items():
        if g['sales'] < MIN_SALES:
            continue
        rows.append({'package': family, 'sales': g['sales'], 'sales_rm': g['sales_rm'],
                     'average_rm': g['sales_rm'] / g['valued'] if g['valued'] else None,
                     'revenue_share': g['sales_rm'] / total_rm if total_rm else None,
                     'returning_share': g['returning'] / g['sales'],
                     'last_quarter': g['recent'], 'quarter_before': g['earlier'],
                     'change': (g['recent'] - g['earlier']) / g['earlier'] if g['earlier'] >= 5 else None})
    rows.sort(key=lambda r: r['sales_rm'], reverse=True)

    by_job = []
    for (premise, pest), counts in jobs.items():
        total = sum(counts.values())
        if total < MIN_SALES or premise not in ('Residential', 'Commercial'):
            continue
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        by_job.append({'premise': premise, 'pest': pest, 'sales': total,
                       'usual_package': ranked[0][0], 'usual_share': ranked[0][1] / total,
                       'second_package': ranked[1][0] if len(ranked) > 1 else None})
    by_job.sort(key=lambda r: r['sales'], reverse=True)

    return {'anchor_date': anchor.isoformat(), 'since': first_recorded, 'rows': rows, 'by_job': by_job,
            'recorded_sales': recorded, 'recorded_rm': total_rm,
            'returning_share': sum(g['returning'] for g in groups.values()) / recorded if recorded else None,
            'method': ('Sales with a package written in the Sales sheet, grouped into families. '
                       'Returning customers: the buyer already had an earlier programme with Nomobug. '
                       f'Trend: last {TREND_DAYS} days against the {TREND_DAYS} days before. '
                       f'Families with fewer than {MIN_SALES} sales are left out.')}


def areas(value, as_of):
    sales = value['records']['sales']
    appointments = value['records']['appointments']
    anchor = _anchor(sales, as_of)
    year_ago = (anchor - timedelta(days=365)).isoformat()
    two_years_ago = (anchor - timedelta(days=730)).isoformat()
    now_end = anchor.isoformat()

    area = defaultdict(lambda: {'sales_rm': 0.0, 'sales': 0, 'previous_rm': 0.0, 'visits': 0, 'warranty_visits': 0})
    located = 0
    recent_total = 0
    for s in sales:
        if not s.get('date') or not two_years_ago < s['date'] <= now_end:
            continue
        recent = s['date'] > year_ago
        recent_total += recent
        name = s.get('district') or 'Unassigned'
        if name == 'Unassigned':
            continue
        a = area[name.split(' / ')[-1]]
        if recent:
            located += 1
            a['sales_rm'] += float(s.get('sales_rm') or 0)
            a['sales'] += 1
        else:
            a['previous_rm'] += float(s.get('sales_rm') or 0)
    for v in appointments:
        name = v.get('district') or 'Unassigned'
        if name == 'Unassigned' or not v.get('date') or not year_ago < v['date'] <= now_end:
            continue
        a = area[name.split(' / ')[-1]]
        a['visits'] += 1
        a['warranty_visits'] += bool(v.get('warranty_signal'))

    rows = []
    for name, a in area.items():
        if not a['sales']:
            continue
        rows.append({'area': name, 'sales_rm': a['sales_rm'], 'sales': a['sales'], 'previous_rm': a['previous_rm'],
                     'change': (a['sales_rm'] - a['previous_rm']) / a['previous_rm'] if a['previous_rm'] >= 5000 and a['sales'] >= 15 else None,
                     'visits': a['visits'],
                     'warranty_share': a['warranty_visits'] / a['visits'] if a['visits'] >= 30 else None})
    rows.sort(key=lambda r: r['sales_rm'], reverse=True)
    changing = [r for r in rows if r['change'] is not None]
    return {'top': rows[:5], 'all': rows,
            'fastest_growing': max(changing, key=lambda r: r['change'], default=None),
            'slowest': min(changing, key=lambda r: r['change'], default=None),
            'located_share': located / recent_total if recent_total else None,
            'period': {'start': year_ago, 'end': now_end},
            'method': 'Sales in the last 12 months by district, compared with the 12 months before. '
                      'Return-visit share: calendar visits marked as a possible warranty or return visit. '
                      'Sales without a known address are left out.'}
