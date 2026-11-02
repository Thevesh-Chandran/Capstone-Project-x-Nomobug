import http.client
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading


def load_proxy():
    spec = importlib.util.spec_from_file_location('cp2_metabase_proxy', Path(__file__).parents[1] / 'infra/metabase/proxy.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_proxy_preserves_body_cookies_and_forwards_write_once():
    writes = []

    class App(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'ok' if self.path == '/api/health' else b'dashboard'
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Set-Cookie', 'fixture=1; HttpOnly')
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            writes.append((self.path, body, self.headers.get('Cookie')))
            self.send_response(201)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    app = ThreadingHTTPServer(('127.0.0.1', 0), App)
    module = load_proxy()
    module.APP_PORT = app.server_port
    proxy = ThreadingHTTPServer(('127.0.0.1', 0), module.Handler)
    for server in (app, proxy):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection('127.0.0.1', proxy.server_port, timeout=5)
        conn.request('GET', '/')
        response = conn.getresponse()
        assert response.status == 200
        assert response.getheader('Set-Cookie') == 'fixture=1; HttpOnly'
        assert response.read() == b'dashboard'
        conn.close()
        conn = http.client.HTTPConnection('127.0.0.1', proxy.server_port, timeout=5)
        conn.request('POST', '/api/fixture', body=b'hello', headers={'Cookie': 'session=fixture'})
        response = conn.getresponse()
        assert response.status == 201 and response.read() == b'hello'
        assert writes == [('/api/fixture', b'hello', 'session=fixture')]
        conn.close()
    finally:
        proxy.shutdown()
        proxy.server_close()
        app.shutdown()
        app.server_close()


def test_health_never_reports_ready_before_upstream():
    module = load_proxy()
    module.app_ready = lambda: False
    proxy = ThreadingHTTPServer(('127.0.0.1', 0), module.Handler)
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection('127.0.0.1', proxy.server_port, timeout=5)
        conn.request('GET', '/cp2-health')
        response = conn.getresponse()
        assert response.status == 503
        assert response.getheader('Retry-After') == '10'
        response.read()
        conn.close()
    finally:
        proxy.shutdown()
        proxy.server_close()
