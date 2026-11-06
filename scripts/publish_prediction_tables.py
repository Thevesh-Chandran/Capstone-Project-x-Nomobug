"""Model results as BigQuery tables for the Looker Studio dashboard.

Reads the files the daily jobs already publish for the portal (return_risk_predictors.json
and planning_forecast.json in the portal bucket) and replaces four tables in the
`predictions` dataset. The models are not changed or refitted; this only copies their
current answers to where Looker can read them.

  return_risk_scores   every service whose 30-day window is open: chance of a return,
                       reasons, when to call, and a suggested action (prescriptive)
  booking_forecast     next-period forecasts with a likely range (predictive)
  forecast_backtest    past forecast vs actual, for a "how accurate was it" chart
  staffing_plan        next week's appointment hours and hours to keep open (prescriptive)

  python scripts/publish_prediction_tables.py --uri gs://<portal bucket>/current
  python scripts/publish_prediction_tables.py --folder <local runtime folder> --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webapp import return_risk  # noqa: E402

PROJECT = 'profound-keel-500007-s4'
DATASET = 'predictions'
LOCATION = 'asia-southeast1'
CALL_LIST_SIZE = 10  # matches the portal's default weekly plan
PLANNING = ROOT / 'webapp/models/planning_v1.json'
RETURN_RISK = ROOT / 'webapp/models/return_risk_v1.json'


def risk_rows(predictors: dict, as_of: date) -> list[dict]:
    model = return_risk.load_model()
    rows = return_risk.validate_predictors(predictors)
    out = []
    for r in rows:
        served = date.fromisoformat(str(r['anchor_date'])[:10])
        age = (as_of - served).days
        if age < 0 or age >= return_risk.WINDOW_DAYS:
            continue
        reasons = return_risk.reasons(r, model)
        out.append({
            'as_of': as_of.isoformat(), 'sales_record_id': r.get('sales_record_id'),
            'service_date': served.isoformat(), 'days_since_service': age,
            'call_from': (served + timedelta(days=return_risk.CHECK_IN_DAY)).isoformat(),
            'window_ends': (served + timedelta(days=return_risk.WINDOW_DAYS)).isoformat(),
            'chance_of_return': round(return_risk.score(r, model), 4),
            'reason_1': reasons[0] if reasons else None, 'reason_2': reasons[1] if len(reasons) > 1 else None,
            'service_number': int(return_risk._num(r.get('service_number'))),
            'programme_services': int(return_risk._num(r.get('package_sessions_recorded'))),
            'premise_type': (r.get('premise_type') or '').title() or None,
            'pest_category': r.get('pest_category') or None,
            'model_version': 'return_risk_v1',
        })
    out.sort(key=lambda x: -x['chance_of_return'])
    callable_rank = 0
    for i, x in enumerate(out, 1):
        x['risk_rank'] = i
        open_for_call = x['days_since_service'] <= 20
        if open_for_call:
            callable_rank += 1
        x['suggested_action'] = ('Call this week' if open_for_call and callable_rank <= CALL_LIST_SIZE
                                 else 'Call if time allows' if open_for_call else 'Past the call window')
    return out


def forecast_rows(forecast: dict, models: dict) -> tuple[list[dict], list[dict], list[dict]]:
    issued = forecast.get('latest', {}).get('issued_at')
    origin = str(forecast.get('latest', {}).get('origin', ''))[:10] or None
    fc, plan = [], []
    for f in forecast.get('forecasts', []):
        m = models.get(f['id'], {})
        mae = m.get('mae')
        pred = f.get('prediction')
        fc.append({'forecast_id': f['id'], 'title': (m.get('title') or f['id']).replace('—', '-').replace('�', '-'),
                   'unit': m.get('unit'), 'issued_at': issued, 'period_start': origin,
                   'period_end': str(f.get('window_end', ''))[:10] or None,
                   'prediction': round(pred, 1) if pred is not None else None,
                   'likely_low': round(pred - mae, 1) if pred is not None and mae else None,
                   'likely_high': round(pred + mae, 1) if pred is not None and mae else None,
                   'simple_average': f.get('baseline'), 'already_booked': f.get('already_booked'),
                   'typical_error': round(mae, 1) if mae else None,
                   'simple_average_typical_error': round(m['baseline_mae'], 1) if m.get('baseline_mae') else None})
        if f['id'] == 'booked_hours_h1' and pred is not None:
            booked = f.get('already_booked') or 0
            buffer = round(mae or 0, 1)
            plan.append({'week_start': origin, 'week_end': str(f.get('window_end', ''))[:10] or None,
                         'expected_hours': round(pred, 1), 'already_booked_hours': booked,
                         'hours_to_keep_open': round(max(0, pred - booked), 1), 'buffer_hours': buffer,
                         'suggested_staff_hours': round(pred + buffer, 1),
                         'suggested_action': f'Staff about {round(pred + buffer)} hours; keep {round(max(0, pred - booked))} hours open for new bookings.'})
    backtest = [{'forecast_id': m['id'], 'title': (m.get('title') or m['id']).replace('�', '-').replace('—', '-'),
                 'period_start': h['origin'], 'actual': h['actual'], 'model_forecast': round(h['selected'], 1),
                 'simple_average': h.get('baseline')}
                for m in models.values() for h in m.get('history', [])]
    return fc, backtest, plan


def evaluation_rows(path: Path = RETURN_RISK) -> list[dict]:
    """The frozen return-visit score's one-time test result, one row per method compared."""
    if not path.exists():
        return []
    ev = json.loads(path.read_text(encoding='utf-8')).get('evaluation') or {}
    cal = ev.get('calibration') or []
    expected = sum(b['services'] * b['predicted'] for b in cal) if cal else None
    actual = sum(b['services'] * b['actual'] for b in cal) if cal else None
    lo, hi = (ev.get('auc_ci') or [None, None])[:2]
    rows = []
    for method, m in (ev.get('compare') or {}).items():
        rows.append({
            'method': method, 'chosen': method.endswith('(chosen)'),
            'test_period': ev.get('period'), 'services': ev.get('services'), 'returns': ev.get('returns'),
            'auc': m.get('auc'), 'ap': m.get('ap'), 'capture_10': m.get('capture_10'), 'capture_20': m.get('capture_20'), 'capture_30': m.get('capture_30'),
            'precision_10': m.get('precision_10'), 'precision_20': m.get('precision_20'), 'precision_30': m.get('precision_30'),
            'base_rate': (ev.get('base_rates') or {}).get('all_services'),
            'gain_vs_rule_low': (ev.get('gain_vs_rule_capture20_ci') or [None, None, None])[0],
            'gain_vs_rule': (ev.get('gain_vs_rule_capture20_ci') or [None, None, None])[1],
            'gain_vs_rule_high': (ev.get('gain_vs_rule_capture20_ci') or [None, None, None])[2],
            'auc_low': lo, 'auc_high': hi,
            'expected_returns': expected, 'recorded_returns': actual,
        })
    return rows


INPUT_LABELS = {
    'final_residential': 'Final service of a home programme', 'final_service': 'Final service of any programme',
    'residential': 'Home (residential) premise', 'three_service_programme': 'Three-service programme',
    'first_service': 'First service of a programme', 'property_past_claims': 'Earlier returns at this address',
    'programme_past_claims': 'Earlier returns in this programme', 'property_claims_90d': 'Returns at this address, last 90 days',
    'gap_missing': 'No earlier service to measure the gap', 'gap_days_capped': 'Days since the last service (per day)',
    'log_sale_rm': 'Package price (per doubling)', 'cockroach_only': 'Cockroach-only treatment', 'includes_rodent': 'Treatment includes rodents',
}


def input_rows(path: Path = RETURN_RISK) -> list[dict]:
    """The chosen model's inputs and how each changes the odds of a recorded return visit."""
    if not path.exists():
        return []
    import math
    d = json.loads(path.read_text(encoding='utf-8'))
    rows = []
    for name, log_odds in (d.get('per_unit_log_odds') or {}).items():
        rows.append({'input': name, 'label': INPUT_LABELS.get(name, name.replace('_', ' ')),
                     'log_odds': log_odds, 'odds_multiplier': math.exp(log_odds),
                     'direction': 'raises' if log_odds > 0 else 'lowers'})
    return sorted(rows, key=lambda r: -abs(r['log_odds']))


def build(predictors: dict | None, forecast: dict | None, as_of: date) -> dict[str, list[dict]]:
    models = {m['id']: m for m in json.loads(PLANNING.read_text(encoding='utf-8'))['models']}
    tables = {'return_risk_scores': risk_rows(predictors, as_of) if predictors else None,
              'model_evaluation': evaluation_rows() or None,
              'model_inputs': input_rows() or None}
    if forecast:
        tables['booking_forecast'], tables['forecast_backtest'], tables['staffing_plan'] = forecast_rows(forecast, models)
    return {k: v for k, v in tables.items() if v is not None}


def read_inputs(uri: str | None, folder: str | None) -> tuple[dict | None, dict | None]:
    names = ('return_risk_predictors.json', 'planning_forecast.json')
    if folder:
        return tuple(json.loads((Path(folder) / n).read_text(encoding='utf-8')) if (Path(folder) / n).exists() else None
                     for n in names)
    from google.cloud import storage
    bucket, _, prefix = uri.removeprefix('gs://').partition('/')
    b = storage.Client(project=PROJECT).bucket(bucket)
    out = []
    for n in names:
        blob = b.blob(f'{prefix.rstrip("/")}/{n}' if prefix else n)
        out.append(json.loads(blob.download_as_text()) if blob.exists() else None)
    return tuple(out)


CALL_LIST_VIEW = f"""
create or replace view `{PROJECT}.{DATASET}.return_risk_call_list` as
select r.*, s.customer_name
from `{PROJECT}.{DATASET}.return_risk_scores` r
left join (select sales_record_id, any_value(nullif(trim(customer_name_raw), '')) as customer_name
           from `{PROJECT}.silver.sales` where sales_record_id is not null group by 1) s
using (sales_record_id)
"""


P = f'`{PROJECT}.{DATASET}'
ACCURACY_VIEW = f"""
create or replace view {P}.booking_forecast_accuracy` as
select date(period_start) as period_start, actual as actual_bookings, model_forecast as model_forecast_bookings,
       simple_average as simple_average_bookings
from {P}.forecast_backtest` where forecast_id = 'booking_entries_h2'
"""
HEADLINE_VIEW = f"""
create or replace view {P}.headline` as select
  (select round(sum(chance_of_return), 1) from {P}.return_risk_scores`) as expected_returns_open,
  (select countif(suggested_action = 'Call this week') from {P}.return_risk_scores`) as customers_to_call,
  (select count(*) from {P}.return_risk_scores`) as services_open,
  (select max(chance_of_return) from {P}.return_risk_scores`) as top_chance,
  (select round(prediction) from {P}.booking_forecast` where forecast_id = 'booking_entries_h2') as bookings_next_2_weeks,
  (select concat(cast(round(likely_low) as string), ' to ', cast(round(likely_high) as string))
     from {P}.booking_forecast` where forecast_id = 'booking_entries_h2') as bookings_likely_range,
  (select round(suggested_staff_hours) from {P}.staffing_plan` limit 1) as staff_hours_next_week,
  (select round(hours_to_keep_open) from {P}.staffing_plan` limit 1) as hours_to_keep_open,
  (select max(as_of) from {P}.return_risk_scores`) as as_of
"""


def load(tables: dict[str, list[dict]], client=None) -> dict:
    from google.cloud import bigquery
    client = client or bigquery.Client(project=PROJECT, location=LOCATION)
    ds = bigquery.Dataset(f'{PROJECT}.{DATASET}'); ds.location = LOCATION
    ds.description = 'Current model results for the Looker Studio dashboard. Replaced daily; estimates, not facts.'
    client.create_dataset(ds, exists_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    counts = {}
    for name, rows in tables.items():
        for r in rows:
            r['loaded_at'] = stamp
        cfg = bigquery.LoadJobConfig(write_disposition='WRITE_TRUNCATE', autodetect=True,
                                     source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON)
        if rows:
            client.load_table_from_json(rows, f'{PROJECT}.{DATASET}.{name}', job_config=cfg).result()
        counts[name] = len(rows)
    if 'return_risk_scores' in tables and tables['return_risk_scores']:
        client.query(CALL_LIST_VIEW).result()
    if {'return_risk_scores', 'booking_forecast', 'staffing_plan'} <= set(tables):
        for sql in (ACCURACY_VIEW, HEADLINE_VIEW):
            client.query(sql).result()
    return {'status': 'PUBLISHED', 'dataset': DATASET, 'rows': counts, 'loaded_at': stamp}


def from_uri(uri: str, client=None, as_of: date | None = None) -> dict:
    """Daily reporting step. Reads the portal files and replaces the prediction tables."""
    predictors, forecast = read_inputs(uri, None)
    return load(build(predictors, forecast, as_of or datetime.now(timezone(timedelta(hours=8))).date()), client)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--uri'); g.add_argument('--folder')
    p.add_argument('--as-of', help='YYYY-MM-DD, default today in Malaysia')
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    as_of = date.fromisoformat(a.as_of) if a.as_of else datetime.now(timezone(timedelta(hours=8))).date()
    tables = build(*read_inputs(a.uri, a.folder), as_of)
    if a.dry_run:
        print(json.dumps({k: {'rows': len(v), 'first': v[0] if v else None} for k, v in tables.items()}, indent=1, default=str))
        return
    print(json.dumps(load(tables), indent=1))


if __name__ == '__main__':
    main()
