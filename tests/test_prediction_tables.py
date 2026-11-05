from datetime import date

from scripts import publish_prediction_tables as p
from webapp import return_risk


def row(sale, served, n=3, total=3, premise='RESIDENTIAL'):
    return {'sales_record_id': sale, 'anchor_date': served, 'service_number': n, 'package_sessions_recorded': total,
            'premise_type': premise, 'pest_category': 'Lipas', 'sale_total_rm': 400, 'days_since_previous_service': 30,
            'prior_package_warranty_claims': 0, 'prior_property_claims_90d': 0, 'prior_property_warranty_claims': 0}


def predictors(rows):
    cols = sorted(rows[0])
    return {'columns': cols, 'records': [[r[c] for c in cols] for r in rows]}


def test_scores_match_the_portal_and_only_open_windows_are_kept():
    rows = [row('A', '2026-11-01'), row('B', '2026-10-01'), row('C', '2026-11-10'), row('D', '2026-10-10', 1, 3, 'COMMERCIAL')]
    out = p.risk_rows(predictors(rows), date(2026, 11, 5))
    ids = [r['sales_record_id'] for r in out]
    assert set(ids) == {'A', 'D'}  # B is past day 30, C is in the future
    model = return_risk.load_model()
    for r in out:
        src = next(x for x in rows if x['sales_record_id'] == r['sales_record_id'])
        assert abs(r['chance_of_return'] - round(return_risk.score(return_risk.validate_predictors(predictors([src]))[0], model), 4)) < 1e-9
    assert [r['risk_rank'] for r in out] == [1, 2]
    assert out[0]['chance_of_return'] >= out[1]['chance_of_return']
    d = next(r for r in out if r['sales_record_id'] == 'D')
    assert d['days_since_service'] == 26 and d['suggested_action'] == 'Past the call window'


def test_forecast_range_uses_historical_error_and_staffing_plan_is_derived():
    forecast = {'latest': {'issued_at': '2026-11-01T15:51:10+00:00', 'origin': '2026-11-02T00:00:00+08:00'},
                'forecasts': [{'id': 'booking_entries_h2', 'prediction': 228.0, 'baseline': 223.5, 'already_booked': 140,
                               'window_end': '2026-11-16T00:00:00+08:00'},
                              {'id': 'booked_hours_h1', 'prediction': 120.0, 'baseline': 130, 'already_booked': 88,
                               'window_end': '2026-11-09T00:00:00+08:00'}]}
    t = p.build(None, forecast, date(2026, 11, 5))
    b = next(r for r in t['booking_forecast'] if r['forecast_id'] == 'booking_entries_h2')
    assert b['likely_low'] < 228 < b['likely_high'] and b['period_start'] == '2026-11-02'
    s = t['staffing_plan'][0]
    assert s['hours_to_keep_open'] == 32.0 and s['suggested_staff_hours'] == round(120 + s['buffer_hours'], 1)
    assert t['forecast_backtest'] and 'return_risk_scores' not in t
