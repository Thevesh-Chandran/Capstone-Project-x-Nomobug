"""Evaluate the declared check-in pilot (webapp/models/checkin_pilot_v1.json).

Process measures (any time): check-ins recorded by arm, customers reached, issues found,
return visits booked early, call minutes. Needs only the action ledger.

Outcome measures (once every pilot service is 30 days old, i.e. from 14 December 2026):
customer-initiated returns by arm. A recorded return for a service whose check-in booked a
return visit is counted as staff-booked, not customer-initiated, because calling customers
creates bookings that would otherwise look like returns. Needs a matured label export with the
model inputs and warranty_signal_within_30d (callback_live_features mature_labels).

  python scripts/evaluate_checkin_pilot.py --ledger <workspace_actions.json or state.json>
  python scripts/evaluate_checkin_pilot.py --ledger <...> --labels <mature_labels/dataset_input.json> --as-of 2026-12-14
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webapp import return_risk as rr  # noqa: E402


def process(ledger: dict, pilot: dict) -> dict:
    recs = [r for r in ledger.get('records', {}).values() if isinstance(r, dict) and r.get('kind') == 'checkin'
            and pilot['calls_from'] <= str(r.get('updated_at', ''))[:10] <= pilot['calls_to']]
    out = {}
    for arm in ('call', 'comparison', None):
        group = [r for r in recs if r.get('pilot_arm') == arm]
        mins = [r['minutes'] for r in group if isinstance(r.get('minutes'), int)]
        out[arm or 'outside_pilot'] = {
            'recorded': len(group), **{k: sum(r.get('status') == k for r in group) for k in rr.OUTCOME_CHOICES},
            'mean_minutes': round(sum(mins) / len(mins), 1) if mins else None}
    out['comparison_contacted_by_mistake'] = out['comparison']['recorded']
    return out


def outcomes(rows: list[dict], ledger: dict, pilot: dict, as_of: date) -> dict:
    m = rr.load_model()
    saved = ledger.get('records', {})
    arms = {'call': [], 'comparison': []}
    immature = 0
    for r in rows:
        served = str(r.get('anchor_date'))[:10]
        p = rr.score(r, m)
        if not (pilot['served_from'] <= served <= pilot['served_to'] and p >= pilot['threshold']):
            continue
        if date.fromisoformat(served) + timedelta(days=rr.WINDOW_DAYS) > as_of:
            immature += 1
            continue
        key = rr.checkin_key(r.get('sales_record_id'), served)
        rec = saved.get(key) if isinstance(saved.get(key), dict) else {}
        returned = bool(int(float(r.get('warranty_signal_within_30d') or 0)))
        staff_booked = returned and rec.get('status') == 'visit_booked'
        arms[rr.pilot_arm(key, pilot)].append({'chance': p, 'returned': returned, 'staff_booked': staff_booked,
                                              'reached': rec.get('status') in rr.DONE})
    def summary(g):
        n = len(g)
        cust = sum(x['returned'] and not x['staff_booked'] for x in g)
        return {'services': n, 'reached': sum(x['reached'] for x in g), 'expected_returns': round(sum(x['chance'] for x in g), 2),
                'any_recorded_return': sum(x['returned'] for x in g), 'staff_booked_return': sum(x['staff_booked'] for x in g),
                'customer_initiated_return': cust, 'customer_initiated_rate': round(cust / n, 3) if n else None}
    res = {k: summary(v) for k, v in arms.items()}
    res.update(immature_excluded=immature, complete=immature == 0,
               note='Feasibility pilot with a small sample; report counts and rates, not a significance claim.')
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--ledger', required=True)
    ap.add_argument('--labels')
    ap.add_argument('--as-of', default=date.today().isoformat())
    a = ap.parse_args()
    pilot = rr.load_pilot()
    ledger = json.loads(Path(a.ledger).read_text(encoding='utf-8'))
    result = {'pilot': pilot['id'], 'process': process(ledger, pilot)}
    if a.labels:
        raw = json.loads(Path(a.labels).read_text(encoding='utf-8'))
        rows = [dict(zip(raw['columns'], r)) if isinstance(r, list) else r for r in raw['records']]
        result['outcomes'] = outcomes(rows, ledger, pilot, date.fromisoformat(a.as_of))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
