"""Return-visit risk score (return_risk_v1): scoring and the weekly check-in plan.

The model is the frozen logistic regression from scripts/research_return_risk_20261103.py.
Scoring here must give exactly the same numbers as the study; tests/test_return_risk.py checks this.

Live scoring reads `return_risk_predictors.json` from the runtime folder. It has the same
columns as the pipeline's predictor export (outputs/.../features/predictors/dataset_input.json):
recent recorded paid services with their pre-visit features and no outcome columns.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import date, datetime, timedelta
from pathlib import Path

MODEL_FILE = Path(__file__).parent / 'models' / 'return_risk_v1.json'
PREDICTORS = 'return_risk_predictors.json'
WINDOW_DAYS = 30
CHECK_IN_DAY = 10          # most recorded return calls arrive in the third and fourth week
DEFAULT_CALLS = 10         # weekly check-in capacity used until staff change it


def load_model(path: Path = MODEL_FILE) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))['model']


def _num(v, default=0.0):
    try:
        if v is None or v == '':
            return default
        x = float(v)
        return default if math.isnan(x) else x
    except (TypeError, ValueError):
        return default


def features(row: dict) -> dict:
    """Same transforms as `feats` in the study script, for one service row."""
    service = _num(row.get('service_number'))
    sessions = _num(row.get('package_sessions_recorded'))
    residential = 1.0 if str(row.get('premise_type') or '').upper() == 'RESIDENTIAL' else 0.0
    final = 1.0 if service >= sessions else 0.0
    gap = row.get('days_since_previous_service')
    gap_missing = 1.0 if gap is None or (isinstance(gap, float) and math.isnan(gap)) or gap == '' else 0.0
    pest = str(row.get('pest_category') or '').lower()
    return {
        'final_residential': residential * final,
        'final_service': final,
        'residential': residential,
        'three_service_programme': 1.0 if sessions == 3 else 0.0,
        'first_service': 1.0 if service == 1 else 0.0,
        'log_sale_rm': math.log1p(_num(row.get('sale_total_rm'))),
        'gap_missing': gap_missing,
        'gap_days_capped': 0.0 if gap_missing else min(max(_num(gap), 0.0), 120.0),
        'property_past_claims': min(max(_num(row.get('prior_property_warranty_claims')), 0.0), 4.0),
        'programme_past_claims': min(max(_num(row.get('prior_package_warranty_claims')), 0.0), 3.0),
        'property_claims_90d': min(max(_num(row.get('prior_property_claims_90d')), 0.0), 3.0),
        'cockroach_only': 1.0 if pest.strip() == 'lipas' else 0.0,
        'includes_rodent': 1.0 if 'tikus' in pest else 0.0,
    }


def score(row: dict, model: dict | None = None) -> float:
    m = model or load_model()
    f = features(row)
    z = m['intercept']
    for name, mean, scale, coef in zip(m['features'], m['scaler_mean'], m['scaler_scale'], m['coef']):
        z += coef * (f[name] - mean) / (scale or 1.0)
    return 1.0 / (1.0 + math.exp(-z))


def reasons(row: dict, model: dict | None = None, top: int = 2) -> list[str]:
    """Plain-language drivers that push this service's score up, largest first."""
    m = model or load_model()
    f = features(row)
    labels = {'final_residential': 'final service of a home programme', 'residential': 'home customer',
              'three_service_programme': '3-service programme', 'property_claims_90d': 'recent return at this address',
              'programme_past_claims': 'earlier return in this programme', 'final_service': 'final service',
              'cockroach_only': 'cockroach treatment', 'log_sale_rm': 'higher package price'}
    parts = []
    for name, mean, scale, coef in zip(m['features'], m['scaler_mean'], m['scaler_scale'], m['coef']):
        push = coef * (f[name] - mean) / (scale or 1.0)
        if name in labels and push > 0.05 and f[name] > 0:
            parts.append((push, labels[name]))
    out = []
    for _, text in sorted(parts, reverse=True):
        if text not in out:
            out.append(text)
    if 'final service of a home programme' in out and 'final service' in out:
        out.remove('final service')
    return out[:top]


def _names(value: dict) -> dict:
    names = {}
    for c in value.get('customers', []):
        for s in c.get('sales', []):
            if s.get('sale_id'):
                names[s['sale_id']] = c.get('name') or s['sale_id']
    return names


OUTCOME_CHOICES = {
    'no_issue': 'Spoke, no issue',
    'issue_found': 'Issue found, advice given',
    'visit_booked': 'Return visit booked',
    'no_answer': 'No answer',
}
DONE = ('no_issue', 'issue_found', 'visit_booked')  # a reached customer is not called again


PILOT_FILE = Path(__file__).parent / 'models' / 'checkin_pilot_v1.json'


def load_pilot(path: Path = PILOT_FILE) -> dict | None:
    return json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else None


def pilot_arm(key: str, pilot: dict) -> str:
    """Fixed 50/50 assignment declared before the pilot: the same service always gets the same arm."""
    return 'call' if int(hashlib.sha256(f"{pilot['salt']}|{key}".encode()).hexdigest()[:8], 16) % 2 == 0 else 'comparison'


def in_pilot(row: dict, pilot: dict | None) -> bool:
    return bool(pilot) and pilot['served_from'] <= row['serviced'] <= pilot['served_to'] and row['chance'] >= pilot['threshold']


def checkin_key(sale_id, serviced) -> str:
    """Ledger key for one check-in: a hash, so no customer identifier sits in the key."""
    return hashlib.sha256(f'checkin|{sale_id}|{str(serviced)[:10]}'.encode()).hexdigest()


def plan(rows: list[dict], as_of: date, calls: int = DEFAULT_CALLS, names: dict | None = None,
         model: dict | None = None, log: dict | None = None, pilot: dict | None = None) -> dict:
    """Prescriptive step: choose this week's check-ins with a fixed calling capacity.

    Every service whose 30-day window is still open is scored. Calls go to the highest
    chances first (each call reaches at most one expected return, so ranking by chance
    maximises returns reached for a fixed number of calls). Services already past day 20
    are left out because most return calls have already arrived by then.
    """
    m = model or load_model()
    names = names or {}
    saved = (log or {}).get('records', {})
    open_rows = []
    for r in rows:
        served = date.fromisoformat(str(r.get('anchor_date'))[:10])
        age = (as_of - served).days
        if age < 0 or age >= WINDOW_DAYS:
            continue
        p = score(r, m)
        open_rows.append({'sale_id': r.get('sales_record_id'), 'name': names.get(r.get('sales_record_id')) or r.get('sales_record_id'),
                          'serviced': served.isoformat(), 'days_since': age,
                          'call_on': max(as_of, served + timedelta(days=CHECK_IN_DAY)).isoformat(),
                          'window_ends': (served + timedelta(days=WINDOW_DAYS)).isoformat(),
                          'chance': round(p, 4), 'service': f"{int(_num(r.get('service_number')))} of {int(_num(r.get('package_sessions_recorded')))}",
                          'premise': (r.get('premise_type') or '').title(), 'why': reasons(r, m)})
        row = open_rows[-1]
        row['key'] = checkin_key(row['sale_id'], row['serviced'])
        rec = saved.get(row['key'])
        if isinstance(rec, dict) and rec.get('kind') == 'checkin' and rec.get('status') in OUTCOME_CHOICES:
            row['outcome'] = {'status': rec['status'], 'label': OUTCOME_CHOICES[rec['status']],
                              'note': rec.get('note', ''), 'minutes': rec.get('minutes'),
                              'saved_at': str(rec.get('updated_at', ''))[:10]}
    open_rows.sort(key=lambda x: -x['chance'])
    active = bool(pilot) and pilot['calls_from'] <= as_of.isoformat() <= pilot['calls_to']
    held = []
    for r in open_rows:
        if in_pilot(r, pilot):
            r['pilot_arm'] = pilot_arm(r['key'], pilot)
            if active and r['pilot_arm'] == 'comparison' and 'outcome' not in r:
                held.append(r)
    held_ids = {id(r) for r in held}
    done = [r for r in open_rows if r.get('outcome', {}).get('status') in DONE]
    done_ids = {id(r) for r in done}
    eligible = [r for r in open_rows if r['days_since'] <= 20 and id(r) not in done_ids and id(r) not in held_ids]
    chosen = eligible[:max(0, int(calls))]
    expected_all = sum(r['chance'] for r in open_rows)
    reached = sum(r['chance'] for r in chosen)
    return {'as_of': as_of.isoformat(), 'calls': int(calls), 'open_windows': len(open_rows),
            'eligible': len(eligible), 'expected_returns_open': round(expected_all, 1),
            'expected_returns_reached': round(reached, 1),
            'share_reached': round(reached / expected_all, 3) if expected_all else None,
            'reserve_hours': None,  # No verified job-duration estimate is available.
            'check_ins': chosen, 'next': eligible[len(chosen):len(chosen) + 5], 'done': done,
            'outcomes': outcome_summary(saved), 'choices': OUTCOME_CHOICES,
            'pilot': {'id': pilot['id'], 'active': active, 'calls_from': pilot['calls_from'], 'calls_to': pilot['calls_to'],
                      'held_back': len(held)} if pilot else None}


def outcome_summary(saved: dict) -> dict:
    """What staff recorded across every check-in so far (the pilot's implementation log)."""
    recs = [r for r in saved.values() if isinstance(r, dict) and r.get('kind') == 'checkin']
    counts = {k: sum(1 for r in recs if r.get('status') == k) for k in OUTCOME_CHOICES}
    reached = sum(counts[k] for k in DONE)
    mins = [r['minutes'] for r in recs if isinstance(r.get('minutes'), int)]
    return {'mean_minutes': round(sum(mins) / len(mins), 1) if mins else None,'recorded': len(recs), 'reached': reached, 'counts': counts,
            'issue_share': round((counts['issue_found'] + counts['visit_booked']) / reached, 3) if reached else None,
            'first': min((str(r.get('updated_at', ''))[:10] for r in recs), default=None)}


def record(folder, sale_id, serviced, status, note, as_of: date, minutes=None) -> tuple[str, dict]:
    """Validate a check-in outcome against the live plan and return the ledger key and change."""
    if status not in OUTCOME_CHOICES:
        raise ValueError('Choose one of the check-in outcomes')
    if not isinstance(note, str) or len(note) > 400:
        raise ValueError('Keep the note to at most 400 characters')
    if minutes not in (None, ''):
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            raise ValueError('Call minutes must be a whole number') from None
        if not 0 <= minutes <= 120:
            raise ValueError('Call minutes must be from 0 to 120')
    else:
        minutes = None
    path = Path(folder) / PREDICTORS
    export = json.loads(path.read_text(encoding='utf-8'))
    rows = validate_predictors(export)
    row = next((r for r in rows if str(r.get('sales_record_id')) == str(sale_id)
                and str(r.get('anchor_date'))[:10] == str(serviced)[:10]), None)
    if row is None:
        raise ValueError('This service is not in the current check-in plan. Refresh the page.')
    age = (as_of - date.fromisoformat(str(row['anchor_date'])[:10])).days
    if age < 0 or age >= WINDOW_DAYS:
        raise ValueError('This service is outside its 30-day window')
    m = load_model()
    key, p = checkin_key(sale_id, serviced), score(row, m)
    pilot = load_pilot() if os.environ.get('CP2_CHECKIN_PILOT_APPROVED') == 'yes' else None
    arm = pilot_arm(key, pilot) if in_pilot({'serviced': str(serviced)[:10], 'chance': p}, pilot) else None
    return key, {'pilot_arm': arm,
        'kind': 'checkin', 'sale_id': str(sale_id), 'serviced': str(serviced)[:10], 'status': status,
        'note': note.strip(), 'minutes': minutes, 'day_of_window': age, 'chance_at_save': round(p, 4),
        'model_version': 'return_risk_v1'}


REQUIRED = ('sales_record_id', 'anchor_date', 'service_number', 'package_sessions_recorded', 'premise_type',
            'sale_total_rm', 'days_since_previous_service', 'prior_property_warranty_claims',
            'prior_package_warranty_claims', 'prior_property_claims_90d', 'pest_category')
OUTCOMES = ('warranty_signal_within_30d', 'warranty_claim_count_30d')  # outcome_end_date is only anchor + 30 days


def validate_predictors(raw: dict) -> list[dict]:
    """Check a predictor export and return its rows. Outcome columns are refused."""
    cols = raw.get('columns')
    if not isinstance(cols, list) or not isinstance(raw.get('records'), list):
        raise ValueError('Predictor export must have columns and records')
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        raise ValueError('Predictor export is missing ' + ', '.join(missing))
    leaked = [c for c in OUTCOMES if c in cols]
    if leaked:
        raise ValueError('Predictor export contains outcome columns: ' + ', '.join(leaked))
    return [dict(zip(cols, r)) if isinstance(r, list) else r for r in raw['records']]


def live(folder, value: dict, as_of: date, calls: int = DEFAULT_CALLS, log: dict | None = None) -> dict:
    path = Path(folder) / PREDICTORS
    if not path.exists():
        return {'status': 'not_connected',
                'message': 'Live scoring needs the predictor export from the reporting job (return_risk_predictors.json).'}
    export = json.loads(path.read_text(encoding='utf-8'))
    rows = validate_predictors(export)
    latest = max((str(r.get('anchor_date'))[:10] for r in rows), default=None)
    pilot = load_pilot() if os.environ.get('CP2_CHECKIN_PILOT_APPROVED') == 'yes' else None
    result = plan(rows, as_of, calls, _names(value), log=log, pilot=pilot)
    result['pilot_approval_required'] = pilot is None
    captured = export.get('captured_at')
    freshness_date = datetime.fromisoformat(captured.replace('Z', '+00:00')).date() if captured else (date.fromisoformat(latest) if latest else None)
    age = (as_of - freshness_date).days if freshness_date else None
    result.update({'status': 'live', 'predictors_through': latest,
                   'captured_at': captured, 'source_release_id': export.get('source_release_id'),
                   'stale': age is None or age < 0 or age > 3})
    if result['stale']:
        result.update(status='stale', message='Service predictors need refreshing before using a check-in plan.')
    return result
