"""Offline safety tests for historical weather caching."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fetch_open_meteo_weather as weather


def test_location_id_is_stable_at_five_decimals():
    assert weather.location_id(3.1234561, 101.7654321) == \
        weather.location_id(3.1234599, 101.7654299)


def test_validate_response_requires_complete_dates(monkeypatch):
    monkeypatch.setattr(weather, "START_DATE", weather.date(2026, 1, 1))
    monkeypatch.setattr(weather, "END_DATE", weather.date(2026, 1, 2))
    payload = {"daily": {"time": ["2026-01-01", "2026-01-02"]}}
    for field in weather.DAILY_FIELDS:
        payload["daily"][field] = [1, 2]
    weather.validate_response(payload)
    payload["daily"][weather.DAILY_FIELDS[0]] = [1]
    with pytest.raises(ValueError, match="coverage"):
        weather.validate_response(payload)


def test_fetch_batch_accepts_single_response_shape(monkeypatch):
    monkeypatch.setattr(weather, "START_DATE", weather.date(2026, 1, 1))
    monkeypatch.setattr(weather, "END_DATE", weather.date(2026, 1, 1))
    payload = {"daily": {"time": ["2026-01-01"]}}
    for field in weather.DAILY_FIELDS:
        payload["daily"][field] = [1]

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return weather.json.dumps(payload).encode()

    monkeypatch.setattr(weather.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    records = weather.fetch_batch([{"latitude": 3.1, "longitude": 101.7}])
    assert len(records) == 1
    assert records[0]["response"]["daily"]["time"] == ["2026-01-01"]
