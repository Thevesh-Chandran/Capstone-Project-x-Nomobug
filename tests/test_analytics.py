from datetime import date

from webapp import analytics


def _value():
    sales = [
        {'date': '2025-02-10', 'sales_rm': 300.0, 'pest': 'Lipas dan tikus', 'premise': 'RESIDENTIAL', 'package': 'GPC3x', 'district': 'Selangor / Petaling'},
        {'date': '2026-02-10', 'sales_rm': 500.0, 'pest': 'Semut', 'premise': 'COMMERCIAL', 'package': 'Unspecified', 'district': 'Unassigned'},
        {'date': '2026-03-01', 'sales_rm': 200.0, 'pest': 'Anai-anai', 'premise': 'RESIDENTIAL', 'package': 'B2B1x', 'district': 'W.P. Kuala Lumpur / W.P. Kuala Lumpur'},
        {'date': None, 'sales_rm': 100.0, 'pest': '', 'premise': 'RESIDENTIAL', 'package': 'Unspecified', 'district': 'Unassigned'},
    ]
    appts = [{'date': '2026-02-11', 'warranty_signal': True}, {'date': '2026-02-12', 'warranty_signal': False}]
    customers = [{'repeat_customer': True}, {'repeat_customer': False}]
    return {'records': {'sales': sales, 'appointments': appts}, 'customers': customers, 'receipt': {'published_release': 'cp2r_x'}}


def test_pest_labels_are_multi_label_and_bilingual():
    assert analytics.pest_labels('Lipas, semut dan tikus') == ['Cockroach', 'Ant', 'Rodent']
    assert analytics.pest_labels('ANAI-ANAI') == ['Termite']
    assert analytics.pest_labels('') == ['Other / unspecified']


def test_descriptive_kpis_anchor_on_latest_sale_and_keep_unknown_dates_in_totals():
    d = analytics.descriptive(_value(), {'tables': {}}, date(2026, 11, 2))
    k = d['kpis']
    assert d['anchor_date'] == '2026-03-01'
    assert k['sales_rm_all'] == 1100.0 and k['sales_rows_all'] == 4
    assert k['ytd_sales_rm'] == 700.0 and k['prev_ytd_sales_rm'] == 300.0
    assert k['repeat_rate'] == 0.5
    assert {r['label'] for r in d['top_districts']} == {'Petaling', 'W.P. Kuala Lumpur'}
    assert k['warranty_rate_12m'] == 0.5


def test_prescriptive_actions_are_ranked_and_carry_links():
    value = _value()
    desc = analytics.descriptive(value, {'tables': {}}, date(2026, 11, 2))
    pred = analytics.predictive({'evidence': {'models': []}, 'live': {}}, {'customers': [], 'eligible_customers': 0}, {}, {}, desc['trend'])
    review = {'counts': {'upcoming': 1, 'missing': 0}, 'tasks': [{'review_kind': 'upcoming', 'sales_remaining_balance_rm': 250.0}]}
    out = analytics.prescriptive(desc, pred, review, {'source_stale': True, 'settings': {}})
    priorities = [a['priority'] for a in out['actions']]
    assert priorities == sorted(priorities, key={'high': 0, 'medium': 1, 'low': 2}.get)
    assert out['actions'][0]['title'].startswith('Refresh source')
    payment = next(a for a in out['actions'] if a['area'] == 'Cash flow')
    assert payment['impact'] == 250.0 and payment['link'] == '#home'


def test_score_options_ranks_by_weighted_criteria():
    opts = [
        {'id': 'a', 'expected_value_rm': 1000.0, 'confidence': 'low', 'urgency': 'low', 'effort': 'high'},
        {'id': 'b', 'expected_value_rm': 500.0, 'confidence': 'high', 'urgency': 'high', 'effort': 'low'},
    ]
    ranked = analytics.score_options(opts)
    assert [r['id'] for r in ranked] == ['b', 'a'] and ranked[0]['rank'] == 1
    value_only = analytics.score_options(opts, {'value': 1, 'confidence': 0, 'urgency': 0, 'effort': 0})
    assert value_only[0]['id'] == 'a'


def test_performance_scorecard_flags_status():
    value = _value()
    desc = analytics.descriptive(value, {'tables': {}}, date(2026, 11, 2))
    pred = analytics.predictive({'evidence': {'models': []}, 'live': {}}, {'customers': [], 'eligible_customers': 0}, {}, {}, desc['trend'])
    perf = analytics.performance(desc, pred, {'counts': {'total': 4, 'reviewed': 1, 'status': 1}})
    by = {r['metric']: r for r in perf['scorecard']}
    assert by['Sales year-to-date']['status'] == 'good'
    assert by['Follow-ups actioned']['value'] == 0.5 and by['Follow-ups actioned']['status'] == 'warn'
    assert by['Booking forecast error']['status'] == 'unknown'


def test_login_requires_username_and_password(tmp_path, monkeypatch):
    import json, threading, urllib.request, urllib.error
    from http.server import ThreadingHTTPServer
    from webapp.server import Portal, handler_for
    monkeypatch.delenv('CP2_PORTAL_TOKEN', raising=False)
    monkeypatch.setenv('CP2_AUTH_MODE', 'staff_code')
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(Portal(tmp_path)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        with __import__('pytest').raises(urllib.error.HTTPError) as unauth:
            urllib.request.urlopen(base + '/api/state')
        assert unauth.value.code == 401

        def login(user, pw):
            req = urllib.request.Request(base + '/api/login', data=json.dumps({'username': user, 'password': pw}).encode(),
                                         headers={'Content-Type': 'application/json', 'Origin': base}, method='POST')
            return urllib.request.urlopen(req)
        with __import__('pytest').raises(urllib.error.HTTPError) as bad:
            login('admin', 'wrong')
        assert bad.value.code == 401
        with login('admin', 'admin') as ok:
            assert ok.status == 200 and 'cp2_session=' in ok.headers['Set-Cookie']
    finally:
        server.shutdown()
