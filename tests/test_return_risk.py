import json
import math
from datetime import date

import pytest

from webapp import return_risk as rr


def _row(sale, served, service=3, sessions=3, premise='RESIDENTIAL', pest='Lipas', **kw):
    base = {'sales_record_id': sale, 'anchor_date': served, 'service_number': service,
            'package_sessions_recorded': sessions, 'premise_type': premise, 'sale_total_rm': 490,
            'days_since_previous_service': 30, 'prior_property_warranty_claims': 0,
            'prior_package_warranty_claims': 0, 'prior_property_claims_90d': 0, 'pest_category': pest}
    base.update(kw)
    return base


def test_model_file_matches_feature_list():
    m = rr.load_model()
    assert set(m['features']) == set(rr.features(_row('A', '2026-10-01')))
    assert len(m['coef']) == len(m['scaler_mean']) == len(m['scaler_scale']) == 13


def test_score_is_the_logistic_of_the_standardised_sum():
    m = rr.load_model()
    row = _row('A', '2026-10-01')
    f = rr.features(row)
    z = m['intercept'] + sum(c * (f[n] - mu) / s for n, mu, s, c in zip(m['features'], m['scaler_mean'], m['scaler_scale'], m['coef']))
    assert rr.score(row, m) == pytest.approx(1 / (1 + math.exp(-z)), abs=1e-12)


def test_risk_follows_the_documented_direction():
    m = rr.load_model()
    final_home = rr.score(_row('A', '2026-10-01'), m)
    first_commercial = rr.score(_row('B', '2026-10-01', service=1, premise='COMMERCIAL', pest='Tikus'), m)
    recent_return = rr.score(_row('C', '2026-10-01', prior_property_claims_90d=1), m)
    assert first_commercial < final_home < recent_return
    assert 0 < first_commercial < 0.05 and 0.1 < final_home < 0.5


def test_missing_gap_and_text_values_are_handled_like_the_study():
    f = rr.features(_row('A', '2026-10-01', days_since_previous_service=None, sale_total_rm='190', pest_category='Lipas dan tikus'))
    assert f['gap_missing'] == 1.0 and f['gap_days_capped'] == 0.0
    assert f['log_sale_rm'] == pytest.approx(math.log1p(190))
    assert f['includes_rodent'] == 1.0 and f['cockroach_only'] == 0.0


def test_plan_ranks_open_windows_and_respects_capacity():
    rows = [_row('HIGH', '2026-10-25', prior_property_claims_90d=2),
            _row('MID', '2026-10-28'),
            _row('LOW', '2026-10-28', service=1, premise='COMMERCIAL'),
            _row('LATE', '2026-10-05'),          # day 29: still open, past the check-in window
            _row('CLOSED', '2026-09-20')]        # window already closed
    out = rr.plan(rows, date(2026, 11, 3), calls=2, names={'HIGH': 'Customer H'})
    assert [c['sale_id'] for c in out['check_ins']] == ['HIGH', 'MID']
    assert out['check_ins'][0]['name'] == 'Customer H'
    assert out['open_windows'] == 4 and out['eligible'] == 3
    assert out['check_ins'][1]['call_on'] == '2026-11-07'      # never before day 10
    assert out['check_ins'][0]['call_on'] == '2026-11-04'
    assert 'recent return at this address' in out['check_ins'][0]['why']
    assert out['expected_returns_reached'] <= out['expected_returns_open']


def test_validate_refuses_outcome_columns():
    cols = list(rr.REQUIRED)
    rows = rr.validate_predictors({'columns': cols, 'records': [[None] * len(cols)]})
    assert len(rows) == 1
    with pytest.raises(ValueError):
        rr.validate_predictors({'columns': cols + ['warranty_signal_within_30d'], 'records': []})
    with pytest.raises(ValueError):
        rr.validate_predictors({'columns': cols[1:], 'records': []})


def test_live_reports_not_connected_without_predictors(tmp_path):
    assert rr.live(tmp_path, {'customers': []}, date(2026, 11, 3))['status'] == 'not_connected'


def test_live_scores_a_published_export(tmp_path):
    cols = list(rr.REQUIRED)
    rec = _row('S1', '2026-10-31')
    (tmp_path / rr.PREDICTORS).write_text(json.dumps({'columns': cols, 'records': [[rec[c] for c in cols]]}))
    value = {'customers': [{'name': 'Aisyah', 'sales': [{'sale_id': 'S1'}]}]}
    out = rr.live(tmp_path, value, date(2026, 11, 3), calls=5)
    assert out['status'] == 'live' and out['predictors_through'] == '2026-10-31' and not out['stale']
    assert out['check_ins'][0]['name'] == 'Aisyah'


def test_reached_customers_leave_the_plan_and_no_answer_stays():
    rows = [_row('HIGH', '2026-10-25', prior_property_claims_90d=2), _row('MID', '2026-10-28'), _row('THIRD', '2026-10-27')]
    k_high, k_mid = rr.checkin_key('HIGH', '2026-10-25'), rr.checkin_key('MID', '2026-10-28')
    log = {'records': {k_high: {'kind': 'checkin', 'status': 'visit_booked', 'note': 'ants back', 'updated_at': '2026-11-03T02:00:00+00:00'},
                       k_mid: {'kind': 'checkin', 'status': 'no_answer', 'note': '', 'updated_at': '2026-11-03T03:00:00+00:00'},
                       'capacity:2026-11-02': {'capacity_hours': 40}}}
    out = rr.plan(rows, date(2026, 11, 3), calls=2, log=log)
    assert [c['sale_id'] for c in out['done']] == ['HIGH']
    assert 'HIGH' not in [c['sale_id'] for c in out['check_ins']]
    mid = next(c for c in out['check_ins'] if c['sale_id'] == 'MID')
    assert mid['outcome']['status'] == 'no_answer'
    assert out['outcomes'] == {'recorded': 2, 'reached': 1, 'counts': {'no_issue': 0, 'issue_found': 0, 'visit_booked': 1, 'no_answer': 1},
                               'issue_share': 1.0, 'first': '2026-11-03', 'mean_minutes': None}


def test_checkin_key_is_a_ledger_safe_hash():
    key = rr.checkin_key('S-1', '2026-10-25T00:00:00')
    assert len(key) == 64 and key == rr.checkin_key('S-1', '2026-10-25') and 'S-1' not in key


def test_record_validates_against_the_open_plan(tmp_path):
    (tmp_path / rr.PREDICTORS).write_text(json.dumps({'columns': list(_row('A', 'x')), 'records': [
        list(_row('OPEN', '2026-10-25').values()), list(_row('OLD', '2026-09-01').values())]}))
    key, change = rr.record(tmp_path, 'OPEN', '2026-10-25', 'issue_found', ' advice given ', date(2026, 11, 3))
    assert key == rr.checkin_key('OPEN', '2026-10-25')
    assert change['kind'] == 'checkin' and change['note'] == 'advice given' and change['day_of_window'] == 9
    assert 0 < change['chance_at_save'] < 1 and change['model_version']
    for args in [('OPEN', '2026-10-25', 'emailed', ''), ('OLD', '2026-09-01', 'no_issue', ''),
                 ('NOPE', '2026-10-25', 'no_issue', ''), ('OPEN', '2026-10-25', 'no_issue', 'x' * 401)]:
        with pytest.raises(ValueError):
            rr.record(tmp_path, *args, date(2026, 11, 3))


def test_publish_keeps_only_model_inputs(tmp_path):
    from scripts import publish_return_risk_predictors as pub
    cols = list(_row('A', 'x')) + ['warranty_signal_within_30d', 'property_address', 'latitude']
    raw = {'columns': cols, 'records': [list(_row('A', '2026-10-25').values()) + [1, 'No 1 Jalan X', 3.1]]}
    out = pub.prepare(raw)
    assert out['columns'] == list(rr.REQUIRED)
    assert pub.write(out, local=tmp_path) == 1
    assert rr.validate_predictors(json.loads((tmp_path / rr.PREDICTORS).read_text()))[0]['sales_record_id'] == 'A'


PILOT = {'id': 'p', 'salt': 'p', 'calls_from': '2026-11-10', 'calls_to': '2026-11-23',
         'served_from': '2026-10-26', 'served_to': '2026-11-13', 'threshold': 0.12}


def test_pilot_arms_are_fixed_and_balanced():
    keys = [rr.checkin_key(f'S{i}', '2026-11-01') for i in range(400)]
    arms = [rr.pilot_arm(k, PILOT) for k in keys]
    assert arms == [rr.pilot_arm(k, PILOT) for k in keys]
    assert 160 < arms.count('call') < 240


def test_pilot_holds_back_only_high_risk_comparison_services_while_active():
    rows = [_row(f'H{i}', '2026-11-02') for i in range(20)] + [_row(f'L{i}', '2026-11-02', service=1, premise='COMMERCIAL') for i in range(5)]
    during = rr.plan(rows, date(2026, 11, 12), calls=40, pilot=PILOT)
    before = rr.plan(rows, date(2026, 11, 9), calls=40, pilot=PILOT)
    held = during['pilot']['held_back']
    assert during['pilot']['active'] and not before['pilot']['active'] and before['pilot']['held_back'] == 0
    assert 0 < held < 20 and len(during['check_ins']) == 25 - held
    assert all(c['pilot_arm'] == 'call' for c in during['check_ins'] if c['sale_id'].startswith('H'))
    assert all('pilot_arm' not in c for c in during['check_ins'] if c['sale_id'].startswith('L'))


def test_record_keeps_call_minutes_and_rejects_bad_values(tmp_path, monkeypatch):
    monkeypatch.setenv("CP2_CHECKIN_PILOT_APPROVED", "yes")
    (tmp_path / rr.PREDICTORS).write_text(json.dumps({'columns': list(_row('A', 'x')), 'records': [list(_row('OPEN', '2026-11-02').values())]}))
    _, change = rr.record(tmp_path, 'OPEN', '2026-11-02', 'no_issue', '', date(2026, 11, 12), minutes='4')
    assert change['minutes'] == 4 and change['pilot_arm'] in ('call', 'comparison')
    with pytest.raises(ValueError):
        rr.record(tmp_path, 'OPEN', '2026-11-02', 'no_issue', '', date(2026, 11, 12), minutes=500)


def test_pilot_evaluation_separates_staff_booked_returns():
    from scripts import evaluate_checkin_pilot as ev
    pilot = rr.load_pilot()
    rows = [_row(f'H{i}', '2026-11-02', warranty_signal_within_30d=1 if i < 6 else 0) for i in range(30)]
    keys = {r['sales_record_id']: rr.checkin_key(r['sales_record_id'], '2026-11-02') for r in rows}
    call = [s for s, k in keys.items() if rr.pilot_arm(k, pilot) == 'call']
    ledger = {'records': {keys[s]: {'kind': 'checkin', 'status': 'visit_booked', 'pilot_arm': 'call',
                                    'updated_at': '2026-11-12T01:00:00+00:00', 'minutes': 5} for s in call}}
    out = ev.outcomes(rows, ledger, pilot, date(2026, 12, 14))
    assert out['complete'] and out['call']['services'] + out['comparison']['services'] == 30
    assert out['call']['customer_initiated_return'] == 0
    assert out['call']['staff_booked_return'] == sum(1 for s in call if int(s[1:]) < 6)
    assert ev.process(ledger, pilot)['call']['visit_booked'] == len(call)
    assert ev.outcomes(rows, ledger, pilot, date(2026, 12, 1))['complete'] is False


def test_live_does_not_hide_comparison_customers_without_owner_agreement(tmp_path, monkeypatch):
    monkeypatch.delenv('CP2_CHECKIN_PILOT_APPROVED', raising=False)
    rows = [_row(f'H{i}', '2026-11-02') for i in range(20)]
    (tmp_path / rr.PREDICTORS).write_text(json.dumps({'columns': list(rows[0]), 'records': rows}))
    result = rr.live(tmp_path, {}, date(2026, 11, 12), calls=40)
    assert result['pilot'] is None and result['pilot_approval_required']
    assert len(result['check_ins']) == 20


def test_live_freshness_uses_source_capture_on_quiet_service_days(tmp_path):
    rows = [_row('H1', '2026-11-02')]
    export = {'columns': list(rows[0]), 'records': rows,
              'captured_at': '2026-11-12T00:00:00+00:00', 'source_release_id': 'example'}
    (tmp_path / rr.PREDICTORS).write_text(json.dumps(export))
    assert rr.live(tmp_path, {}, date(2026, 11, 12))['status'] == 'live'
    assert rr.live(tmp_path, {}, date(2026, 11, 16))['status'] == 'stale'
