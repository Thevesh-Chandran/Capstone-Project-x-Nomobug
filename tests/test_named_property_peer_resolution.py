from scripts.resolve_review_with_named_property_peers import (
    apply_peer,
    choose_peer,
    distinctive_name_agreement,
)


def test_distinctive_property_name_agreement():
    assert distinctive_name_agreement(
        "Conezion Residences", "Conezión Residences, IOI Resort City, Malaysia"
    )[0]
    assert not distinctive_name_agreement(
        "Conezion Residences", "Unrelated Residence, Kuala Lumpur"
    )[0]
    assert not distinctive_name_agreement(
        "Apartment Suri Puteri", "Vista Alam Serviced Apartment, Shah Alam"
    )[0]


def test_apply_peer_preserves_original_input_and_uses_geoapify_coordinates():
    original = {"address_hash": "unit", "input_address": "Conezion, CND-12-06"}
    peer = {
        "address_hash": "peer", "formatted": "Conezion Residences, IOI Resort City",
        "latitude": 2.9, "longitude": 101.7, "result_type": "amenity",
        "confidence": 1, "match_type": "full_match", "postcode": "62502",
        "postcode_agrees": None,
    }
    updated = apply_peer(original, peer)
    assert updated["input_address"] == original["input_address"]
    assert updated["peer_address_hash"] == "peer"
    assert updated["coordinate_source"] == "trusted_geoapify_named_property_peer"
