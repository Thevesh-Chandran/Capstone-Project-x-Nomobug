"""Cloud collector must release its lease and preserve failed-tick evidence."""
from datetime import datetime, timezone

import pytest
from google.api_core.exceptions import PreconditionFailed

from scripts import cp2_cloud_collector as cloud


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


def test_cloud_tick_orders_durable_state_before_bigquery(monkeypatch):
    bucket = Bucket()
    events = []
    monkeypatch.setenv("NOMOBUG_CP2_COLLECTOR_BUCKET", bucket.name)
    monkeypatch.setattr(cloud.storage, "Client", lambda **kwargs: type(
        "Client", (), {"bucket": lambda self, name: bucket})())
    monkeypatch.setattr(cloud, "hydrate_artifacts", lambda b: events.append("artifacts"))
    monkeypatch.setattr(cloud, "hydrate_state", lambda b: events.append("state"))
    monkeypatch.setattr(cloud.tick, "poll", lambda: events.append("poll") or {"status": "idle"})
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
    monkeypatch.setattr(cloud.tick, "poll", lambda: (_ for _ in ()).throw(RuntimeError("source")))
    with pytest.raises(RuntimeError):
        cloud.run_tick()
    assert bucket.lock.deleted


def test_cloud_tick_does_not_overlap_active_run(monkeypatch):
    bucket = Bucket()
    monkeypatch.setenv("NOMOBUG_CP2_COLLECTOR_BUCKET", bucket.name)
    monkeypatch.setattr(cloud.storage, "Client", lambda **kwargs: type(
        "Client", (), {"bucket": lambda self, name: bucket})())
    monkeypatch.setattr(bucket.lock, "upload_from_string", lambda *args, **kwargs:
                        (_ for _ in ()).throw(PreconditionFailed("lease held")))
    assert cloud.run_tick()["status"] == "another_cloud_tick_active"
    assert not bucket.lock.deleted
