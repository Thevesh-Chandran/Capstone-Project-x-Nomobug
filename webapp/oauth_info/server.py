"""Serve only approved public information assets; no source or customer API."""
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT=Path(__file__).parent
PAGES={'/':'index.html','/index.html':'index.html','/privacy':'privacy.html',
       '/privacy.html':'privacy.html','/usage':'usage.html','/usage.html':'usage.html'}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        name=PAGES.get(urlsplit(self.path).path)
        if not name:
            self.send_error(404);return
        content=(ROOT/name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(content)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers();self.wfile.write(content)

if __name__=='__main__':
    ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8080'))),Handler).serve_forever()
