"""Train and export the property warranty-risk model (warranty_risk_v1).

Configuration fixed by the 2 November 2026 study on validation data only:
Extra Trees, visit-history inputs, min_samples_leaf=20, max_features=0.5.

Exports a portable JSON (trees + Platt calibration) to webapp/models/warranty_risk_v1.json,
scored by webapp/warranty_risk.py with no scikit-learn dependency at runtime.

Run: python scripts/train_warranty_risk.py --data <runtime folder> [--weather <grid jsonl>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

import research_property_warranty_20261102 as study

ROOT = Path(__file__).resolve().parents[1]
FEATURES = study.SETS['history']
PARAMS = dict(n_estimators=200, min_samples_leaf=20, max_features=0.5, class_weight='balanced', random_state=7, n_jobs=-1)


def export_tree(t):
    tr = t.tree_
    value = tr.value[:, 0, :]
    prob = (value[:, 1] / value.sum(axis=1)).round(5)
    return {'f': tr.feature.tolist(), 't': np.round(tr.threshold, 5).tolist(), 'l': tr.children_left.tolist(), 'r': tr.children_right.tolist(), 'p': prob.tolist()}


def platt(scores, y):
    s = np.clip(scores, 1e-4, 1 - 1e-4)
    x = np.log(s / (1 - s)).reshape(-1, 1)
    lr = LogisticRegression(C=1e6).fit(x, y)
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def apply_platt(scores, a, b):
    s = np.clip(scores, 1e-4, 1 - 1e-4)
    return 1 / (1 + np.exp(-(a * np.log(s / (1 - s)) + b)))


def timing_cdf(value, horizon):
    """Share of warranty visits that arrive within k days of the paid visit, k = 0..horizon."""
    from collections import defaultdict
    from datetime import timedelta
    visits = defaultdict(list)
    for a in value['records']['appointments']:
        if a.get('location'):
            visits[(round(a['location']['latitude'], 4), round(a['location']['longitude'], 4))].append((date.fromisoformat(a['date']), bool(a.get('warranty_signal'))))
    gaps = []
    for vs in visits.values():
        vs.sort()
        for i, (d, w) in enumerate(vs):
            if not w:
                nxt = [d2 for d2, w2 in vs[i + 1:] if w2 and d < d2 <= d + timedelta(days=horizon)]
                if nxt:
                    gaps.append((nxt[0] - d).days)
    return [round(sum(g <= k for g in gaps) / max(1, len(gaps)), 4) for k in range(horizon + 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--weather')
    a = ap.parse_args()
    raw = (Path(a.data) / 'business_tools_private.json').read_bytes()
    value = json.loads(raw)
    as_of = max(date.fromisoformat(x['date']) for x in value['records']['sales'] if x.get('date'))
    df = study.build(value, study.weather_index(a.weather), as_of)
    dev, val, test = df[df.date < study.VALID], df[(df.date >= study.VALID) & (df.date < study.TEST)], df[df.date >= study.TEST]

    # 1. calibration fitted on validation scores of a development-only model
    m_dev = ExtraTreesClassifier(**PARAMS).fit(dev[FEATURES], dev.y)
    ca, cb = platt(m_dev.predict_proba(val[FEATURES])[:, 1], val.y.values)

    # 2. held-out test of the development+validation model (as in the study)
    trv = pd.concat([dev, val])
    m_tv = ExtraTreesClassifier(**PARAMS).fit(trv[FEATURES], trv.y)
    pt = apply_platt(m_tv.predict_proba(test[FEATURES])[:, 1], ca, cb)
    yt = test.y.values
    k = int(round(len(pt) * 0.2))
    top = np.argsort(-pt)[:k]
    evaluation = {
        'test_period': f"{study.TEST.isoformat()} to {test.date.max().isoformat()}", 'test_visits': int(len(test)), 'test_warranty_calls': int(yt.sum()),
        'base_rate': float(yt.mean()), 'roc_auc': float(roc_auc_score(yt, pt)), 'average_precision': float(average_precision_score(yt, pt)),
        'brier': float(brier_score_loss(yt, pt)), 'brier_always_base_rate': float(brier_score_loss(yt, np.full(len(yt), trv.y.mean()))),
        'top20_precision': float(yt[top].mean()), 'top20_recall': float(yt[top].sum() / yt.sum()), 'top20_lift': float(yt[top].mean() / yt.mean()),
        'expected_vs_actual_calls': [float(pt.sum()), int(yt.sum())],
        'rule_baseline_roc_auc': float(roc_auc_score(yt, test.prior_warranty_rate + test.warranty_last_90d * 0.01)),
    }

    # 3. final model on every matured visit, same calibration
    m = ExtraTreesClassifier(**PARAMS).fit(df[FEATURES], df.y)
    out = {
        'version': 'warranty_risk_v1', 'status': 'research_candidate', 'trained_through': df.date.max().isoformat(),
        'question': 'After a paid service visit, will the same property need a warranty visit within 30 days?',
        'horizon_days': study.HORIZON, 'algorithm': 'extra_trees', 'params': {k: v for k, v in PARAMS.items() if k != 'n_jobs'},
        'features': FEATURES, 'calibration': {'a': ca, 'b': cb}, 'training_visits': int(len(df)), 'training_calls': int(df.y.sum()),
        'evaluation': evaluation, 'source_sha256': hashlib.sha256(raw).hexdigest(),
        'selection': 'Configuration chosen by validation average precision (Jan to Apr 2026); test (May to Sep 2026) scored once with a development+validation fit.',
        'trees': [export_tree(t) for t in m.estimators_],
    }
    out['timing_cdf'] = timing_cdf(value, study.HORIZON)
    path = ROOT / 'webapp/models/warranty_risk_v1.json'
    path.write_text(json.dumps(out, separators=(',', ':')))
    print(json.dumps(evaluation, indent=1))
    print('saved', path, round(path.stat().st_size / 1e6, 2), 'MB')


if __name__ == '__main__':
    main()
