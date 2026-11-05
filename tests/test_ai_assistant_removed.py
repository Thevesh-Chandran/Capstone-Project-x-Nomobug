import threading
from http.server import ThreadingHTTPServer
import requests
from webapp.server import Portal,handler_for


def test_retired_ai_routes_do_not_call_ollama_and_booking_remains_present(tmp_path,monkeypatch):
    monkeypatch.setenv('CP2_AUTH_MODE','staff_code');monkeypatch.setenv('CP2_PORTAL_TOKEN','fixture')
    monkeypatch.delenv('CP2_PORTAL_GCS_URI',raising=False)
    portal=Portal(tmp_path);server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(portal));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_port);headers={'Cookie':'cp2_session='+portal.session(),'Origin':base}
    try:
        assert requests.get(base+'/api/assistant/status',headers=headers,timeout=3).status_code==410
        assert requests.post(base+'/api/assistant',json={'question':'Any question'},headers=headers,timeout=3).status_code==410
        result=requests.get(base+'/api/booking',headers=headers,timeout=3)
        assert result.status_code==200 and len(result.json()['teams'])==6
        assert requests.get(base+'/healthz',timeout=3).status_code==200
    finally:server.shutdown();server.server_close()


def test_active_frontend_contains_no_chat_surface_or_ollama_calls():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'webapp/static'
    for name in ('app.js','workspace.js','index.html','guide.js'):
        text=(root/name).read_text(encoding='utf-8')
        assert '/api/assistant' not in text
        assert 'ask-form' not in text
        assert 'Ollama' not in text
        assert '#assistant' not in text
        assert 'Ask Nomobug' not in text
    assert 'createBookingCalendar' in (root/'booking.js').read_text(encoding='utf-8')
