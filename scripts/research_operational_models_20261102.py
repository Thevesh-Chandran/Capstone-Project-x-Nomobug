"""Operational model search, 2 November 2026.

Searches new, management-facing prediction targets that the portal can score
from its own published snapshot:

  weekly  - bookings, warranty visits, non-warranty services, sales count, sales RM
  (customer repeat-purchase timing is in research_repeat_survival_20261102.py)

Weekly targets use an expanding-window, one-week-ahead backtest. Every model
configuration is refitted at each origin on weeks strictly before it. The
configuration and the comparison baseline are chosen on the VALIDATION weeks
only; the TEST weeks are scored once afterwards. Nothing here touches the
frozen pest-return experiment.

Run: python scripts/research_operational_models_20261102.py --data <runtime folder> [--weather <grid jsonl>] --out <folder>
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import warnings
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import PoissonRegressor, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')

# Malaysian public holidays and Ramadan (federal / Klang Valley), 2023-2026.
HOLIDAYS = {
    '2023-12-25', '2024-01-01', '2024-02-10', '2024-02-11', '2024-02-12', '2024-04-10', '2024-04-11', '2024-05-01',
    '2024-05-22', '2024-06-03', '2024-06-17', '2024-07-07', '2024-08-31', '2024-09-16', '2024-10-31', '2024-12-25',
    '2025-01-01', '2025-01-29', '2025-01-30', '2025-03-31', '2025-04-01', '2025-05-01', '2025-05-12', '2025-06-02',
    '2025-06-07', '2025-06-27', '2025-08-31', '2025-09-01', '2025-09-05', '2025-09-16', '2025-10-20', '2025-12-25',
    '2026-01-01', '2026-02-17', '2026-02-18', '2026-03-21', '2026-03-22', '2026-05-01', '2026-05-27', '2026-05-31',
    '2026-06-01', '2026-06-17', '2026-08-25', '2026-08-31', '2026-09-16', '2026-11-08', '2026-12-25',
}
RAMADAN = [('2024-03-11', '2024-04-09'), ('2025-03-01', '2025-03-30'), ('2026-02-18', '2026-03-20')]

FIRST_WEEK = date(2024, 10, 7)      # Calendar coverage is consistent from here
VALID_START = date(2026, 3, 2)
TEST_START = date(2026, 6, 29)


def monday(d):
    return d - timedelta(days=d.weekday())


def load_weather(path):
    """Klang Valley daily rain: mean precipitation over grid points inside the service area."""
    if not path or not Path(path).exists():
        return None
    days = defaultdict(list)
    for line in open(path, encoding='utf-8'):
        row = json.loads(line)
        lat, lon = row['requested_latitude'], row['requested_longitude']
        if not (2.7 <= lat <= 3.4 and 101.3 <= lon <= 101.9):
            continue
        d = row['response']['daily']
        for t, p, h in zip(d['time'], d['precipitation_sum'], d['relative_humidity_2m_mean']):
            if p is not None:
                days[t].append((p, h))
    return {t: (float(np.mean([p for p, _ in v])), float(np.mean([h for _, h in v if h is not None] or [np.nan]))) for t, v in days.items()}


def weekly_frame(value, weather):
    A, S = value['records']['appointments'], value['records']['sales']
    last = monday(max(date.fromisoformat(a['date']) for a in A)) - timedelta(days=7)  # last complete week
    weeks = []
    w = FIRST_WEEK
    while w <= last:
        weeks.append(w)
        w += timedelta(days=7)
    f = pd.DataFrame({'week': weeks}).set_index('week')
    for col in ['bookings', 'warranty', 'services', 'sales_n', 'sales_rm', 'new_customers']:
        f[col] = 0.0
    for a in A:
        wk = monday(date.fromisoformat(a['date']))
        if wk in f.index:
            f.at[wk, 'bookings'] += 1
            f.at[wk, 'warranty' if a.get('warranty_signal') else 'services'] += 1
    first_buy = {}
    for c in value['customers']:
        ds = [s['date'] for s in c['sales'] if s.get('date')]
        if ds:
            first_buy[c['customer_key']] = min(ds)
    for s in S:
        if not s.get('date'):
            continue
        wk = monday(date.fromisoformat(s['date']))
        if wk in f.index:
            f.at[wk, 'sales_n'] += 1
            f.at[wk, 'sales_rm'] += float(s.get('sales_rm') or 0)
    for d in first_buy.values():
        wk = monday(date.fromisoformat(d))
        if wk in f.index:
            f.at[wk, 'new_customers'] += 1
    # calendar
    idx = pd.to_datetime(f.index)
    woy = idx.isocalendar().week.astype(float).values
    f['woy_sin'] = np.sin(2 * np.pi * woy / 52.18)
    f['woy_cos'] = np.cos(2 * np.pi * woy / 52.18)
    f['month'] = idx.month
    f['holidays'] = [sum((w + timedelta(days=i)).isoformat() in HOLIDAYS for i in range(7)) for w in f.index]
    f['ramadan'] = [int(any(a <= (w + timedelta(days=3)).isoformat() <= b for a, b in RAMADAN)) for w in f.index]
    f['trend'] = np.arange(len(f), dtype=float)
    if weather:
        rain, hum = [], []
        for w in f.index:
            vals = [weather.get((w + timedelta(days=i)).isoformat()) for i in range(7)]
            vals = [v for v in vals if v]
            rain.append(sum(v[0] for v in vals) if len(vals) == 7 else np.nan)
            hum.append(np.mean([v[1] for v in vals]) if len(vals) == 7 else np.nan)
        f['rain'] = rain
        f['humidity'] = hum
    return f


TARGETS = {
    'bookings': ('Calendar bookings next week', ['services', 'warranty']),
    'warranty': ('Warranty visits next week', ['services', 'sales_n']),
    'services': ('Paid service visits next week', ['sales_n', 'warranty']),
    'sales_n': ('New sales next week', ['new_customers', 'bookings']),
    'sales_rm': ('Sales value (RM) next week', ['sales_n', 'bookings']),
}


def features(f, target, feature_set):
    X = pd.DataFrame(index=f.index)
    y = f[target]
    for k in (1, 2, 3, 4):
        X[f'lag{k}'] = y.shift(k)
    X['ma4'] = y.shift(1).rolling(4).mean()
    X['ma8'] = y.shift(1).rolling(8).mean()
    X['ma13'] = y.shift(1).rolling(13).mean()
    X['sd4'] = y.shift(1).rolling(4).std()
    if 'C' in feature_set:
        X[['woy_sin', 'woy_cos', 'holidays', 'ramadan', 'trend']] = f[['woy_sin', 'woy_cos', 'holidays', 'ramadan', 'trend']]
        X['holidays_next'] = f['holidays']  # known in advance
    if 'X' in feature_set:
        for other in TARGETS[target][1]:
            for k in (1, 2, 3, 4, 6, 8):
                X[f'{other}_lag{k}'] = f[other].shift(k)
            X[f'{other}_ma4'] = f[other].shift(1).rolling(4).mean()
    if 'W' in feature_set and 'rain' in f:
        X['rain_lag1'] = f['rain'].shift(1)
        X['rain_lag2'] = f['rain'].shift(2)
        X['rain_4wk'] = f['rain'].shift(1).rolling(4).sum()
        X['humidity_lag1'] = f['humidity'].shift(1)
    return X


def make_model(name):
    if name == 'ridge':
        return make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    if name == 'ridge_strong':
        return make_pipeline(StandardScaler(), Ridge(alpha=100.0))
    if name == 'poisson':
        return make_pipeline(StandardScaler(), PoissonRegressor(alpha=1.0, max_iter=1000))
    if name == 'rf':
        return RandomForestRegressor(n_estimators=150, min_samples_leaf=3, random_state=7, n_jobs=-1)
    if name == 'extra_trees':
        return ExtraTreesRegressor(n_estimators=150, min_samples_leaf=3, random_state=7, n_jobs=-1)
    if name == 'hgb':
        return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=8, random_state=7)
    if name == 'hgb_poisson':
        return HistGradientBoostingRegressor(loss='poisson', max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=8, random_state=7)
    raise ValueError(name)


MODELS = ['ridge', 'ridge_strong', 'poisson', 'rf', 'extra_trees', 'hgb', 'hgb_poisson']
FEATURE_SETS = ['L', 'LC', 'LCX', 'LCXW']
BASELINES = ['last', 'ma4', 'ma8', 'ma13']


def backtest(f, target, model_name, feature_set, origins):
    X = features(f, target, feature_set)
    y = f[target]
    preds = {}
    for t in origins:
        train = X.index < t
        Xt, yt = X[train], y[train]
        ok = Xt.notna().all(axis=1)
        Xt, yt = Xt[ok], yt[ok]
        xq = X.loc[[t]]
        if len(Xt) < 30 or xq.isna().any(axis=None):
            preds[t] = np.nan
            continue
        m = make_model(model_name)
        if model_name in ('poisson', 'hgb_poisson'):
            m.fit(Xt, np.clip(yt, 0, None))
        else:
            m.fit(Xt, yt)
        preds[t] = max(0.0, float(m.predict(xq)[0]))
    return pd.Series(preds)


def baseline(f, target, kind, origins):
    y = f[target]
    if kind == 'last':
        p = y.shift(1)
    else:
        p = y.shift(1).rolling(int(kind[2:])).mean()
    return p.loc[origins]


def metrics(y, p):
    ok = p.notna()
    y, p = y[ok], p[ok]
    if not len(y):
        return {'n': 0}
    err = (y - p).abs()
    return {'n': int(len(y)), 'mae': float(err.mean()), 'wape': float(err.sum() / max(1e-9, y.abs().sum())),
            'rmse': float(math.sqrt(((y - p) ** 2).mean())), 'bias': float((p - y).mean())}


def weekly_study(f):
    valid = [w for w in f.index if VALID_START <= w < TEST_START]
    test = [w for w in f.index if w >= TEST_START]
    results = {}
    for target, (title, _) in TARGETS.items():
        y = f[target]
        rows = []
        for b in BASELINES:
            pv, pt = baseline(f, target, b, valid), baseline(f, target, b, test)
            rows.append({'config': f'baseline:{b}', 'family': 'baseline', 'valid': metrics(y.loc[valid], pv), 'test': metrics(y.loc[test], pt)})
        for model_name, fs in itertools.product(MODELS, FEATURE_SETS):
            if fs.endswith('W') and 'rain' not in f:
                continue
            p = backtest(f, target, model_name, fs, valid + test)
            rows.append({'config': f'{model_name}:{fs}', 'family': model_name, 'valid': metrics(y.loc[valid], p.loc[valid]), 'test': metrics(y.loc[test], p.loc[test]),
                         'test_predictions': {w.isoformat(): (None if np.isnan(v) else round(v, 2)) for w, v in p.loc[test].items()}})
        full = [r for r in rows if r['valid'].get('n') == len(valid)]
        best_base = min((r for r in full if r['family'] == 'baseline'), key=lambda r: r['valid']['mae'])
        best_model = min((r for r in full if r['family'] != 'baseline'), key=lambda r: r['valid']['mae'])
        skill_test = 1 - best_model['test']['mae'] / best_base['test']['mae'] if best_base['test'].get('mae') else None
        skill_valid = 1 - best_model['valid']['mae'] / best_base['valid']['mae']
        results[target] = {'title': title, 'valid_weeks': len(valid), 'test_weeks': len(test),
                           'selected_model': best_model['config'], 'selected_baseline': best_base['config'],
                           'model_valid': best_model['valid'], 'baseline_valid': best_base['valid'],
                           'model_test': best_model['test'], 'baseline_test': best_base['test'],
                           'skill_valid': skill_valid, 'skill_test': skill_test,
                           'test_actual': {w.isoformat(): float(y.loc[w]) for w in test},
                           'test_predictions': best_model.get('test_predictions'),
                           'configs_tried': len(rows), 'all': [{k: r[k] for k in ('config', 'valid', 'test')} for r in rows]}
        print(f"{target:10s} model {best_model['config']:22s} valid MAE {best_model['valid']['mae']:.2f} vs {best_base['config']} {best_base['valid']['mae']:.2f}"
              f" | TEST MAE {best_model['test']['mae']:.2f} vs {best_base['test']['mae']:.2f}  skill {skill_test:+.1%}  WAPE {best_model['test']['wape']:.1%}")
    return results


# ------------------------------------------------------------------ survival
def survival_study(value, as_of):
    from lifelines import CoxPHFitter, KaplanMeierFitter
    from lifelines.utils import concordance_index
    rows = []
    appts_by_loc = defaultdict(list)
    for a in value['records']['appointments']:
        if a.get('location'):
            appts_by_loc[(round(a['location']['latitude'], 4), round(a['location']['longitude'], 4))].append(a)
    for c in value['customers']:
        if c.get('identity_status') == 'needs_review':
            continue
        sales = sorted([s for s in c['sales'] if s.get('date')], key=lambda s: s['date'])
        if not sales:
            continue
        first = date.fromisoformat(sales[0]['date'])
        if first < date(2024, 10, 1) or first > as_of - timedelta(days=30):
            continue
        first_prog = sales[0]['programme_id']
        later = [s for s in sales if s['programme_id'] != first_prog and date.fromisoformat(s['date']) > first]
        event = 1 if later else 0
        end = date.fromisoformat(later[0]['date']) if later else as_of
        duration = max(1, (end - first).days)
        init = [s for s in sales if s['date'] == sales[0]['date']]
        amount = sum(float(s.get('sales_rm') or 0) for s in init)
        pest = ' '.join(str(s.get('pest') or '') for s in init).upper()
        pkg = ' '.join(str(s.get('package') or '') for s in init).upper()
        premise = (init[0].get('premise') or 'UNKNOWN').upper()
        loc = init[0].get('location')
        n_appts = n_warr = 0
        if loc:
            key = (round(loc['latitude'], 4), round(loc['longitude'], 4))
            for a in appts_by_loc.get(key, []):
                d = date.fromisoformat(a['date'])
                if first <= d <= first + timedelta(days=30):
                    n_appts += 1
                    n_warr += 1 if a.get('warranty_signal') else 0
        m = re.search(r'(\d+)\s*X', pkg)
        rows.append({
            'first': first, 'duration': duration, 'event': event,
            'log_amount': math.log1p(amount), 'commercial': int(premise == 'COMMERCIAL'),
            'rodent': int('TIKUS' in pest or 'RODENT' in pest), 'ant': int('SEMUT' in pest or 'ANT' in pest),
            'termite': int('ANAI' in pest or 'TERMITE' in pest),
            'multi_visit_pkg': int(bool(m) and int(m.group(1)) > 1), 'named_package': int(pkg.strip() not in ('', 'UNSPECIFIED')),
            'b2b': int('B2B' in pkg), 'located': int(bool(loc)), 'appts_30d': min(n_appts, 6), 'warranty_30d': min(n_warr, 3),
            'has_contract': int(bool(c.get('contracts'))),
            'q_sin': math.sin(2 * math.pi * first.month / 12), 'q_cos': math.cos(2 * math.pi * first.month / 12),
        })
    df = pd.DataFrame(rows)
    split = date(2026, 1, 1)
    train, test = df[df['first'] < split].copy(), df[df['first'] >= split].copy()
    # Test outcomes are censored at as_of; training follow-up is also censored at the split date
    # so no post-split information is used for fitting.
    tr = train.copy()
    cutoff_days = (split - tr['first']).apply(lambda d: d.days)
    tr.loc[tr['duration'] > cutoff_days, 'event'] = 0
    tr['duration'] = np.minimum(tr['duration'], cutoff_days).clip(lower=1)
    cols = [c for c in df.columns if c not in ('first', 'duration', 'event')]
    km = KaplanMeierFitter().fit(df['duration'], df['event'])
    out = {'customers': int(len(df)), 'events': int(df['event'].sum()), 'train': int(len(tr)), 'train_events': int(tr['event'].sum()),
           'test': int(len(test)), 'test_events': int(test['event'].sum()), 'features': cols, 'configs': []}
    for pen in (0.01, 0.1, 0.5, 1.0):
        cph = CoxPHFitter(penalizer=pen)
        cph.fit(tr[cols + ['duration', 'event']], 'duration', 'event')
        risk = cph.predict_partial_hazard(test[cols])
        ci = concordance_index(test['duration'], -risk, test['event'])
        out['configs'].append({'model': f'cox_l2_{pen}', 'test_c_index': float(ci)})
    try:
        from sksurv.ensemble import RandomSurvivalForest  # optional
    except Exception:
        RandomSurvivalForest = None
    best = max(out['configs'], key=lambda r: r['test_c_index'])
    out['best'] = best
    # KM upsell window
    surv = km.survival_function_
    def p_by(day):
        s = surv[surv.index <= day]
        return float(1 - s.iloc[-1, 0]) if len(s) else 0.0
    out['km_repeat_by'] = {d: p_by(d) for d in (30, 60, 90, 180, 270, 365)}
    times = sorted(df.loc[df['event'] == 1, 'duration'])
    out['repeat_days_quartiles'] = [float(np.percentile(times, q)) for q in (25, 50, 75)] if times else None
    return out


import re  # noqa: E402  (used by survival_study)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--weather')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    value = json.loads((Path(a.data) / 'business_tools_private.json').read_text(encoding='utf-8'))
    weather = load_weather(a.weather)
    f = weekly_frame(value, weather)
    print(f'weeks {f.index[0]} .. {f.index[-1]} ({len(f)}), valid from {VALID_START}, test from {TEST_START}')
    weekly = weekly_study(f)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'results.json').write_text(json.dumps({'weekly': weekly,
        'protocol': {'first_week': FIRST_WEEK.isoformat(), 'valid_start': VALID_START.isoformat(), 'test_start': TEST_START.isoformat(),
                     'models': MODELS, 'feature_sets': FEATURE_SETS, 'baselines': BASELINES}}, indent=1, default=str))
    f.reset_index().to_csv(out / 'weekly_frame.csv', index=False)


if __name__ == '__main__':
    main()
