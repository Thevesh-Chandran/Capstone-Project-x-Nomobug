"""Offline tests for transient Google place hints and persistent Geoapify output."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from retry_geocodes_with_google_place_hints import (
    enriched_query,
    geoapify_matches_hint,
    proposed_record,
    select_place_hint,
)


def pelangi_place():
    return {
        "displayName": {"text": "Taman Kayangan, Pelangi Heights, Mantin"},
        "formattedAddress": "Jalan Kayangan 5, 71700 Mantin, Negeri Sembilan, Malaysia",
        "addressComponents": [
            {"longText": "Mantin", "types": ["locality"]},
            {"longText": "Negeri Sembilan", "types": ["administrative_area_level_1"]},
            {"longText": "71700", "types": ["postal_code"]},
        ],
    }


def test_select_place_hint_uses_meaningful_named_place_agreement():
    address = "106 Jalan Kayangan 2, Taman Kayangan, Pelangi Height"
    wrong = {
        "displayName": {"text": "Desa Kayangan"},
        "formattedAddress": "Jalan Desa Kayangan 2/4, Kedah, Malaysia",
    }
    assert select_place_hint(address, [wrong, pelangi_place()]) == pelangi_place()


def test_select_place_hint_ignores_unit_and_plural_for_named_building():
    place = {
        "displayName": {"text": "Razak City Residences"},
        "formattedAddress": "1 Jalan Razak Mansion, 57100 Kuala Lumpur, Malaysia",
    }
    assert select_place_hint("Razak City Residence C1-46-11", [place]) == place
    assert select_place_hint("Razak City Reaidences D3-42-11", [place]) == place


def test_enriched_query_adds_only_coarse_missing_fields():
    address = "106 Jalan Kayangan 2, Taman Kayangan, Pelangi Height"
    query, fields = enriched_query(address, pelangi_place())
    assert query == (
        "106 Jalan Kayangan 2, Taman Kayangan, Pelangi Height, Mantin, "
        "Negeri Sembilan, 71700, Malaysia"
    )
    assert fields == ("locality", "administrative_area_level_1", "postal_code")


def test_explicit_input_postcode_is_never_rewritten_by_google_hint():
    address = "Example Residence, 43000 Kajang"
    query, fields = enriched_query(address, pelangi_place())
    assert "71700" not in query
    assert "postal_code" not in fields


def test_persistent_record_contains_only_geoapify_result_and_hint_metadata():
    old = {
        "address_hash": "abc",
        "input_address": "Pelangi Heights",
        "calendar_event_rows": [1],
    }
    result = {
        "latitude": 2.86,
        "longitude": 101.86,
        "formatted": "Pelangi Heights, Mantin, Negeri Sembilan, Malaysia",
        "postcode": "71700",
        "result_type": "street",
        "confidence": 0.7,
        "result_count": 2,
    }
    record = proposed_record(old, result, ("locality", "postal_code"), True)
    assert record["provider"] == "geoapify"
    assert record["coordinate_source"] == \
        "geoapify_after_transient_google_place_hint"
    assert record["postcode_agrees"] is None
    assert record["google_places_hint_agreement"] is True
    assert not any(key.startswith("google_") and key not in {
        "google_places_hint_used", "google_places_hint_fields",
        "google_places_hint_agreement",
    } for key in record)


def test_geoapify_postcode_can_confirm_transient_google_locality_hint():
    assert geoapify_matches_hint(pelangi_place(), {
        "formatted": "71700 Mantin, Negeri Sembilan, Malaysia",
        "postcode": "71700",
    })
