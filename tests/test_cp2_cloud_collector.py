"""Cloud collector must release its lease and preserve failed-tick evidence."""
from datetime import datetime, timezone
import json
from hashlib import sha256

import pytest
from google.api_core.exceptions import PreconditionFailed

from scripts import cp2_cloud_collector as cloud


def test_artifact_prefix_is_stable_across_json_line_endings(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud, "ROOT", tmp_path)
    path = tmp_path / "config/cp2_live_feature_contract.json"
    path.parent.mkdir()
    path.write_bytes(b'{\n  "version": "test",\n  "hash": "abc"\n}\n')
    first = cloud.artifact_prefix()
    path.write_bytes(b'{\r\n  "hash": "abc",\r\n  "version": "test"\r\n}\r\n')
    assert cloud.artifact_prefix() == first
    assert first.startswith("artifacts/")


def test_startup_rejects_unpublished_gold_field(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud, "ROOT", tmp_path)
    sql = tmp_path / "dbt/target/compiled/nomobug/models/calendar_events.sql"
    sql.parent.mkdir(parents=True)
    sql.write_text("SELECT r.event_identity_hash", encoding="utf-8")
    monkeypatch.setenv("NOMOBUG_CP2_COLLECTOR_BUCKET", "private-test")
    monkeypatch.setattr(cloud.storage, "Client", lambda **kwargs: type(
        "Storage", (), {"bucket": lambda self, name: object()})())
    monkeypatch.setattr(cloud, "hydrate_artifacts", lambda bucket: None)

    class BigQuery:
        def get_table(self, name):
            return type("Table", (), {"schema": [type("Field", (), {"name": "calendar_event_row"})()]})()

        def close(self):
            pass

    monkeypatch.setattr(cloud.bigquery, "Client", lambda **kwargs: BigQuery())
    with pytest.raises(ValueError, match="incompatible"):
        cloud.preflight_dependencies()

    BigQuery.get_table = lambda self, name: type("Table", (), {"schema": [
        type("Field", (), {"name": "event_identity_hash"})()]})()
    cloud.preflight_dependencies()


class Lock:
    generation = 7
    updated = datetime.now(timezone.utc)

    def __init__(self):
        self.deleted = False

    def upload_from_string(self, *args, **kwargs):
        assert kwargs["if_generation_match"] == 0

    def reload(self):
        pass

    def delete(self, *, if_generation_match):
        assert if_generation_match == self.generation
        self.deleted = True


class Bucket:
    name = "private-test"

    def __init__(self):
        self.lock = Lock()

    def blob(self, name):
        assert name == "control/active_tick.json"
        return self.lock


def test_recovery_final_restores_after_upload_failure_without_reevaluation(tmp_path,monkeypatch):
    from scripts.freeze_callback_prospective import record_digest
    monkeypatch.setattr(cloud,'ROOT',tmp_path)
    monkeypatch.setattr(cloud.pipeline,'BASE',tmp_path/'state')
    config=tmp_path/'config';config.mkdir()
    registry={'bundle_sha256':'a'*64,'recovery_cohort_protocol_sha256':'b'*64}
    (config/'cp2_model_current.json').write_text(json.dumps(registry))
    objects={'evaluations/october10_2026.json':b'original incomplete evidence'};failed=[False];calls=[]
    class Blob:
        def __init__(self,name):self.name=name
        def exists(self):return self.name in objects
        def download_as_bytes(self):return objects[self.name]
        def upload_from_string(self,raw,**kwargs):
            assert kwargs['if_generation_match']==0
            if self.exists():raise PreconditionFailed('exists')
            objects[self.name]=raw
        def upload_from_filename(self,path,**kwargs):
            if self.name=='evaluations/recovery_20261016.json' and not failed[0]:
                failed[0]=True;raise OSError('Interrupted aggregate upload')
            self.upload_from_string(__import__('pathlib').Path(path).read_bytes(),**kwargs)
    bucket=type('B',(),{'blob':lambda self,name:Blob(name)})()
    def evaluate(bucket,**kwargs):
        calls.append(kwargs)
        path=tmp_path/'outputs/cp2-v2/prospective_callback_v2/prospective_recovery_evaluation.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        labels=path.parent/'labels.json';payload={'schema_version':2,'records':[]}
        payload['record_sha256']=record_digest(payload);labels.write_text(json.dumps(payload))
        path.write_text(json.dumps({'bundle_sha256':'a'*64,'repaired_protocol_sha256':'b'*64,
            'cohort_start':'2026-10-16','cohort_end':'2026-10-30','source_labels_sha256':sha256(labels.read_bytes()).hexdigest()}))
        return {'labels_path':str(labels)}
    monkeypatch.setattr(cloud,'journaled_final_evaluation',evaluate)
    with pytest.raises(OSError):cloud.recovery_final_evaluation(bucket)
    assert cloud.recovery_final_evaluation(bucket)['status']=='finalized'
    assert cloud.recovery_final_evaluation(bucket)['status']=='already_finalized'
    assert calls==[{'recovery':True}]
    assert objects['evaluations/october10_2026.json']==b'original incomplete evidence'
    registry['recovery_cohort_protocol_sha256']='c'*64
    (config/'cp2_model_current.json').write_text(json.dumps(registry))
    with pytest.raises(ValueError,match='protocol'):cloud.recovery_final_evaluation(bucket)


def test_followup_upload_recovery_does_not_repeat_primary(tmp_path, monkeypatch):
    from scripts import evaluate_cp2_followup_policy as policy
    class Blob:
        def __init__(self): self.raw = None
        def exists(self): return self.raw is not None
        def upload_from_string(self, raw, **kwargs):
            assert kwargs['if_generation_match'] == 0
            if self.exists(): raise PreconditionFailed('exists')
            self.raw = raw
        def upload_from_filename(self, path, **kwargs):
            self.upload_from_string(__import__('pathlib').Path(path).read_bytes(), **kwargs)
        def download_as_bytes(self): return self.raw
    objects = {}
    bucket = type('B', (), {'blob': lambda self, name: objects.setdefault(name, Blob())})()
    monkeypatch.setattr(cloud.pipeline, 'BASE', tmp_path)
    monkeypatch.setattr(policy, 'RESULT', tmp_path / 'supplement.json')
    calls = []
    def evaluate(labels, logs):
        calls.append(labels.read_bytes())
        policy.RESULT.write_text('{"comparison":true}')
    monkeypatch.setattr(policy, 'evaluate', evaluate)
    source = tmp_path / 'labels.json'
    source.write_text('{"complete":true}')
    assert cloud.finish_followup_comparison(bucket, source) == 'finalized'
    assert cloud.finish_followup_comparison(bucket) == 'already_finalized'
    assert calls == [source.read_bytes()]
    assert set(objects) == {'evaluations/followup_policy_v1.json', 'evaluations/private/october10_labels.json'}


def test_followup_failure_keeps_labels_for_retry(tmp_path, monkeypatch):
    from scripts import evaluate_cp2_followup_policy as policy
    class Blob:
        raw = None
        def exists(self): return self.raw is not None
        def upload_from_string(self, raw, **kwargs): self.raw = raw
        def download_as_bytes(self): return self.raw
    objects = {}
    bucket = type('B', (), {'blob': lambda self, name: objects.setdefault(name, Blob())})()
    monkeypatch.setattr(cloud.pipeline, 'BASE', tmp_path)
    monkeypatch.setattr(policy, 'RESULT', tmp_path / 'supplement.json')
    monkeypatch.setattr(policy, 'evaluate', lambda *args: (_ for _ in ()).throw(ValueError('incomplete')))
    source = tmp_path / 'labels.json'
    source.write_text('{"complete":false}')
    with pytest.raises(ValueError, match='incomplete'):
        cloud.finish_followup_comparison(bucket, source)
    assert objects['evaluations/private/october10_labels.json'].raw == source.read_bytes()
    assert not objects['evaluations/followup_policy_v1.json'].exists()


def test_final_evidence_commits_result_and_labels_together(tmp_path, monkeypatch):
    class Blob:
        raw = None
        def exists(self): return self.raw is not None
        def upload_from_string(self, raw, **kwargs):
            assert kwargs['if_generation_match'] == 0
            if self.exists(): raise PreconditionFailed('exists')
            self.raw = raw
        def download_as_bytes(self): return self.raw
    blob = Blob()
    bucket = type('B', (), {'blob': lambda self, name: blob})()
    monkeypatch.setattr(cloud.pipeline, 'BASE', tmp_path / 'state')
    labels = tmp_path / 'labels.json'
    labels.write_bytes(b'{"complete":true}\r\n')
    result = tmp_path / 'result.json'
    result.write_text(json.dumps({'source_labels_sha256': sha256(labels.read_bytes()).hexdigest()}))
    cloud.preserve_october10_evidence(bucket, result, labels)
    # A repeat of exactly the same evidence is safe; a new refresh is not.
    cloud.preserve_october10_evidence(bucket, result, labels)
    recovered = tmp_path / 'recovered/result.json'
    recovered_labels = cloud.restore_october10_evidence(bucket, recovered)
    assert recovered.read_bytes() == result.read_bytes()
    assert recovered_labels.read_bytes() == labels.read_bytes()
    result.write_text('{}')
    with pytest.raises(ValueError, match='does not match'):
        cloud.preserve_october10_evidence(bucket, result, labels)


def test_cloud_tick_orders_durable_state_before_bigquery(monkeypatch):
    bucket = Bucket()
    events = []
    monkeypatch.setenv("NOMOBUG_CP2_COLLECTOR_BUCKET", bucket.name)
    monkeypatch.setattr(cloud.storage, "Client", lambda **kwargs: type(
        "Client", (), {"bucket": lambda self, name: bucket})())
    monkeypatch.setattr(cloud, "hydrate_artifacts", lambda b: events.append("artifacts"))
    monkeypatch.setattr(cloud, "hydrate_state", lambda b: events.append("state"))
    monkeypatch.setattr(cloud.tick, "poll", lambda **kwargs: events.append("poll") or {"status": "idle"})
    monkeypatch.setattr(cloud, "persist_state", lambda b: events.append("persist"))
    monkeypatch.setattr(cloud, "mirror_predictions", lambda b: events.append("mirror") or 0)
    assert cloud.run_tick()["status"] == "idle"
    assert events == ["artifacts", "state", "poll", "persist", "mirror"]
    assert bucket.lock.deleted


def test_cloud_tick_releases_lease_on_source_failure(monkeypatch):
    bucket = Bucket()
    monkeypatch.setenv("NOMOBUG_CP2_COLLECTOR_BUCKET", bucket.name)
    monkeypatch.setattr(cloud.storage, "Client", lambda **kwargs: type(
        "Client", (), {"bucket": lambda self, name: bucket})())
    monkeypatch.setattr(cloud, "hydrate_artifacts", lambda b: None)
    monkeypatch.setattr(cloud, "hydrate_state", lambda b: None)
    preserved = []
    monkeypatch.setattr(cloud, "persist_state", lambda b: preserved.append(True))
    monkeypatch.setattr(cloud.tick, "poll", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("source")))
    with pytest.raises(RuntimeError):
        cloud.run_tick()
    assert bucket.lock.deleted
    assert preserved == [True]


def test_cloud_tick_does_not_overlap_active_run(monkeypatch):
    bucket = Bucket()
    monkeypatch.setenv("NOMOBUG_CP2_COLLECTOR_BUCKET", bucket.name)
    monkeypatch.setattr(cloud.storage, "Client", lambda **kwargs: type(
        "Client", (), {"bucket": lambda self, name: bucket})())
    monkeypatch.setattr(bucket.lock, "upload_from_string", lambda *args, **kwargs:
                        (_ for _ in ()).throw(PreconditionFailed("lease held")))
    assert cloud.run_tick()["status"] == "another_cloud_tick_active"
    assert not bucket.lock.deleted


class JournalBlob:
    generation = 1

    def __init__(self):
        self.payload = None

    def upload_from_string(self, payload, **kwargs):
        assert kwargs['if_generation_match'] == 0
        assert kwargs['timeout'] == 10 and kwargs['retry'] is None
        if self.payload is not None:
            raise PreconditionFailed('exists')
        self.payload = payload

    def reload(self, **kwargs):
        pass

    def download_as_bytes(self, **kwargs):
        assert kwargs['if_generation_match'] == self.generation
        return self.payload


class JournalBucket:
    def __init__(self):
        self.objects = {}

    def blob(self, name):
        return self.objects.setdefault(name, JournalBlob())


def test_journal_redacts_source_bodies_and_binds_original_manifest(tmp_path):
    run_dir = tmp_path / '20261004T030000Z_01234567'
    run_dir.mkdir()
    state = {'run_id': run_dir.name, 'status': 'failed', 'error_type': 'ValueError',
             'error_message': 'private token and customer', 'stages': {'sources': {
                 'status': 'succeeded', 'receipt': {'customer_name': 'Private name', 'token': 'secret'}}}}
    path = run_dir / 'run.json'
    path.write_text(json.dumps(state))
    bucket = JournalBucket()
    cloud.persist_run_journal(bucket, run_dir)
    cloud.persist_run_journal(bucket, run_dir)
    assert len(bucket.objects) == 1
    name, blob = next(iter(bucket.objects.items()))
    payload = json.loads(blob.payload)
    assert payload['source_manifest_sha256'] == sha256(path.read_bytes()).hexdigest()
    assert sha256(blob.payload).hexdigest() in name
    assert b'Private name' not in blob.payload and b'secret' not in blob.payload
    assert 'error_message' not in payload
    blob.payload = b'altered'
    with pytest.raises(ValueError, match='integrity'):
        cloud.persist_run_journal(bucket, run_dir)


def test_journal_rejects_large_or_mismatched_manifest(tmp_path):
    run_dir = tmp_path / '20261004T030000Z_01234567'
    run_dir.mkdir()
    path = run_dir / 'run.json'
    path.write_bytes(b' ' * (cloud.JOURNAL_MAX_BYTES + 1))
    with pytest.raises(ValueError, match='bound'):
        cloud.persist_run_journal(JournalBucket(), run_dir)
    path.write_text(json.dumps({'run_id': '../wrong'}))
    with pytest.raises(ValueError, match='identity'):
        cloud.persist_run_journal(JournalBucket(), run_dir)


@pytest.mark.parametrize('fails', [False, True])
def test_pipeline_journals_terminal_success_and_failure(tmp_path, monkeypatch, fails):
    run_dir = tmp_path / '20261004T030000Z_01234567'
    run_dir.mkdir()
    state = {'run_id': run_dir.name, 'status': 'running', 'stages': {'sources': {'status': 'running'}}}
    path = run_dir / 'run.json'
    path.write_text(json.dumps(state))
    def callback(directory):
        assert directory == run_dir
        return {'private': 'not archived'}
    monkeypatch.setattr(cloud.pipeline, 'stage_callbacks', lambda: {'sources': callback})
    def run(**kwargs):
        kwargs['callbacks']['sources'](run_dir)
        state['status'] = 'failed' if fails else 'succeeded'
        state['stages']['sources']['status'] = state['status']
        path.write_text(json.dumps(state))
        if fails:
            raise RuntimeError('private failure')
        return state
    monkeypatch.setattr(cloud.pipeline, 'run', run)
    bucket = JournalBucket()
    if fails:
        with pytest.raises(RuntimeError):
            cloud.journaled_pipeline_run(bucket)
    else:
        assert cloud.journaled_pipeline_run(bucket)['status'] == 'succeeded'
    statuses = {json.loads(blob.payload)['status'] for blob in bucket.objects.values()}
    assert statuses == {'running', 'failed' if fails else 'succeeded'}
