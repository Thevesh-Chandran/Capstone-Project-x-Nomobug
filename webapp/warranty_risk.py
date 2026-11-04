"""Property warranty-risk scoring (warranty_risk_v1). Read-only; no records change.

For every located property with a paid service visit in the last 30 days and no
warranty visit recorded since, estimate the chance that it needs a warranty visit
before that visit's 30-day window closes. Features match
scripts/research_property_warranty_20261102.py ('history' set) exactly.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

MODEL = Path(__file__).parent / 'models/warranty_risk_v1.json'
_cache = {}


def load():
    if 'm' not in _cache:
        _cache['m'] = json.loads(MODEL.read_text(encoding='utf-8'))
    return _cache['m']


def _key(loc):
    return (round(loc['latitude'], 4), round(loc['longitude'], 4))


def history_features(prior, d):
    """prior: list of (date, is_warranty) strictly before the scored visit."""
    paid = [p for p in prior if not p[1]]
    warr = [p for p in prior if p[1]]
    last = prior[-1][0] if prior else None
    return {
        'n_prior': len(prior), 'n_prior_paid': len(paid), 'n_prior_warranty': len(warr),
        'prior_warranty_rate': len(warr) / len(prior) if prior else 0.0,
        'warranty_last_90d': sum(1 for p in warr if (d - p[0]).days <= 90),
        'visits_last_90d': sum(1 for p in prior if (d - p[0]).days <= 90),
        'days_since_last': (d - last).days if last else 999,
        'first_visit': int(not prior),
    }


def score(features, model=None):
    model = model or load()
    x = [float(features[f]) for f in model['features']]
    total = 0.0
    for t in model['trees']:
        i = 0
        while t['l'][i] != -1:
            i = t['l'][i] if x[t['f'][i]] <= t['t'][i] else t['r'][i]
        total += t['p'][i]
    raw = min(max(total / len(model['trees']), 1e-4), 1 - 1e-4)
    c = model['calibration']
    return 1 / (1 + math.exp(-(c['a'] * math.log(raw / (1 - raw)) + c['b'])))


def open_windows(value, as_of=None, model=None):
    model = model or load()
    horizon = int(model['horizon_days'])
    visits = defaultdict(list)
    for a in value['records']['appointments']:
        if a.get('location') and a.get('date'):
            visits[_key(a['location'])].append((date.fromisoformat(a['date']), bool(a.get('warranty_signal')), a.get('district') or 'Unassigned'))
    dated = [v[0] for vs in visits.values() for v in vs]
    if not dated:
        return {'as_of': None, 'properties': [], 'expected_calls': 0.0}
    as_of = as_of or min(max(dated), date.today())
    names = {}
    for c in value.get('customers', []):
        for s in c.get('sales', []):
            if s.get('location'):
                names.setdefault(_key(s['location']), c['name'].strip())
    rows = []
    for key, vs in visits.items():
        vs.sort()
        paid = [i for i, v in enumerate(vs) if not v[1] and as_of - timedelta(days=horizon) < v[0] <= as_of]
        if not paid:
            continue
        i = paid[-1]
        d, _, district = vs[i]
        if any(w and d < d2 <= as_of for d2, w, _ in vs[i + 1:]):
            continue  # a warranty visit is already recorded for this window
        prior = [(p[0], p[1]) for p in vs[:i]]
        f = history_features(prior, d)
        p = score(f, model)
        cdf = model.get('timing_cdf')
        if cdf:  # chance remaining after the days already passed without a warranty visit
            done = cdf[min(len(cdf) - 1, (as_of - d).days)]
            p = p * (1 - done) / max(1e-9, 1 - p * done)
        rows.append({'property': names.get(key) or 'Unlinked property', 'district': district.split(' / ')[-1], 'last_service': d.isoformat(),
                     'days_left': horizon - (as_of - d).days, 'prior_visits': f['n_prior'], 'prior_warranty': f['n_prior_warranty'],
                     'risk': round(p, 4), 'linked': key in names})
    rows.sort(key=lambda r: -r['risk'])
    return {'as_of': as_of.isoformat(), 'horizon_days': horizon, 'open_windows': len(rows),
            'expected_calls': round(sum(r['risk'] for r in rows), 1), 'properties': rows}


def summary(value, top=15):
    try:
        model = load()
    except FileNotFoundError:
        return {'status': 'unavailable'}
    w = open_windows(value, model=model)
    flagged = [r for r in w['properties'] if r['risk'] >= 0.2]
    ev = model['evaluation']
    return {'status': model['status'], 'version': model['version'], 'question': model['question'], 'as_of': w['as_of'],
            'open_windows': w.get('open_windows', 0), 'expected_calls': w.get('expected_calls', 0.0),
            'high_risk': len(flagged), 'high_risk_expected_calls': round(sum(r['risk'] for r in flagged), 1),
            'properties': w['properties'][:top], 'evaluation': ev, 'selection': model['selection'],
            'trained_through': model['trained_through'], 'training_visits': model['training_visits']}
