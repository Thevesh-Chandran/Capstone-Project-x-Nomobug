"""Open Vercel's port while the JVM initializes; never claim early readiness."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import signal
import subprocess
import threading
import time
import json
from pathlib import Path

HOP = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
       'te', 'trailer', 'transfer-encoding', 'upgrade', 'content-length'}
APP_PORT = int(os.environ.get('MB_JETTY_PORT', '3001'))
STARTUP_WAIT = 240
child = None


def resource_status(pid):
    """Read only resource counters, never environment variables or command lines."""
    status = {}
    for name in ('memory.current', 'memory.max', 'memory.events'):
        try:
            status[name] = (Path('/sys/fs/cgroup') / name).read_text().strip()
        except OSError:
            pass
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith(('VmRSS:', 'VmPeak:', 'Threads:')):
                key, value = line.split(':', 1)
                status[key] = value.strip()
    except OSError:
        pass
    return status


def app_ready():
    conn = http.client.HTTPConnection('127.0.0.1', APP_PORT, timeout=2)
    try:
        conn.request('GET', '/api/health')
        response = conn.getresponse()
        response.read()
        return response.status == 200
    except (OSError, http.client.HTTPException):
        return False
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_):
        pass  # Never log user URLs, cookies, passwords or request bodies.

    def unavailable(self):
        body = b'Metabase is starting or temporarily unavailable. Please retry shortly.'
        self.send_response(503)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Retry-After', '10')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def proxy(self):
        if self.path == '/cp2-health':
            if not app_ready():
                return self.unavailable()
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(b'ok')
            return
        deadline = time.monotonic() + STARTUP_WAIT
        while not app_ready():
            if (child is not None and child.poll() is not None) or time.monotonic() >= deadline:
                return self.unavailable()
            time.sleep(0.5)
        # Forward each actual request once, only after readiness. Never retry writes.
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 4_500_000 or self.headers.get('Transfer-Encoding'):
                self.send_error(413)
                return
        except ValueError:
            self.send_error(400)
            return
        payload = self.rfile.read(length) if length else None
        blocked = HOP | {s.strip().lower() for s in self.headers.get('Connection', '').split(',')}
        headers = {k: v for k, v in self.headers.items() if k.lower() not in blocked}
        conn = http.client.HTTPConnection('127.0.0.1', APP_PORT, timeout=250)
        started = False
        try:
            conn.request(self.command, self.path, body=payload, headers=headers)
            response = conn.getresponse()
            self.send_response(response.status)
            started = True
            for key, value in response.getheaders():
                if key.lower() not in HOP:
                    self.send_header(key, value)
            self.send_header('Connection', 'close')
            self.end_headers()
            if self.command != 'HEAD':
                while chunk := response.read1(16384):
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except (OSError, http.client.HTTPException):
            if not started:
                self.unavailable()
        finally:
            self.close_connection = True
            conn.close()

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = proxy


def main():
    global child
    server = ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '80'))), Handler)
    child = subprocess.Popen(['/app/run_metabase.sh'], start_new_session=True)

    def supervise():
        code = child.wait()
        print(f'Metabase process stopped with exit status {code}; stopping container.', flush=True)
        # A live proxy with a dead JVM would otherwise keep returning 503 forever.
        os._exit(code if code > 0 else 1)

    threading.Thread(target=supervise, daemon=True).start()

    def observe_startup():
        for tick in range(30):
            if child.poll() is not None:
                return
            print('Startup resources ' + json.dumps(resource_status(child.pid)), flush=True)
            if app_ready():
                print('Metabase health verified ready.', flush=True)
                return
            time.sleep(10)

    threading.Thread(target=observe_startup, daemon=True).start()

    def stop(*_):
        print('Container received termination signal.', flush=True)
        os.killpg(child.pid, signal.SIGTERM)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)


if __name__ == '__main__':
    main()
