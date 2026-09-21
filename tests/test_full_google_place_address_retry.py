"""Offline safety tests for the full-place transient retry."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from retry_remaining_with_full_google_place_address import full_place_query


def test_full_place_query_combines_name_and_formatted_address_transiently():
    place = {
        "displayName": {"text": "Razak City Residences"},
        "formattedAddress": "1 Jalan Razak Mansion, 57100 Kuala Lumpur, Malaysia",
    }
    assert full_place_query(place) == (
        "Razak City Residences 1 Jalan Razak Mansion, 57100 Kuala Lumpur, Malaysia"
    )


def test_full_place_query_adds_country_when_provider_omits_it():
    place = {
        "displayName": {"text": "Example Residence"},
        "formattedAddress": "Jalan Example, Kuala Lumpur",
    }
    assert full_place_query(place).endswith(", Malaysia")
