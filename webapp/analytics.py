"""Business-intelligence summary: descriptive, predictive and prescriptive views.

Everything here is a read-only aggregate of the already-published private
business snapshot, the saved planning evidence and the existing experimental
models. No customer contact details or locations leave this module; only
aggregate counts, ringgit totals and the existing ranked customer names that
the Customers page already shows to signed-in staff.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from datetime import date, timedelta

PESTS = (
    ('Cockroach', ('LIPAS', 'COCKROACH', 'GPC')),
    ('Ant', ('SEMUT', 'SEMUIT', 'ANT')),
    ('Rodent', ('TIKUS', 'TIKSU', 'RODENT', 'RAT')),
    ('Termite', ('ANAI', 'TERMITE')),
    ('Fly', ('LALAT', 'FLY')),
    ('Centipede / millipede', ('LIPAN', 'GONGGOK', 'KAMITETEP')),
    ('Bed bug', ('BED BUG', 'BEDBUG', 'PEPIJAT')),
    ('Mosquito', ('NYAMUK', 'MOSQUITO')),
)
WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


def pest_labels(raw):
    text = str(raw or '').upper()
    found = [name for name, keys in PESTS if any(re.search(r'\b' + re.escape(k), text) for k in keys)]
    return found or ['Other / unspecified']


def _month(value):
    return value[:7] if value else None


def _months_back(end, count):
    y, m = end.year, end.month
    out = []
    for _ in range(count):
        out.append(f'{y:04d}-{m:02d}')
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def _pct_change(now, before):
    if not before:
        return None
    return (now - before) / before


def descriptive(value, snapshot, as_of):
    sales = value['records']['sales']
    appts = value['records']['appointments']
    customers = value['customers']
    dated = [s for s in sales if s.get('date')]
    # The latest recorded closing date anchors comparisons, not the wall clock,
    # so a stale source does not look like a collapse in sales.
    anchor = max((date.fromisoformat(s['date']) for s in dated), default=as_of)
    ytd_start = date(anchor.year, 1, 1)
    prev_start, prev_end = date(anchor.year - 1, 1, 1), date(anchor.year - 1, anchor.month, min(anchor.day, 28))
    ytd = [s for s in dated if ytd_start.isoformat() <= s['date'] <= anchor.isoformat()]
    prev = [s for s in dated if prev_start.isoformat() <= s['date'] <= prev_end.isoformat()]
    rm = lambda rows: sum(float(r.get('sales_rm') or 0) for r in rows)
    known_values = [float(s['sales_rm']) for s in sales if s.get('sales_rm') not in (None, '')]

    l30 = [s for s in dated if (anchor - timedelta(days=29)).isoformat() <= s['date'] <= anchor.isoformat()]
    p30 = [s for s in dated if (anchor - timedelta(days=59)).isoformat() <= s['date'] < (anchor - timedelta(days=29)).isoformat()]

    repeat = sum(1 for c in customers if c.get('repeat_customer'))
    months = _months_back(anchor, 18)
    by_month = defaultdict(lambda: {'sales_rm': 0.0, 'sales': 0, 'appointments': 0, 'warranty': 0})
    for s in dated:
        b = by_month[_month(s['date'])]
        b['sales_rm'] += float(s.get('sales_rm') or 0)
        b['sales'] += 1
    for a in appts:
        if not a.get('date'):
            continue
        b = by_month[_month(a['date'])]
        b['appointments'] += 1
        b['warranty'] += 1 if a.get('warranty_signal') else 0
    trend = [{'month': m, **by_month[m]} for m in months]

    premise = Counter()
    for s in sales:
        premise[(s.get('premise') or 'UNKNOWN').title()] += float(s.get('sales_rm') or 0)
    pests = Counter()
    for s in dated:
        if s['date'] >= (anchor - timedelta(days=365)).isoformat():
            for p in pest_labels(s.get('pest')):
                pests[p] += 1
    districts = Counter()
    district_rows = Counter()
    for s in sales:
        d = s.get('district') or 'Unassigned'
        if d == 'Unassigned':
            continue
        name = d.split(' / ')[-1]
        districts[name] += float(s.get('sales_rm') or 0)
        district_rows[name] += 1
    located_rm = sum(districts.values())
    weekday = Counter()
    recent_appts = [a for a in appts if a.get('date') and a['date'] >= (anchor - timedelta(days=365)).isoformat()]
    for a in recent_appts:
        weekday[date.fromisoformat(a['date']).weekday()] += 1
    warranty_recent = sum(1 for a in recent_appts if a.get('warranty_signal'))

    packages = Counter()
    for s in sales:
        pkg = (s.get('package') or 'Unspecified').strip()
        if pkg != 'Unspecified':
            packages[re.sub(r'\s*\(.*\)$', '', pkg)] += 1

    growth = []
    cur_rows = Counter(); prev_rows = Counter()
    for r in ytd:
        if (r.get('district') or 'Unassigned') != 'Unassigned':
            cur_rows[r['district'].split(' / ')[-1]] += float(r.get('sales_rm') or 0)
    for r in prev:
        if (r.get('district') or 'Unassigned') != 'Unassigned':
            prev_rows[r['district'].split(' / ')[-1]] += float(r.get('sales_rm') or 0)
    for name in set(cur_rows) | set(prev_rows):
        if prev_rows[name] >= 5000:
            growth.append({'label': name, 'now': cur_rows[name], 'before': prev_rows[name], 'change': _pct_change(cur_rows[name], prev_rows[name])})
    growth.sort(key=lambda r: r['change'], reverse=True)

    contracts = [k for c in customers for k in c.get('contracts', [])]
    fnum = lambda v: float(v) if v not in (None, '') else 0.0
    contract_totals = {'contracts': len(contracts),
                       'value_rm': sum(fnum(k.get('sale_total_rm')) for k in contracts),
                       'paid_rm': sum(fnum(k.get('sales_total_recorded_paid_rm')) for k in contracts),
                       'remaining_rm': sum(max(0.0, fnum(k.get('sales_remaining_balance_rm'))) for k in contracts)}

    segments = snapshot.get('tables', {}).get('customer_segments', [])
    return {
        'anchor_date': anchor.isoformat(),
        'kpis': {
            'sales_rm_all': rm(sales),
            'sales_rows_all': len(sales),
            'ytd_sales_rm': rm(ytd), 'ytd_sales_rows': len(ytd),
            'prev_ytd_sales_rm': rm(prev), 'ytd_change': _pct_change(rm(ytd), rm(prev)),
            'last30_sales_rm': rm(l30), 'prev30_sales_rm': rm(p30), 'last30_change': _pct_change(rm(l30), rm(p30)),
            'last30_sales_rows': len(l30),
            'customers': len(customers), 'repeat_customers': repeat,
            'repeat_rate': repeat / len(customers) if customers else None,
            'avg_sale_rm': sum(known_values) / len(known_values) if known_values else None,
            'appointments_12m': len(recent_appts),
            'warranty_rate_12m': warranty_recent / len(recent_appts) if recent_appts else None,
        },
        'trend': trend,
        'premise_mix': [{'label': k, 'value': v} for k, v in premise.most_common()],
        'pest_mix': [{'label': k, 'value': v} for k, v in pests.most_common(7)],
        'top_districts': [{'label': k, 'value': v, 'rows': district_rows[k]} for k, v in districts.most_common(8)],
        'located_share': located_rm / rm(sales) if rm(sales) else None,
        'weekday': [{'label': WEEKDAYS[i], 'value': weekday[i]} for i in range(7)],
        'packages': [{'label': k, 'value': v} for k, v in packages.most_common(6)],
        'district_growth': growth,
        'contracts': contract_totals,
        'segments': [{'label': r.get('segment'), 'customers': r.get('customer_groups'), 'sales_rm': r.get('sales_rm')} for r in segments],
    }


def run_rate(trend):
    """Transparent 3-month moving-average projection; not a trained model."""
    complete = trend[:-1]  # the anchor month is usually incomplete
    if len(complete) < 6:
        return None
    last3 = [m['sales_rm'] for m in complete[-3:]]
    prior3 = [m['sales_rm'] for m in complete[-6:-3]]
    avg3 = sum(last3) / 3
    slope = (avg3 - sum(prior3) / 3) / 3
    last = date.fromisoformat(complete[-1]['month'] + '-01')
    out = []
    y, m = last.year, last.month
    for i in range(1, 4):
        m += 1
        if m == 13:
            y, m = y + 1, 1
        out.append({'month': f'{y:04d}-{m:02d}', 'sales_rm': max(0.0, avg3 + slope * i)})
    return {'method': '3-month moving average with recent slope', 'base_avg_rm': avg3,
            'monthly_slope_rm': slope, 'projection': out,
            'notice': 'Simple trend extrapolation for orientation only. It is not a validated forecast.'}


def predictive(planning, repeat, return_evidence, research_best, trend):
    models = []
    live = {f['id']: f for f in (planning.get('live', {}).get('forecasts') or [])}
    for m in planning.get('evidence', {}).get('models', []):
        f = live.get(m['id'], {})
        models.append({
            'id': m['id'], 'title': m['title'], 'unit': m['unit'], 'algorithm': m.get('algorithm'),
            'mae': m.get('mae'), 'baseline_mae': m.get('baseline_mae'), 'wape': m.get('wape'),
            'test_windows': m.get('test_windows'),
            'improvement': (1 - m['mae'] / m['baseline_mae']) if m.get('mae') and m.get('baseline_mae') else None,
            'history': [{'origin': h['origin'], 'actual': h['actual'], 'forecast': h['selected'], 'baseline': h['baseline']} for h in m.get('history', [])],
            'prediction': f.get('prediction'), 'baseline': f.get('baseline'),
            'already_booked': f.get('already_booked'), 'window_end': f.get('window_end'),
        })
    live_meta = planning.get('live', {})
    ev = return_evidence or {}
    tp, fn, fp = ev.get('threshold_TP', 0), ev.get('threshold_FN', 0), ev.get('threshold_FP', 0)
    rows = ev.get('rows', 0)
    tn = rows - tp - fn - fp if rows else 0
    return {
        'forecasts': models,
        'forecast_origin': (live_meta.get('latest') or {}).get('origin'),
        'forecast_stale': bool(live_meta.get('stale')),
        'repeat': {
            'eligible': repeat.get('eligible_customers'),
            'top': repeat.get('customers', [])[:8],
            'evaluation': repeat.get('evaluation') or {},
            'notice': repeat.get('notice'),
        },
        'return_model': {
            'rows': rows, 'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn,
            'recall': tp / (tp + fn) if (tp + fn) else None,
            'precision': tp / (tp + fp) if (tp + fp) else None,
            'accuracy': (tp + tn) / rows if rows else None,
            'notice': ev.get('notice'),
        },
        'research_candidate': (research_best or {}).get('candidate'),
        'run_rate': run_rate(trend),
    }


def prescriptive(desc, pred, review, work):
    actions = []
    counts = review.get('counts', {})
    tasks = review.get('tasks', [])
    upcoming_rm = sum(float(t.get('sales_remaining_balance_rm') or 0) for t in tasks if t['review_kind'] == 'upcoming')
    missing_rm = sum(float(t.get('sales_remaining_balance_rm') or 0) for t in tasks if t['review_kind'] == 'missing')

    if work.get('source_stale'):
        actions.append({'priority': 'high', 'area': 'Data', 'title': 'Refresh source records before acting',
            'why': 'The published Sheets/Calendar release is older than 36 hours, so forecasts and follow-up lists may be out of date.',
            'action': 'Run the daily reporting refresh, then reopen this page.', 'impact': None, 'link': '#status', 'link_label': 'Open models'})
    if counts.get('upcoming'):
        actions.append({'priority': 'high', 'area': 'Cash flow', 'title': f"Check {counts['upcoming']} payment reminder{'s' if counts['upcoming'] != 1 else ''} due in the next 7 days",
            'why': 'These contracts have a recorded balance and an owner-defined reminder date this week.',
            'action': 'Confirm the latest Sales balance, then contact the customer if still appropriate.', 'impact': upcoming_rm, 'impact_label': 'Recorded balance',
            'link': '#home', 'link_label': 'Open follow-ups'})
    if counts.get('missing'):
        actions.append({'priority': 'medium', 'area': 'Cash flow', 'title': f"Add reminder dates for {counts['missing']} contract{'s' if counts['missing'] != 1 else ''}",
            'why': 'A balance is recorded but no reminder schedule exists, so these balances cannot be followed up on time.',
            'action': 'Check contract terms and add verified reminder dates in the Sales sheet.', 'impact': missing_rm, 'impact_label': 'Recorded balance',
            'link': '#payments', 'link_label': 'Open payments'})

    hours = next((f for f in pred['forecasts'] if f['id'] == 'booked_hours_h1'), None)
    if hours and hours.get('prediction'):
        gap = hours['prediction'] - (hours.get('already_booked') or 0)
        actions.append({'priority': 'medium', 'area': 'Capacity', 'title': f"Plan for about {round(hours['prediction'])} appointment hours next week",
            'why': f"The planning model expects ~{round(hours['prediction'])} hours; {round(hours.get('already_booked') or 0)} were already booked when it was scored (historical error ±{hours['mae']:.0f} h).",
            'action': f"Keep roughly {max(0, round(gap))} hours of team time open for new bookings and set a buffer of {round(hours['mae'])} h.",
            'impact': None, 'link': '#plan', 'link_label': 'Open scheduling'})

    top = pred['repeat']['top'][:5]
    if top:
        value = len(top) * (desc['kpis'].get('avg_sale_rm') or 0)
        actions.append({'priority': 'medium', 'area': 'Growth', 'title': f"Offer a follow-up programme to the top {len(top)} repeat-purchase prospects",
            'why': f"The experimental repeat-purchase ranking scores {pred['repeat']['eligible']} recent first-time customers; the top group is listed below.",
            'action': 'Call or WhatsApp with a maintenance-package offer before their 90-day window closes.', 'impact': value, 'impact_label': 'If all rebook at avg sale',
            'link': '#customers', 'link_label': 'Open customers'})

    k = desc['kpis']
    if k.get('repeat_rate') is not None and k['repeat_rate'] < 0.25:
        actions.append({'priority': 'low', 'area': 'Retention', 'title': f"Lift the repeat-customer rate from {k['repeat_rate']*100:.0f}%",
            'why': 'Most customer groups have bought only one programme, so retention is the largest untapped revenue pool.',
            'action': 'Bundle a 3x/upsell offer into the final paid service visit and track acceptance.', 'impact': None,
            'link': '#customers', 'link_label': 'Open customers'})

    peak = max(desc['weekday'], key=lambda r: r['value']) if desc['weekday'] else None
    working = [r for r in desc['weekday'] if peak and r['value'] >= 0.2 * peak['value']]  # skip closed days
    low = min(working, key=lambda r: r['value']) if working else None
    if peak and low and peak['value']:
        actions.append({'priority': 'low', 'area': 'Operations', 'title': f"Balance workload: {peak['label']} is the busiest day, {low['label']} the quietest",
            'why': f"Over the last 12 months {peak['label']} had {peak['value']:,} appointments versus {low['value']:,} on {low['label']}.",
            'action': f"Steer flexible bookings and inspections toward {low['label']} when offering slots.", 'impact': None,
            'link': '#plan', 'link_label': 'Open scheduling'})

    if k.get('warranty_rate_12m') is not None:
        actions.append({'priority': 'low', 'area': 'Quality', 'title': f"Watch warranty signals ({k['warranty_rate_12m']*100:.1f}% of appointments)",
            'why': 'Calendar warranty signals indicate customers asking for return visits. They are not proof of treatment failure.',
            'action': 'Review hotspot areas on the heatmap and check treatment notes where signals cluster.', 'impact': None,
            'link': '/maps', 'link_label': 'Open heatmaps'})

    order = {'high': 0, 'medium': 1, 'low': 2}
    actions.sort(key=lambda a: order[a['priority']])
    return {'actions': actions,
            'capacity': {'forecast_hours': hours.get('prediction') if hours else None,
                         'already_booked': hours.get('already_booked') if hours else None,
                         'mae': hours.get('mae') if hours else None,
                         'saved_capacity_hours': (work.get('settings') or {}).get('capacity_hours')},
            'notice': 'Recommendations are rule-based suggestions built from recorded data and experimental models. Staff decide; nothing is sent or changed automatically.'}


# ---------------------------------------------------------------- Design
def _hours_per_booking(pred):
    hours = next((f for f in pred['forecasts'] if f['id'] == 'booked_hours_h1'), None)
    books = next((f for f in pred['forecasts'] if f['id'] == 'booking_entries_h2'), None)
    if not hours or not books or not hours['history'] or not books['history']:
        return None
    weekly_hours = sum(h['actual'] for h in hours['history']) / len(hours['history'])
    weekly_books = sum(h['actual'] for h in books['history']) / len(books['history']) / 2
    return weekly_hours / weekly_books if weekly_books else None


def design(desc, pred, review, work, risk=None):
    """Candidate courses of action, each with a model- or trend-based expected outcome."""
    k = desc['kpis']
    avg = k.get('avg_sale_rm') or 0
    tasks = review.get('tasks', [])
    counts = review.get('counts', {})
    options = []

    due = [t for t in tasks if t['review_kind'] in ('upcoming', 'missing')]
    due_rm = sum(float(t.get('sales_remaining_balance_rm') or 0) for t in due)
    if due:
        options.append({'id': 'collect', 'title': 'Follow up outstanding contract balances', 'lever': 'Cash flow',
            'description': f"Confirm {len(due)} recorded balances ({counts.get('upcoming', 0)} reminders due this week, {counts.get('missing', 0)} with no reminder date) and contact customers where appropriate.",
            'expected_value_rm': due_rm, 'expected_label': f"{len(due)} balances to confirm",
            'basis': 'Recorded Sales balances and owner reminder dates (descriptive, not a payment prediction).',
            'confidence': 'medium', 'effort': 'low', 'urgency': 'high' if counts.get('upcoming') else 'medium', 'horizon': 'This week',
            'link': '#home', 'link_label': 'Open follow-ups'})

    ev = pred['repeat'].get('evaluation') or {}
    hit = (ev.get('cases_in_review_list') or 0) / ev['review_budget'] if ev.get('review_budget') else None
    n = min(20, pred['repeat'].get('eligible') or 0)
    if n and hit:
        conv = n * hit
        options.append({'id': 'repeat', 'title': f'Re-engage the top {n} likely repeat buyers', 'lever': 'Growth',
            'description': 'Offer a maintenance package to the first-time customers most likely to buy again, within 90 days of their first purchase.',
            'expected_value_rm': conv * avg, 'expected_label': f"about {conv:.0f} extra purchases",
            'basis': f"Historical hit rate in the model's review list {hit*100:.1f}% (vs {ev.get('prevalence', 0)*100:.1f}% at random, lift ×{ev.get('review_lift', 0):.1f}) × average sale.",
            'confidence': 'low', 'effort': 'medium', 'urgency': 'medium', 'horizon': 'Next 90 days',
            'link': '#customers', 'link_label': 'Open customers'})

    cand = pred.get('research_candidate') or {}
    if cand.get('pooled_precision') and k.get('repeat_rate') is not None:
        monthly_first = (k.get('last30_sales_rows') or 0)
        flagged = monthly_first * (cand['positive_windows'] + cand['FP']) / max(1, cand['services'])
        conv = flagged * cand['pooled_precision'] * 0.25
        options.append({'id': 'renewal', 'title': 'Offer renewal at the final paid service', 'lever': 'Retention',
            'description': 'When a home treatment programme reaches its last paid visit, the technician offers the next programme. Start with the customers most likely to need us again.',
            'expected_value_rm': conv * avg, 'expected_label': f"about {conv:.0f} renewals a month",
            'basis': f"Research model: recall {cand['pooled_recall']*100:.0f}%, precision {cand['pooled_precision']*100:.0f}%; assumes 1 in 4 flagged customers accept.",
            'confidence': 'low', 'effort': 'medium', 'urgency': 'low', 'horizon': 'Monthly',
            'link': '#customers', 'link_label': 'Open customers'})

    hours = next((f for f in pred['forecasts'] if f['id'] == 'booked_hours_h1'), None)
    if hours and hours.get('prediction'):
        options.append({'id': 'capacity', 'title': 'Match next week\'s roster to forecast demand', 'lever': 'Capacity',
            'description': f"Staff for about {round(hours['prediction'])} appointment hours (±{hours['mae']:.0f} h) so slots are neither lost nor left idle.",
            'expected_value_rm': None, 'expected_label': f"{round(hours['prediction'])} h forecast",
            'basis': f"Hours model ({hours['algorithm']}): mean error {hours['mae']:.1f} h vs baseline {hours['baseline_mae']:.1f} h over {hours['test_windows']} back-test weeks.",
            'confidence': 'medium', 'effort': 'low', 'urgency': 'high', 'horizon': 'Next week',
            'link': '#plan', 'link_label': 'Open scheduling'})

    hpb = _hours_per_booking(pred)
    warr = k.get('warranty_rate_12m')
    if warr and k.get('appointments_12m'):
        monthly_warranty = k['appointments_12m'] * warr / 12
        saved = monthly_warranty * 0.10
        options.append({'id': 'quality', 'title': 'Cut warranty revisits by 10% in hotspot areas', 'lever': 'Quality',
            'description': 'Where warranty visits cluster on the heatmap, read the treatment notes and add an inspection visit so the problem is fixed the first time.',
            'expected_value_rm': None, 'expected_label': f"about {saved:.0f} fewer return visits a month" + (f" ({saved*hpb:.0f} team hours)" if hpb else ''),
            'basis': f"{warr*100:.1f}% of the last 12 months' appointments carried a warranty signal (~{monthly_warranty:.0f}/month). 10% reduction is a planning assumption.",
            'confidence': 'low', 'effort': 'high', 'urgency': 'low', 'horizon': '3 months',
            'link': '/maps', 'link_label': 'Open heatmaps'})

    if risk and risk.get('status') not in (None, 'unavailable') and risk.get('high_risk'):
        ev = risk['evaluation']
        hpb = _hours_per_booking(pred)
        options.append({'id': 'warranty_risk', 'title': f"Check in early with {risk['high_risk']} high-risk properties", 'lever': 'Quality',
            'description': 'Call or inspect properties the warranty-risk model flags (20% or higher chance of a warranty visit) before their 30-day window closes.',
            'expected_value_rm': None, 'expected_label': f"about {risk['high_risk_expected_calls']:.0f} warranty visits expected" + (f" ({risk['high_risk_expected_calls']*hpb:.0f} team hours)" if hpb else ''),
            'basis': f"Warranty-risk model: test AUC {ev['roc_auc']:.2f}; the top 20% of visits held {ev['top20_recall']*100:.0f}% of warranty calls ({ev['top20_lift']:.1f}x the average rate).",
            'confidence': 'medium', 'effort': 'low', 'urgency': 'high', 'horizon': 'Next 30 days',
            'link': '#risk', 'link_label': 'Open warranty risk'})

    growth = desc.get('district_growth') or []
    if growth:
        g = growth[0]
        options.append({'id': 'area', 'title': f"Focus marketing on {g['label']}", 'lever': 'Demand',
            'description': f"{g['label']} has grown faster than any other district this year. Put leaflets and ads there and group its appointments on the same days.",
            'expected_value_rm': max(0.0, g['now'] - g['before']), 'expected_label': f"sales {(g['change'] or 0)*100:+.0f}% on last year so far",
            'basis': 'Year-to-date located sales versus the same period last year (trend, not a causal estimate).',
            'confidence': 'low', 'effort': 'medium', 'urgency': 'low', 'horizon': 'This quarter',
            'link': '#business', 'link_label': 'Open area explorer'})
    return {'options': options,
            'hours_per_booking': hpb,
            'notice': 'Expected outcomes combine saved model evaluations with stated assumptions. They are planning estimates, not guarantees.'}


# ---------------------------------------------------------------- Choice
LEVELS = {'low': 1, 'medium': 2, 'high': 3}
DEFAULT_WEIGHTS = {'value': 0.35, 'confidence': 0.25, 'urgency': 0.25, 'effort': 0.15}


def score_options(options, weights=None):
    w = weights or DEFAULT_WEIGHTS
    top_value = max([o['expected_value_rm'] or 0 for o in options] + [1])
    ranked = []
    for o in options:
        parts = {
            'value': (o['expected_value_rm'] or 0) / top_value if o['expected_value_rm'] else 0.35,
            'confidence': (LEVELS[o['confidence']] - 1) / 2,
            'urgency': (LEVELS[o['urgency']] - 1) / 2,
            'effort': (3 - LEVELS[o['effort']]) / 2,
        }
        total = sum(w[key] * parts[key] for key in w) / sum(w.values())
        ranked.append({**o, 'parts': parts, 'score': round(total * 100, 1)})
    ranked.sort(key=lambda r: r['score'], reverse=True)
    for i, r in enumerate(ranked):
        r['rank'] = i + 1
    return ranked


# ---------------------------------------------------------------- Implementation
def _status(value, good, warn, higher_is_better=True):
    if value is None:
        return 'unknown'
    if not higher_is_better:
        value, good, warn = -value, -good, -warn
    return 'good' if value >= good else 'warn' if value >= warn else 'bad'


TARGETS_FILE = Path(__file__).parent / 'performance_targets.json'


def load_targets():
    try:
        return json.loads(TARGETS_FILE.read_text(encoding='utf-8'))['targets']
    except (FileNotFoundError, ValueError, KeyError):
        return {}


def target_row(key, value, targets=None):
    t = (targets if targets is not None else load_targets()).get(key)
    if not t:
        return {'metric': key, 'value': value, 'format': 'pct', 'benchmark': None, 'benchmark_label': 'no target set', 'change': None, 'status': 'unknown'}
    confirmed = t.get('status') == 'confirmed'
    label = ('owner target' if confirmed else 'target to confirm with the owner') + (f", confirmed {t['confirmed_on']}" if confirmed and t.get('confirmed_on') else '')
    return {'metric': t['label'].replace(' (ceiling)', ''), 'value': value, 'format': 'pct', 'benchmark': t['target'], 'benchmark_label': label,
            'target_status': t.get('status'), 'change': None,
            'status': _status(value, t['target'], t['watch'], higher_is_better=t.get('direction') != 'lower')}


def performance(desc, pred, work):
    k = desc['kpis']
    c = desc['contracts']
    counts = (work or {}).get('counts') or {}
    total = counts.get('total') or 0
    done = (counts.get('reviewed') or 0) + (counts.get('status') or 0)
    bk = next((f for f in pred['forecasts'] if f['id'] == 'booking_entries_h2'), None)
    hours = next((f for f in pred['forecasts'] if f['id'] == 'booked_hours_h1'), None)
    collected = c['paid_rm'] / c['value_rm'] if c['value_rm'] else None
    scorecard = [
        {'metric': 'Sales year-to-date', 'value': k['ytd_sales_rm'], 'format': 'rm', 'benchmark': k['prev_ytd_sales_rm'], 'benchmark_label': 'same period last year',
         'change': k['ytd_change'], 'status': _status(k['ytd_change'], 0.0, -0.05)},
        {'metric': 'Sales, last 30 days', 'value': k['last30_sales_rm'], 'format': 'rm', 'benchmark': k['prev30_sales_rm'], 'benchmark_label': 'previous 30 days',
         'change': k['last30_change'], 'status': _status(k['last30_change'], 0.0, -0.10)},
        target_row('repeat_rate', k['repeat_rate']),
        target_row('warranty_rate', k['warranty_rate_12m']),
        target_row('collected_share', collected),
        {'metric': 'Follow-ups actioned', 'value': done / total if total else None, 'format': 'pct', 'benchmark': 1.0, 'benchmark_label': f'{total} open follow-ups',
         'change': None, 'status': _status(done / total if total else None, 0.8, 0.4)},
        {'metric': 'Booking forecast error', 'value': bk['wape'] if bk else None, 'format': 'pct', 'benchmark': 0.15, 'benchmark_label': 'largest acceptable error',
         'change': None, 'status': _status(bk['wape'] if bk else None, 0.10, 0.15, higher_is_better=False)},
        {'metric': 'Hours forecast, gain over a simple average', 'value': hours['improvement'] if hours else None, 'format': 'pct', 'benchmark': 0.0, 'benchmark_label': 'must be better than a simple average',
         'change': None, 'status': _status(hours['improvement'] if hours else None, 0.10, 0.0)},
    ]
    trend = desc['trend']
    plan_vs_actual = []
    for i in range(3, len(trend)):
        expected = sum(t['sales_rm'] for t in trend[i - 3:i]) / 3
        plan_vs_actual.append({'month': trend[i]['month'], 'actual': trend[i]['sales_rm'], 'expected': expected})
    errors = []
    if bk:
        errors = [{'origin': h['origin'], 'model': abs(h['forecast'] - h['actual']), 'baseline': abs(h['baseline'] - h['actual'])} for h in bk['history']]
    return {'scorecard': scorecard,
            'plan_vs_actual': plan_vs_actual[-12:],
            'forecast_errors': errors,
            'followup': {'total': total, 'open': counts.get('open') or 0, 'reviewed': counts.get('reviewed') or 0,
                         'in_progress': counts.get('status') or 0, 'upcoming': counts.get('upcoming') or 0, 'missing': counts.get('missing') or 0},
            'contracts': c,
            'notice': 'Targets marked "working" are placeholders for management to confirm. Statuses compare recorded data, not audited results.'}


RETURN_RISK_FILE = Path(__file__).parent / 'models' / 'return_risk_v1.json'


def return_risk_evidence(desc):
    """Frozen evidence for the return-visit risk score plus the size of the problem it addresses."""
    try:
        ev = json.loads(RETURN_RISK_FILE.read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        return {'status': 'unavailable'}
    k = desc.get('kpis', {})
    appts, rate = k.get('appointments_12m'), k.get('warranty_rate_12m')
    ev['problem'] = {'appointments_12m': appts, 'return_share_12m': rate,
                     'return_visits_per_month': round(appts * rate / 12, 1) if appts and rate is not None else None}
    return ev


def build(value, snapshot, planning, repeat, return_evidence, research_best, review, work, as_of):
    desc = descriptive(value, snapshot, as_of)
    pred = predictive(planning, repeat, return_evidence, research_best, desc['trend'])
    pres = prescriptive(desc, pred, review, work)
    try:
        from webapp import warranty_risk
        risk = warranty_risk.summary(value)
    except (FileNotFoundError, KeyError, ValueError, TypeError):
        risk = {'status': 'unavailable'}
    des = design(desc, pred, review, work, risk)
    from webapp import overview
    choice = {'ranked': score_options(des['options']), 'weights': DEFAULT_WEIGHTS,
              'levels': LEVELS, 'actions': pres['actions'], 'capacity': pres['capacity'], 'notice': pres['notice']}
    return {'as_of': as_of.isoformat(), 'release': value.get('receipt', {}).get('published_release'),
            'source_updated': work.get('source_updated'), 'source_stale': work.get('source_stale'),
            'coverage': value.get('receipt', {}).get('coverage', {}),
            'descriptive': desc, 'predictive': pred, 'design': des, 'choice': choice,
            'prescriptive': pres, 'performance': performance(desc, pred, work), 'warranty_risk': risk,
            'return_risk': return_risk_evidence(desc),
            'packages': overview.packages(value, as_of), 'areas': overview.areas(value, as_of)}
