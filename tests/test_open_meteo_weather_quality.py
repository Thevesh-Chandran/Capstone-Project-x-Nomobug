"""Offline grain tests for the weather Quality loader."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from load_open_meteo_weather_quality import expanded_rows


def sample_record():
    return {
        "weather_location_id": "x", "requested_latitude": 3.1,
        "requested_longitude": 101.7, "model": "ecmwf_ifs",
        "response": {"latitude": 3.12, "longitude": 101.68, "daily": {
            "time": ["2026-01-01"], "temperature_2m_mean": [27.0],
            "precipitation_sum": [3.0], "rain_sum": [3.0],
            "relative_humidity_2m_mean": [82.0],
            "soil_moisture_0_to_7cm_mean": [0.3],
        }},
    }


def test_expansion_preserves_location_date_grain():
    rows = expanded_rows([sample_record()])
    assert len(rows) == 1
    assert rows[0]["weather_date"] == "2026-01-01"
    assert rows[0]["precipitation_sum_mm"] == 3.0


def test_duplicate_location_is_rejected():
    record = sample_record()
    with pytest.raises(ValueError, match="duplicate weather location"):
        expanded_rows([record, record])
