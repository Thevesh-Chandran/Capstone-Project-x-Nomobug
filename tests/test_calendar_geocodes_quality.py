"""Safety tests for the sanitized Calendar geocode quality loader."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from load_calendar_geocodes_quality import sanitized_rows


def test_sanitized_rows_exclude_raw_address_and_review_candidates():
    records = [
        {
            "address_hash": "a" * 64,
            "input_address": "private address",
            "calendar_event_rows": [10],
            "latitude": 3.1,
            "longitude": 101.7,
            "result_type": "street",
            "confidence": 0.8,
            "postcode_agrees": True,
        },
        {
            "address_hash": "b" * 64,
            "calendar_event_rows": [11],
            "latitude": 3.2,
            "longitude": 101.8,
            "result_type": "city",
            "confidence": 0.9,
            "postcode_agrees": False,
        },
    ]
    rows = sanitized_rows(records)
    assert len(rows) == 1
    assert rows[0]["calendar_event_row"] == 10
    assert "input_address" not in rows[0]


def test_sanitized_rows_reject_out_of_country_coordinates():
    records = [{
        "address_hash": "a" * 64,
        "input_address": "SkyDeck Camp Lu Ying",
        "formatted": "SkyDeck, Camp Lu Ying, Selangor, Malaysia",
        "calendar_event_rows": [10],
        "latitude": 51.5,
        "longitude": -0.1,
        "result_type": "street",
        "confidence": 0.8,
        "postcode_agrees": True,
    }]
    assert sanitized_rows(records) == []


def test_sanitized_rows_include_area_analysis_candidate_without_claiming_precision():
    records = [{
        "address_hash": "a" * 64,
        "input_address": "SkyDeck Camp Lu Ying",
        "formatted": "SkyDeck, Camp Lu Ying, Selangor, Malaysia",
        "calendar_event_rows": [10],
        "latitude": 3.1,
        "longitude": 101.7,
        "result_type": "building",
        "confidence": 0.2,
        "match_type": "match_by_building",
        "postcode_agrees": None,
    }]
    rows = sanitized_rows(records)
    assert rows[0]["precision_tier"] == "area_analysis_candidate"


def test_sanitized_rows_enforce_calendar_event_grain():
    record = {
        "address_hash": "a" * 64,
        "calendar_event_rows": [10, 10],
        "latitude": 3.1,
        "longitude": 101.7,
        "result_type": "street",
        "confidence": 0.8,
        "postcode_agrees": True,
    }
    with pytest.raises(ValueError, match="grain expanded"):
        sanitized_rows([record])


def test_sanitized_rows_include_postcode_proximity_candidate():
    records = [{
        "address_hash": "c" * 64,
        "input_address": "Residensi Example 55200 Kuala Lumpur",
        "formatted": "Residensi Example, Kuala Lumpur, Malaysia",
        "calendar_event_rows": [12],
        "latitude": 3.1,
        "longitude": 101.7,
        "result_type": "amenity",
        "confidence": 0.5,
        "postcode_agrees": False,
        "postcode_reference_distance_km": 3.0,
    }]
    assert sanitized_rows(records)[0]["precision_tier"] == "proximity_candidate"


def test_sanitized_rows_include_verified_peer_address_candidate():
    records = [{
        "address_hash": "d" * 64,
        "input_address": "alternate address spelling",
        "formatted": "trusted peer provider result",
        "calendar_event_rows": [13],
        "latitude": 3.1,
        "longitude": 101.7,
        "peer_address_agreement": True,
        "postcode_agrees": None,
    }]
    assert sanitized_rows(records)[0]["precision_tier"] == "peer_address_candidate"


def test_sanitized_rows_preserve_protected_manual_coordinate_provenance():
    records = [{
        "address_hash": "e" * 64,
        "input_address": "verified property",
        "calendar_event_rows": [14],
        "latitude": 3.1,
        "longitude": 101.7,
        "coordinate_source": "manual_user_verified",
        "manual_override_protected": True,
        "result_type": "manual_coordinate",
    }]
    row = sanitized_rows(records)[0]
    assert row["precision_tier"] == "manual_verified"
    assert row["geocode_provider"] == "manual"
    assert row["coordinate_source"] == "manual_user_verified"
    assert row["manual_override_protected"] is True
