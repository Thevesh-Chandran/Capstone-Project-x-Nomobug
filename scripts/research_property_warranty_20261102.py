"""Property-level warranty-call risk, 2 November 2026 (exploratory challenger).

Question: after a paid service visit at a property, will the same property need a
warranty visit within 30 days? This is close to the frozen pest-return experiment
but uses every located Calendar appointment in the current snapshot (no frozen
inputs are changed; the frozen model and its future test are untouched).

Split by visit date: development < 2026-01-01; validation 2026-01-01..2026-04-30
(configuration choice); test 2026-05-01..(as_of - 30 days), scored once.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import warnings
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')
HORIZON = 30
VALID, TEST = date(2026, 1, 1), date(2026, 5, 1)


def weather_index(path):
    if not path or not Path(path).exists():
        return {}
    days = defaultdict(list)
    for line in open(path, encoding='utf-8'):
        r = json.loads(line)
        if 2.7 <= r['requested_latitude'] <= 3.4 and 101.3 <= r['requested_longitude'] <= 101.9:
            d = r['response']['daily']
            for t, p in zip(d['time'], d['precipitation_sum']):
                if p is not None:
                    days[t].append(p)
    return {t: float(np.mean(v)) for t, v in days.items()}


def build(value, rain, as_of):
    by_prop = defaultdict(list)
    for a in value['records']['appointments']:
        if a.get('location'):
            key = (round(a['location']['latitude'], 4), round(a['location']['longitude'], 4))
            by_prop[key].append((date.fromisoformat(a['date']), bool(a.get('warranty_signal')), a.get('pest') or 'UNSPECIFIED', a.get('district') or 'Unassigned', a['location'].get('uncertainty_km', 1.0)))
    sale_by_prop = defaultdict(list)
    for s in value['records']['sales']:
        if s.get('location') and s.get('date'):
            sale_by_prop[(round(s['location']['latitude'], 4), round(s['location']['longitude'], 4))].append(s)
    rows = []
    for key, visits in by_prop.items():
        visits.sort()
        sales = sorted(sale_by_prop.get(key, []), key=lambda s: s['date'])
        for i, (d, warr, pest, district, unc) in enumerate(visits):
            if warr or d > as_of - timedelta(days=HORIZON) or d < date(2024, 10, 1):
                continue
            prior = visits[:i]
            label = int(any(w and d < d2 <= d + timedelta(days=HORIZON) for d2, w, *_ in visits[i + 1:]))
            prev_paid = [p for p in prior if not p[1]]
            prev_warr = [p for p in prior if p[1]]
            last_any = prior[-1][0] if prior else None
            s_before = [s for s in sales if s['date'] <= d.isoformat()]
            last_sale = s_before[-1] if s_before else None
            r14 = [rain.get((d - timedelta(days=k)).isoformat()) for k in range(1, 15)]
            r14 = [x for x in r14 if x is not None]
            pkg = (last_sale.get('package') or '').upper() if last_sale else ''
            rows.append({
                'date': d, 'y': label,
                'n_prior': len(prior), 'n_prior_paid': len(prev_paid), 'n_prior_warranty': len(prev_warr),
                'prior_warranty_rate': len(prev_warr) / len(prior) if prior else 0.0,
                'warranty_last_90d': sum(1 for p in prev_warr if (d - p[0]).days <= 90),
                'visits_last_90d': sum(1 for p in prior if (d - p[0]).days <= 90),
                'days_since_last': (d - last_any).days if last_any else 999,
                'first_visit': int(not prior),
                'pest_ant': int(pest == 'ANT'), 'pest_termite': int(pest == 'TERMITE'), 'pest_cockroach': int(pest == 'COCKROACH'),
                'pest_rodent': int(pest == 'RODENT'), 'pest_known': int(pest != 'UNSPECIFIED'),
                'kl': int('Kuala Lumpur' in district), 'petaling': int('Petaling' in district), 'ulu_langat': int('Ulu Langat' in district),
                'unassigned': int(district == 'Unassigned'), 'precise': int(unc <= 1.0),
                'commercial': int(bool(last_sale) and (last_sale.get('premise') or '') == 'COMMERCIAL'),
                'sale_linked': int(bool(last_sale)),
                'log_sale_rm': math.log1p(float(last_sale.get('sales_rm') or 0)) if last_sale else 0.0,
                'days_since_sale': min(999, (d - date.fromisoformat(last_sale['date'])).days) if last_sale else 999,
                'pkg_multi': int(any(t in pkg for t in ('3X', '4X', '6X', '12X', '24X'))),
                'month_sin': math.sin(2 * math.pi * d.month / 12), 'month_cos': math.cos(2 * math.pi * d.month / 12),
                'rain_14d': sum(r14) if len(r14) == 14 else np.nan,
            })
    return pd.DataFrame(rows)


SETS = {
    'history': ['n_prior', 'n_prior_paid', 'n_prior_warranty', 'prior_warranty_rate', 'warranty_last_90d', 'visits_last_90d', 'days_since_last', 'first_visit'],
}
SETS['history_context'] = SETS['history'] + ['pest_ant', 'pest_termite', 'pest_cockroach', 'pest_rodent', 'pest_known', 'kl', 'petaling', 'ulu_langat', 'unassigned', 'precise', 'month_sin', 'month_cos']
SETS['history_context_sale'] = SETS['history_context'] + ['commercial', 'sale_linked', 'log_sale_rm', 'days_since_sale', 'pkg_multi']
SETS['all_with_rain'] = SETS['history_context_sale'] + ['rain_14d']


def model(name):
    return {
        'logistic': lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000, class_weight='balanced')),
        'rf': lambda: RandomForestClassifier(n_estimators=400, min_samples_leaf=10, class_weight='balanced_subsample', random_state=7, n_jobs=-1),
        'extra_trees': lambda: ExtraTreesClassifier(n_estimators=400, min_samples_leaf=10, class_weight='balanced', random_state=7, n_jobs=-1),
        'hgb': lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, min_samples_leaf=30, class_weight='balanced', random_state=7),
    }[name]()


def top_share(y, p, share=0.2):
    k = max(1, int(round(len(p) * share)))
    idx = np.argsort(-p)[:k]
    return {'flagged': k, 'hits': int(y[idx].sum()), 'precision': float(y[idx].mean()), 'recall': float(y[idx].sum() / max(1, y.sum())),
            'base_rate': float(y.mean()), 'lift': float(y[idx].mean() / max(1e-9, y.mean()))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--weather')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    value = json.loads((Path(a.data) / 'business_tools_private.json').read_text(encoding='utf-8'))
    as_of = max(date.fromisoformat(x['date']) for x in value['records']['sales'] if x.get('date'))
    df = build(value, weather_index(a.weather), as_of)
    dev, val, test = df[df.date < VALID], df[(df.date >= VALID) & (df.date < TEST)], df[df.date >= TEST]
    print(f'visits {len(df)} positive rate {df.y.mean():.3f} | dev {len(dev)} val {len(val)} test {len(test)} ({test.y.sum()} positives)')
    rows = []
    for fs, name in itertools.product(SETS, ['logistic', 'rf', 'extra_trees', 'hgb']):
        cols = SETS[fs]
        tr = dev.dropna(subset=cols)
        va = val.dropna(subset=cols)
        if len(va) < len(val) * 0.9:
            continue
        m = model(name).fit(tr[cols], tr.y)
        p = m.predict_proba(va[cols])[:, 1]
        rows.append({'features': fs, 'model': name, 'val_ap': float(average_precision_score(va.y, p)), 'val_auc': float(roc_auc_score(va.y, p))})
        print(f"  {fs:22s} {name:12s} val AP {rows[-1]['val_ap']:.3f} AUC {rows[-1]['val_auc']:.3f}")
    # baseline rule: prior warranty rate at the property
    base_val = float(average_precision_score(val.y, val.prior_warranty_rate + val.warranty_last_90d * 0.01))
    best = max(rows, key=lambda r: r['val_ap'])
    cols = SETS[best['features']]
    trv = pd.concat([dev, val]).dropna(subset=cols)
    te = test.dropna(subset=cols)
    m = model(best['model']).fit(trv[cols], trv.y)
    p = m.predict_proba(te[cols])[:, 1]
    rule = (te.prior_warranty_rate + te.warranty_last_90d * 0.01).values
    res = {'selected': best, 'baseline_rule_val_ap': base_val,
           'test': {'n': int(len(te)), 'positives': int(te.y.sum()), 'ap': float(average_precision_score(te.y, p)), 'auc': float(roc_auc_score(te.y, p)), 'top20': top_share(te.y.values, p)},
           'test_rule': {'ap': float(average_precision_score(te.y, rule)), 'auc': float(roc_auc_score(te.y, rule)), 'top20': top_share(te.y.values, rule)},
           'grid': rows}
    print('selected', best)
    print('TEST model', res['test'])
    print('TEST rule ', res['test_rule'])
    if hasattr(m, 'feature_importances_'):
        res['importance'] = dict(sorted(zip(cols, map(float, m.feature_importances_)), key=lambda x: -x[1]))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'results.json').write_text(json.dumps(res, indent=1, default=str))


if __name__ == '__main__':
    main()
