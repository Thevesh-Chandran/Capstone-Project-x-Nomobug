"""Release consistency and last-good snapshot recovery at the storage boundary."""
import json
from urllib.parse import unquote, urlsplit

import pytest

from webapp import storage


class Response:
    status_code = 200

    def __init__(self, value):
        self.content = json.dumps(value).encode()

    def raise_for_status(self):
        pass


class Session:
    def __init__(self, release, tools_release, fail_file=None):
        self.release = release
        self.tools_release = tools_release
        self.fail_file = fail_file

    def get(self, url, **kwargs):
        name = unquote(urlsplit(url).path).rsplit('/', 1)[-1]
        if name == self.fail_file:
            raise TimeoutError('Synthetic refresh timeout')
        if name == 'business_snapshot.json':
            return Response({'status':'connected', 'tables':{'freshness':[
                {'source_name':source, 'release_run_id':self.release}
                for source in ('sales', 'calendar', 'recurring_payments')]}})
        if name == 'business_tools_private.json':
            return Response({'receipt':{'published_release':'cp2r_'+self.tools_release}})
        return Response({'fixture':'new'})


@pytest.mark.parametrize('failure', ['mixed_release', 'download_timeout'])
def test_failed_refresh_retains_all_files_then_matching_release_recovers(tmp_path, failure):
    names = (*storage.FILES, 'business_tools_private.json')
    originals = {name:json.dumps({'fixture':'last_good', 'file':name}).encode() for name in names}
    for name, raw in originals.items():
        (tmp_path/name).write_bytes(raw)
    session = Session('new', 'old' if failure == 'mixed_release' else 'new',
        'business_snapshot.json' if failure == 'download_timeout' else None)
    with pytest.raises((ValueError, TimeoutError)):
        storage.pull('gs://fixture/current', tmp_path, session)
    assert {name:(tmp_path/name).read_bytes() for name in names} == originals
    storage.pull('gs://fixture/current', tmp_path, Session('new', 'new'))
    assert json.loads((tmp_path/'business_tools_private.json').read_text())['receipt']['published_release']=='cp2r_new'
    assert json.loads((tmp_path/'business_snapshot.json').read_text())['tables']['freshness'][0]['release_run_id']=='new'
    assert not list(tmp_path.glob('*.next'))
