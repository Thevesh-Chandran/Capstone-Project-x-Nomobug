from webapp import server


def test_google_calendar_embed_is_off_until_configured(monkeypatch):
    monkeypatch.delenv('CP2_GOOGLE_CALENDAR_IDS', raising=False)
    assert server.google_calendar_url() is None


def test_google_calendar_embed_keeps_only_valid_calendar_ids(monkeypatch):
    monkeypatch.setenv('CP2_GOOGLE_CALENDAR_IDS', 'team.ace@group.calendar.google.com, bad id ,"><script>@x')
    url = server.google_calendar_url()
    assert url.startswith('https://calendar.google.com/calendar/embed?')
    assert url.count('&src=') == 1 and 'team.ace%40group.calendar.google.com' in url
    assert '<' not in url and ' ' not in url


def test_sales_pest_spellings_group_into_standard_categories():
    from webapp.business import pest_group
    assert pest_group('LIPAS') == pest_group('Lipas') == 'Cockroach'
    assert pest_group('Lipas, semut dan tikus') == pest_group('Lipas semut dan tikus') == 'Cockroach + Ant + Rodent'
    assert pest_group('') == pest_group(None) == 'Unspecified'


def test_dashboard_pest_macro_matches_website_categories():
    """The dbt macro and the website must group pest names the same way."""
    import re
    from pathlib import Path
    from webapp.analytics import PESTS
    sql = (Path(__file__).resolve().parents[1] / 'dbt/macros/pest_group.sql').read_text()
    found = re.findall(r"struct\('([^']+)' as label, regexp_contains\(upper\(\{\{ expr \}\}\), r'\\b\(([^)]+)\)'\)", sql)
    assert [(name, tuple(keys.split('|'))) for name, keys in found] == [(n, tuple(k)) for n, k in PESTS]


def test_customer_filters_and_summary(tmp_path, monkeypatch):
    """Relationship filter, order and summary on the customer search."""
    import json, threading, urllib.error, urllib.request
    from http.server import ThreadingHTTPServer
    monkeypatch.setenv('CP2_PORTAL_TOKEN', 'test-staff-access-code-long-enough')
    customers = [
        {'name': 'Alpha', 'identity_status': 'exact_name_and_phone', 'sales_rm': 900.0, 'purchase_count': 2,
         'repeat_customer': True, 'sales': [{'sale_id': 'S1'}]},
        {'name': 'Beta', 'identity_status': 'needs_review', 'sales_rm': 100.0, 'purchase_count': 1,
         'repeat_customer': False, 'sales': [{'sale_id': 'S2'}]},
        {'name': 'Cara', 'identity_status': 'exact_name_and_phone', 'sales_rm': 500.0, 'purchase_count': 1,
         'repeat_customer': False, 'sales': [{'sale_id': 'S3'}]},
    ]
    (tmp_path / 'business_tools_private.json').write_text(json.dumps({'receipt': {}, 'records': {}, 'customers': customers}))
    portal = server.Portal(tmp_path)
    srv = ThreadingHTTPServer(('127.0.0.1', 0), server.handler_for(portal))
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:' + str(srv.server_port)
    cookie = 'cp2_session=' + portal.session()

    def search(body):
        req = urllib.request.Request(base + '/api/customers', data=json.dumps(body).encode(),
                                     headers={'Origin': base, 'Cookie': cookie}, method='POST')
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, None
    try:
        code, r = search({'q': '', 'relationship': 'repeat'})
        assert code == 200 and [c['name'] for c in r['customers']] == ['Alpha'] and r['summary']['repeat'] == 1
        code, r = search({'q': '', 'sort': 'name'})
        assert [c['name'] for c in r['customers']] == ['Alpha', 'Beta', 'Cara']
        assert r['summary'] == {'groups': 3, 'sales_rm': 1500.0, 'repeat': 1, 'needs_review': 1}
        code, r = search({'q': '', 'relationship': 'review'})
        assert [c['name'] for c in r['customers']] == ['Beta']
        assert search({'q': '', 'relationship': 'bogus'})[0] == 400
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join()
