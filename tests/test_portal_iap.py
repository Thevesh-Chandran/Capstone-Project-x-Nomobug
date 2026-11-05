"""IAP-only access must verify signatures and ignore staff cookies."""
from webapp.server import Portal
from google.oauth2 import id_token

def test_iap_requires_assertion_and_expected_audience(monkeypatch,tmp_path):
    monkeypatch.setenv('CP2_AUTH_MODE','iap')
    monkeypatch.setenv('CP2_IAP_AUDIENCE','/projects/123/locations/region/services/portal')
    portal=Portal(tmp_path)
    assert not portal.authenticated('cp2_session='+portal.session())
    seen=[]
    def verify(token,request,**kwargs):
        seen.append(kwargs)
        return {'iss':'https://cloud.google.com/iap','sub':'verified-user'}
    monkeypatch.setattr(id_token,'verify_token',verify)
    assert portal.authenticated(None,'signed-assertion')
    assert seen[0]['audience']=='/projects/123/locations/region/services/portal'
    assert seen[0]['certs_url']=='https://www.gstatic.com/iap/verify/public_key'
    monkeypatch.setattr(id_token,'verify_token',lambda *a,**k:{'iss':'wrong','sub':'user'})
    assert not portal.authenticated(None,'wrong-issuer')
    def invalid(*a,**k):raise ValueError('invalid signature, expired or wrong audience')
    monkeypatch.setattr(id_token,'verify_token',invalid)
    assert not portal.authenticated(None,'forged')
    monkeypatch.delenv('CP2_IAP_AUDIENCE')
    assert not portal.authenticated(None,'signed-assertion')
