"""Repeat-purchase timing study (survival analysis), 2 November 2026.

Question: after a customer's first programme, how likely are they to buy another
one, and when? Survival models use every customer, including recent ones whose
outcome is not known yet (censored), instead of discarding them like a fixed
90-day classifier does.

Protocol
- Cohort: first recorded purchase 2024-10-01 .. as_of - 30 days, identities not under review.
- Development: first purchase before 2026-01-01, follow-up CENSORED at 2026-01-01, so
  no later outcome is used for fitting or for choosing a configuration.
- Configuration choice: 5-fold cross-validated concordance (C-index) inside development.
- Test: customers whose first purchase is in 2026, outcomes up to as_of. Scored once.
- Comparison: the deployed repeat90_v1 ranking and two simple rules on the same test customers.

Run: python scripts/research_repeat_survival_20261102.py --data <runtime folder> --out <folder>
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
import warnings
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

warnings.filterwarnings('ignore')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPLIT = date(2026, 1, 1)
DISTRICTS = ['W.P. Kuala Lumpur', 'Petaling', 'Ulu Langat', 'Sepang', 'Gombak']


def build(value, as_of):
    appts = defaultdict(list)
    for a in value['records']['appointments']:
        if a.get('location'):
            appts[(round(a['location']['latitude'], 4), round(a['location']['longitude'], 4))].append(a)
    rows = []
    for c in value['customers']:
        if c.get('identity_status') == 'needs_review':
            continue
        sales = sorted([s for s in c['sales'] if s.get('date')], key=lambda s: s['date'])
        if not sales:
            continue
        first = date.fromisoformat(sales[0]['date'])
        if first < date(2024, 10, 1) or first > as_of - timedelta(days=30):
            continue
        prog = sales[0]['programme_id']
        later = [s for s in sales if s['programme_id'] != prog and s['date'] > sales[0]['date']]
        end = date.fromisoformat(later[0]['date']) if later else as_of
        init = [s for s in sales if s['date'] == sales[0]['date']]
        amount = sum(float(s.get('sales_rm') or 0) for s in init)
        pest = ' '.join(str(s.get('pest') or '') for s in init).upper()
        pkg = ' '.join(str(s.get('package') or '') for s in init).upper()
        premise = (init[0].get('premise') or 'UNKNOWN').upper()
        district = (init[0].get('district') or 'Unassigned').split(' / ')[-1]
        loc = init[0].get('location')
        n_appts = n_warr = 0
        if loc:
            for a in appts.get((round(loc['latitude'], 4), round(loc['longitude'], 4)), []):
                d = date.fromisoformat(a['date'])
                if first <= d <= first + timedelta(days=30):
                    n_appts += 1
                    n_warr += int(bool(a.get('warranty_signal')))
        m = re.search(r'(\d+)\s*X', pkg)
        visits = int(m.group(1)) if m else 1
        row = {
            'customer_key': c['customer_key'], 'first': first, 'event': int(bool(later)),
            'duration': max(1, (end - first).days),
            'log_amount': math.log1p(amount), 'amount_missing': int(amount <= 0),
            'commercial': int(premise == 'COMMERCIAL'), 'residential': int(premise == 'RESIDENTIAL'),
            'cockroach': int('LIPAS' in pest or 'GPC' in pest), 'rodent': int('TIKUS' in pest),
            'ant': int('SEMUT' in pest), 'termite': int('ANAI' in pest or 'TERMITE' in pest),
            'multi_pest': int(len(re.findall(r'LIPAS|TIKUS|SEMUT|ANAI|LIPAN|LALAT', pest)) > 1),
            'log_visits': math.log(min(visits, 24)), 'named_package': int(pkg.strip() not in ('', 'UNSPECIFIED')),
            'b2b': int('B2B' in pkg), 'promo': int('PROMO' in pest or 'PROMO' in pkg),
            'located': int(bool(loc)), 'appts_30d': min(n_appts, 6), 'warranty_30d': min(n_warr, 3),
            'has_contract': int(bool(c.get('contracts'))),
            'month_sin': math.sin(2 * math.pi * first.month / 12), 'month_cos': math.cos(2 * math.pi * first.month / 12),
        }
        for dname in DISTRICTS:
            row['d_' + dname.split()[-1].lower()] = int(district == dname)
        rows.append(row)
    return pd.DataFrame(rows)


FEATURE_SETS = {
    'basic': ['log_amount', 'amount_missing', 'commercial', 'residential', 'month_sin', 'month_cos'],
    'service': ['log_amount', 'amount_missing', 'commercial', 'residential', 'month_sin', 'month_cos',
                'cockroach', 'rodent', 'ant', 'termite', 'multi_pest', 'log_visits', 'named_package', 'b2b', 'promo'],
}
FEATURE_SETS['service_place'] = FEATURE_SETS['service'] + ['located', 'appts_30d', 'warranty_30d', 'has_contract'] + ['d_' + d.split()[-1].lower() for d in DISTRICTS]


def censor_at(df, when):
    out = df.copy()
    limit = (pd.Series([when] * len(out), index=out.index) - out['first']).apply(lambda d: d.days)
    out.loc[out['duration'] > limit, 'event'] = 0
    out['duration'] = np.minimum(out['duration'], limit).clip(lower=1)
    return out


def fit_predict(kind, params, train, test, cols):
    from sksurv.util import Surv
    y = Surv.from_arrays(train['event'].astype(bool), train['duration'].astype(float))
    Xtr, Xte = train[cols].astype(float).values, test[cols].astype(float).values
    if kind == 'cox':
        from sksurv.linear_model import CoxnetSurvivalAnalysis
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        m = CoxnetSurvivalAnalysis(l1_ratio=params['l1'], alphas=[params['alpha']], fit_baseline_model=True, max_iter=200000)
        m.fit((Xtr - mu) / sd, y)
        return m.predict((Xte - mu) / sd), m, (mu, sd)
    if kind == 'rsf':
        from sksurv.ensemble import RandomSurvivalForest
        m = RandomSurvivalForest(n_estimators=300, min_samples_leaf=params['leaf'], max_features='sqrt', random_state=7, n_jobs=-1)
        m.fit(Xtr, y)
        return m.predict(Xte), m, None
    if kind == 'gbs':
        from sksurv.ensemble import GradientBoostingSurvivalAnalysis
        m = GradientBoostingSurvivalAnalysis(n_estimators=params['n'], learning_rate=0.05, max_depth=2, subsample=0.8, random_state=7)
        m.fit(Xtr, y)
        return m.predict(Xte), m, None
    raise ValueError(kind)


CONFIGS = ([('cox', {'l1': l1, 'alpha': a}) for l1, a in itertools.product([0.01, 0.5, 1.0], [0.001, 0.01, 0.05, 0.1])]
           + [('rsf', {'leaf': leaf}) for leaf in (10, 25, 50)]
           + [('gbs', {'n': n}) for n in (100, 300)])


def cindex(df, risk):
    from sksurv.metrics import concordance_index_censored
    return float(concordance_index_censored(df['event'].astype(bool), df['duration'].astype(float), np.asarray(risk))[0])


def auc_at(df, risk, horizon):
    """Repeat within `horizon` days, among customers followed for at least that long (or who repeated earlier)."""
    from sklearn.metrics import average_precision_score, roc_auc_score
    ok = (df['duration'] >= horizon) | (df['event'] == 1)
    y = ((df['event'] == 1) & (df['duration'] <= horizon))[ok].astype(int)
    r = np.asarray(risk)[ok.values]
    if y.nunique() < 2:
        return None
    return {'n': int(ok.sum()), 'positives': int(y.sum()), 'roc_auc': float(roc_auc_score(y, r)),
            'average_precision': float(average_precision_score(y, r)), 'base_rate': float(y.mean())}


def lift_top(df, risk, horizon, share=0.2):
    ok = (df['duration'] >= horizon) | (df['event'] == 1)
    y = ((df['event'] == 1) & (df['duration'] <= horizon))[ok].astype(int).values
    r = np.asarray(risk)[ok.values]
    k = max(1, int(round(len(r) * share)))
    top = np.argsort(-r)[:k]
    return {'share': share, 'contacted': int(k), 'repeat_in_top': int(y[top].sum()), 'all_repeats': int(y.sum()),
            'capture': float(y[top].sum() / max(1, y.sum())), 'hit_rate': float(y[top].mean()), 'base_rate': float(y.mean()),
            'lift': float(y[top].mean() / max(1e-9, y.mean()))}


def repeat90_scores(value, test_df):
    from webapp import predictions
    model = json.loads((ROOT / 'webapp/models/repeat90_v1.json').read_text())
    by = {c['customer_key']: c for c in value['customers']}
    out = []
    for _, r in test_df.iterrows():
        c = by[r['customer_key']]
        sales = [s for s in c['sales'] if s.get('date') and s['date'] <= r['first'].isoformat()]
        out.append(predictions.rank_score(predictions.initial_features(sales), model))
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    value = json.loads((Path(a.data) / 'business_tools_private.json').read_text(encoding='utf-8'))
    as_of = max(date.fromisoformat(s['date']) for s in value['records']['sales'] if s.get('date'))
    df = build(value, as_of)
    dev = censor_at(df[df['first'] < SPLIT], SPLIT).reset_index(drop=True)
    test = df[df['first'] >= SPLIT].reset_index(drop=True)
    print(f'customers {len(df)}  development {len(dev)} ({dev.event.sum()} repeats, censored at {SPLIT})  test {len(test)} ({test.event.sum()} repeats by {as_of})')

    # 1. choose configuration by cross-validated C-index on development only
    kf = KFold(5, shuffle=True, random_state=7)
    cv = []
    for fs, cols in FEATURE_SETS.items():
        for kind, params in CONFIGS:
            scores = []
            for tr, va in kf.split(dev):
                try:
                    risk, _, _ = fit_predict(kind, params, dev.iloc[tr], dev.iloc[va], cols)
                    scores.append(cindex(dev.iloc[va], risk))
                except Exception as exc:  # noqa: BLE001
                    scores.append(np.nan)
            cv.append({'features': fs, 'model': kind, 'params': params, 'cv_c_index': float(np.nanmean(scores)), 'cv_sd': float(np.nanstd(scores))})
            print(f"  {fs:14s} {kind:4s} {params}  CV C-index {np.nanmean(scores):.3f}")
    best = max(cv, key=lambda r: r['cv_c_index'])
    print('selected', best)

    # 2. refit on all development data, score the 2026 test cohort once
    cols = FEATURE_SETS[best['features']]
    risk, model, scale = fit_predict(best['model'], best['params'], dev, test, cols)
    r90 = repeat90_scores(value, test)
    rule_commercial = test['commercial'] * 10 + test['log_amount']
    compare = {}
    for name, rk in [('selected_survival_model', risk), ('deployed_repeat90_v1', r90), ('rule_commercial_then_amount', rule_commercial.values)]:
        compare[name] = {'c_index': cindex(test, rk), 'auc_90d': auc_at(test, rk, 90), 'auc_180d': auc_at(test, rk, 180), 'top20_90d': lift_top(test, rk, 90)}
        c = compare[name]
        print(f"TEST {name:28s} C {c['c_index']:.3f}  AUC90 {c['auc_90d']['roc_auc'] if c['auc_90d'] else None}  top20% lift {c['top20_90d']['lift']:.2f}x capture {c['top20_90d']['capture']:.0%}")

    # 3. Kaplan-Meier timing (all customers) for the contact window
    from sksurv.nonparametric import kaplan_meier_estimator
    t, s = kaplan_meier_estimator(df['event'].astype(bool), df['duration'].astype(float))
    def p_by(day):
        m = t <= day
        return float(1 - s[m][-1]) if m.any() else 0.0
    rep = df.loc[df.event == 1, 'duration']
    timing = {'repeat_by_day': {d: p_by(d) for d in (30, 60, 90, 120, 180, 270, 365)},
              'repeat_day_quartiles': [float(np.percentile(rep, q)) for q in (25, 50, 75)]}
    by_segment = {}
    for seg, mask in [('commercial', df.commercial == 1), ('residential', df.residential == 1)]:
        t2, s2 = kaplan_meier_estimator(df.loc[mask, 'event'].astype(bool), df.loc[mask, 'duration'].astype(float))
        by_segment[seg] = {d: float(1 - s2[t2 <= d][-1]) if (t2 <= d).any() else 0.0 for d in (90, 180, 365)}
    timing['by_segment'] = by_segment
    print('timing', timing)

    # 4. final model for deployment: refit on ALL customers with current follow-up (cox only, portable)
    deploy = None
    if best['model'] == 'cox':
        _, m, (mu, sd) = fit_predict('cox', best['params'], df, df.head(1), cols)
        deploy = {'kind': 'coxnet', 'features': cols, 'mean': mu.tolist(), 'scale': sd.tolist(), 'coef': m.coef_[:, 0].tolist()}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'results.json').write_text(json.dumps({'as_of': as_of.isoformat(), 'cohort': {'customers': len(df), 'repeats': int(df.event.sum()),
        'development': len(dev), 'development_repeats': int(dev.event.sum()), 'test': len(test), 'test_repeats': int(test.event.sum())},
        'cv': cv, 'selected': best, 'test': compare, 'timing': timing, 'deploy': deploy}, indent=1, default=str))


if __name__ == '__main__':
    main()
