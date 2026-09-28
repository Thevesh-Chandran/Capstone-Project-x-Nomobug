from scripts.resolve_named_property_aliases import is_conezion_alias, resolve_conezion


def test_conezion_alias_spellings():
    assert is_conezion_alias("Conezion, CND-12-06")
    assert is_conezion_alias("Conezión Residences, IOI Resort City")
    assert not is_conezion_alias("Unrelated residence")


def test_resolve_conezion_uses_exact_property_peer():
    rows = [
        {
            "address_hash": "canonical",
            "input_address": "08-13A Conezion Residence",
            "formatted": "Conezión Residences, IOI Resort City, 62502 Sepang, Malaysia",
            "latitude": 2.9650623,
            "longitude": 101.7206449,
            "result_type": "amenity",
            "confidence": 0,
            "match_type": "full_match",
            "postcode": "62502",
            "postcode_agrees": None,
        },
        {"address_hash": "unit", "input_address": "Conezion, CND-12-06"},
    ]
    assert resolve_conezion(rows) == 2
    assert rows[1]["latitude"] == 2.9650623
    assert rows[1]["peer_address_hash"] == "canonical"
    assert rows[1]["coordinate_source"] == "trusted_geoapify_named_property_peer"
