"""Operational scoring recovery uses a published release, never experiment logs."""
import json
from types import SimpleNamespace

import pytest
from google.cloud import bigquery
from scripts import publish_return_risk_predictors as export


class Client:
    def __init__(self, manifest=None, current=True):
        self.manifest, self.current, self.closed = manifest, current, False

    def query(self, sql, *, job_config):
        assert job_config.maximum_bytes_billed == 104857600
        if 'audit.release_runs' in sql:
            rows = [{'manifest_json': json.dumps(self.manifest)}] if self.manifest else []
        else:
            assert 'ORDER BY' in sql
            rows = [{'synthetic': 'value'}]
        return SimpleNamespace(result=lambda **kw: rows)

    def get_table(self, name):
        if '.gold.' in name:
            assert name.endswith('.gold.sales_monthly_recorded')
            release = self.manifest['run_id'] if self.current else 'another_release'
            return SimpleNamespace(view_query=f'SELECT * FROM `project.cp2r_{release}_gold.sales_monthly_recorded`')
        return SimpleNamespace(num_rows=1, description=json.dumps({
            'snapshot_id': name.rsplit('_', 1)[1], 'extracted_at': '2026-10-01T00:00:00+00:00'}))

    def close(self):
        self.closed = True


def manifest():
    keys = ('calendar', 'SALES', 'PAYMENT LINK', 'WARRANTY CLAIM')
    return {'run_id': '2026110403310550a46b',
            'snapshot_tables': {k: 'snapshot_' + 'a' * 64 for k in keys},
            'extracted_at': {k: '2026-11-04T03:31:00+00:00' for k in keys}}


def test_recovery_refuses_absent_release(monkeypatch):
    client = Client()
    monkeypatch.setattr(bigquery, 'Client', lambda **kw: client)
    with pytest.raises(ValueError, match='No published release'):
        export.from_published_release('gs://example/current')
    assert client.closed


def test_recovery_refuses_release_that_no_longer_matches_gold(monkeypatch):
    client = Client(manifest(), current=False)
    monkeypatch.setattr(bigquery, 'Client', lambda **kw: client)
    with pytest.raises(ValueError, match='no longer matches'):
        export.from_published_release('gs://example/current')
    assert client.closed


def test_recovery_keeps_verified_extraction_times_and_approved_sources(tmp_path, monkeypatch):
    client = Client(manifest())
    monkeypatch.setattr(bigquery, 'Client', lambda **kw: client)
    monkeypatch.setattr(export, 'ROOT', tmp_path)
    def publish(folder, uri, *, client):
        calendar = json.loads((folder / 'calendar_private.json').read_text())
        sheets = json.loads((folder / 'sheets_private.json').read_text())
        assert calendar['metadata']['extracted_at'] == manifest()['extracted_at']['calendar']
        assert set(sheets['snapshots']) == {'SALES', 'PAYMENT LINK', 'WARRANTY CLAIM'}
        assert json.loads((folder / 'release_manifest.json').read_text()) == manifest()
        return {'status': 'PUBLISHED', 'services': 1}
    monkeypatch.setattr(export, 'from_release', publish)
    assert export.from_published_release('gs://example/current')['status'] == 'PUBLISHED'
    assert client.closed
