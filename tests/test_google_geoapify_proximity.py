"""Offline tests for transient Google-to-Geoapify proximity validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_google_geoapify_proximity import within_threshold


def test_within_threshold_accepts_nearby_point_and_rejects_distant_point():
    record = {"latitude": 3.1000, "longitude": 101.7000}
    nearby = {"location": {"latitude": 3.1040, "longitude": 101.7040}}
    distant = {"location": {"latitude": 3.1200, "longitude": 101.7200}}
    assert within_threshold(record, nearby)
    assert not within_threshold(record, distant)
