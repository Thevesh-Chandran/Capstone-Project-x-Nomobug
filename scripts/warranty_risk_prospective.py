"""Prospective (forward) test of warranty_risk_v1. Separate from the frozen pest-return experiment.

freeze   Score every open 30-day service window in a snapshot and write a write-once record.
evaluate Later, label each frozen window from a NEWER snapshot and report the results.

A window's label is 1 if the same property has a warranty visit dated after the frozen
snapshot date and on or before the window end (last paid service + 30 days). Nothing
after the freeze is used to make the predictions; frozen files are never overwritten.
Properties are stored as hashes of their rounded coordinates, never names.

  python scripts/warranty_risk_prospective.py freeze --data <runtime folder> --out <folder>
  python scripts/warranty_risk_prospective.py evaluate --freeze <freeze json> --data <newer runtime folder>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webapp import warranty_risk  # noqa: E402


def prop_hash(loc):
    return hashlib.sha256(f"{round(loc['latitude'], 4):.4f},{round(loc['longitude'], 4):.4f}".encode()).hexdigest()[:20]


def snapshot_date(value):
    return max(date.fromisoformat(a['date']) for a in value['records']['appointments'] if a.get('date') and date.fromisoformat(a['date']) <= date.today())


def freeze(data, out):
    raw = (Path(data) / 'business_tools_private.json').read_bytes()
    value = json.loads(raw)
    model_bytes = warranty_risk.MODEL.read_bytes()
    model = json.loads(model_bytes)
    as_of = snapshot_date(value)
    horizon = int(model['horizon_days'])
    visits = defaultdict(list)
    for a in value['records']['appointments']:
        if a.get('location') and a.get('date'):
            visits[prop_hash(a['location'])].append((date.fromisoformat(a['date']), bool(a.get('warranty_signal'))))
    rows = []
    for key, vs in visits.items():
        vs.sort()
        paid = [i for i, v in enumerate(vs) if not v[1] and as_of - timedelta(days=horizon) < v[0] <= as_of]
        if not paid:
            continue
        i = paid[-1]
        d = vs[i][0]
        if any(w and d < d2 <= as_of for d2, w in vs[i + 1:]):
            continue
        f = warranty_risk.history_features(vs[:i], d)
        p_full = warranty_risk.score(f, model)
        done = model['timing_cdf'][min(horizon, (as_of - d).days)]
        p = p_full * (1 - done) / max(1e-9, 1 - p_full * done)
        rows.append({'property': key, 'last_service': d.isoformat(), 'window_end': (d + timedelta(days=horizon)).isoformat(),
                     'risk': round(p, 5), 'risk_full_window': round(p_full, 5), 'high_risk': p >= 0.2, **f})
    rows.sort(key=lambda r: -r['risk'])
    created = datetime.now(timezone.utc).replace(microsecond=0)
    record = {'experiment': 'warranty_risk_v1_prospective', 'created_at_utc': created.isoformat(),
              'snapshot_date': as_of.isoformat(), 'source_sha256': hashlib.sha256(raw).hexdigest(),
              'model_sha256': hashlib.sha256(model_bytes).hexdigest(), 'model_version': model['version'],
              'label': f'warranty visit at the same property after {as_of.isoformat()} and on or before window_end',
              'evaluate_after': max(r['window_end'] for r in rows) if rows else None,
              'windows': len(rows), 'expected_calls': round(sum(r['risk'] for r in rows), 2),
              'high_risk_windows': sum(r['high_risk'] for r in rows), 'rows': rows}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f'freeze_{created:%Y%m%dT%H%M%SZ}.json'
    if path.exists():
        raise SystemExit(f'{path} exists; frozen records are never overwritten')
    body = json.dumps(record, indent=1)
    path.write_text(body, encoding='utf-8')
    (out / (path.stem + '.sha256')).write_text(hashlib.sha256(body.encode()).hexdigest() + '  ' + path.name + '\n')
    print(f"frozen {record['windows']} windows from snapshot {as_of}; expected warranty visits {record['expected_calls']}; "
          f"high risk {record['high_risk_windows']}; evaluate after {record['evaluate_after']} -> {path}")
    return path


def evaluate(freeze_path, data):
    rec = json.loads(Path(freeze_path).read_text(encoding='utf-8'))
    value = json.loads((Path(data) / 'business_tools_private.json').read_bytes())
    newer = snapshot_date(value)
    start = date.fromisoformat(rec['snapshot_date'])
    if newer <= start:
        raise SystemExit('The evaluation snapshot must be newer than the frozen snapshot')
    warr = defaultdict(list)
    for a in value['records']['appointments']:
        if a.get('location') and a.get('warranty_signal'):
            warr[prop_hash(a['location'])].append(date.fromisoformat(a['date']))
    matured = [r for r in rec['rows'] if date.fromisoformat(r['window_end']) <= newer]
    y = [int(any(start < d <= date.fromisoformat(r['window_end']) for d in warr.get(r['property'], []))) for r in matured]
    p = [r['risk'] for r in matured]
    res = {'freeze': Path(freeze_path).name, 'evaluated_with_snapshot': newer.isoformat(), 'matured_windows': len(matured),
           'pending_windows': len(rec['rows']) - len(matured), 'complete': len(matured) == len(rec['rows']),
           'warranty_visits': sum(y), 'expected': round(sum(p), 2)}
    if matured:
        hi = [yy for yy, r in zip(y, matured) if r['high_risk']]
        res['high_risk_windows'] = len(hi)
        res['high_risk_with_warranty'] = sum(hi)
        res['high_risk_rate'] = sum(hi) / len(hi) if hi else None
        res['other_rate'] = (sum(y) - sum(hi)) / max(1, len(y) - len(hi))
        k = max(1, round(len(p) * 0.2))
        top = sorted(range(len(p)), key=lambda i: -p[i])[:k]
        res['top20_capture'] = sum(y[i] for i in top) / sum(y) if sum(y) else None
        if 0 < sum(y) < len(y):
            from sklearn.metrics import average_precision_score, roc_auc_score
            res['roc_auc'] = roc_auc_score(y, p)
            res['average_precision'] = average_precision_score(y, p)
    print(json.dumps(res, indent=1))
    return res


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('freeze')
    f.add_argument('--data', required=True)
    f.add_argument('--out', default=str(ROOT / 'outputs/model_validation/20261102_warranty_risk_prospective'))
    e = sub.add_parser('evaluate')
    e.add_argument('--freeze', required=True)
    e.add_argument('--data', required=True)
    a = ap.parse_args()
    freeze(a.data, a.out) if a.cmd == 'freeze' else evaluate(a.freeze, a.data)


if __name__ == '__main__':
    main()
