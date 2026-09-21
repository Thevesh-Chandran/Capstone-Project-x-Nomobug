"""Offline checks for the Google-identification Geoapify retry."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from retry_review_with_google_identification import (
    acceptable_candidate,
    google_identification_queries,
    normalize_google_query_spacing,
    validate_google_address,
)


def test_query_variants_are_distinct_and_contain_no_coordinates_or_place_ids():
    place = {
        "displayName": {"text": "Example Residence"},
        "formattedAddress": "1 Jalan Example, 43000 Kajang, Malaysia",
        "addressComponents": [
            {"longText": "Kajang", "types": ["locality"]},
            {"longText": "43000", "types": ["postal_code"]},
        ],
    }
    queries = google_identification_queries("A-1 Example Residence", place)
    assert len(queries) >= 3
    assert len({query.casefold() for _, query in queries}) == len(queries)
    assert all("place" not in strategy or "text" in strategy for strategy, _ in queries)
    assert all("latitude" not in query and "longitude" not in query for _, query in queries)


def test_short_named_property_queries_are_tried_first():
    place = {
        "displayName": {"text": "Ampang Prima Condominium"},
        "formattedAddress": "Ampang Prima Condominium, Jalan Wawasan 2/5, 68000 Ampang",
        "addressComponents": [
            {"longText": "Ampang", "types": ["locality"]},
            {"longText": "Selangor", "types": ["administrative_area_level_1"]},
        ],
    }
    queries = google_identification_queries("15-3A AMPANG PRIMA CONDO", place)
    assert queries[0] == (
        "google_display_name_only", "Ampang Prima Condominium, Malaysia"
    )
    assert queries[1][0] == "google_name_city_only"


def test_collapsed_malaysian_address_boundaries_are_repaired():
    assert normalize_google_query_spacing(
        "No 6 Lorong SS1/24aKampung Tunku47300 Petaling JayaSelangor"
    ) == "No 6 Lorong SS1/24a Kampung Tunku 47300 Petaling Jaya Selangor"


def test_candidate_requires_geoapify_text_agreement_not_google_hint_alone():
    original = {"input_address": "Example Residence Jalan Mawar"}
    wrong = {
        "formatted": "Different District, Malaysia",
        "latitude": 3.1,
        "longitude": 101.7,
        "google_places_hint_agreement": True,
        "postcode_agrees": None,
    }
    right = {
        "formatted": "Example Residence, Jalan Mawar, Malaysia",
        "latitude": 3.1,
        "longitude": 101.7,
        "result_type": "building",
        "match_type": "match_by_building",
        "confidence": 0.6,
        "google_places_hint_agreement": True,
        "postcode_agrees": None,
    }
    assert not acceptable_candidate(original, wrong)
    assert acceptable_candidate(original, right)
