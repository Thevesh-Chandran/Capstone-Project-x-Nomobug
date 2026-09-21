"""Offline safety checks for the capped Calendar geocoding pilot."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pilot_geoapify_calendar import (
    ADDRESS_PLACEHOLDER, address_text_agreement, analysis_tier, choose_result,
    eligible_address, precision_tier,
    sanitized_address_candidate, without_leading_premise,
)
from summarize_geoapify_calendar import current_tier


def test_clear_address_is_eligible():
    assert eligible_address("No 18 Jalan P8G1, Presint 8, Putrajaya")


def test_contact_or_url_is_never_eligible():
    assert not eligible_address("No 18 Jalan P8G1, Putrajaya 0132044243")
    assert not eligible_address("No 18 Jalan P8G1, Putrajaya person@example.com")
    assert not eligible_address("No 18 Jalan P8G1, Putrajaya https://example.com")


def test_sanitizer_removes_name_and_contact_tail_before_geocoding():
    source = "Muhamad Nor Asnawi no 7 Jalan Suadamai 6/1, Cheras 0132044243"
    assert sanitized_address_candidate(source) == "no 7 Jalan Suadamai 6/1, Cheras"
    assert sanitized_address_candidate(source).casefold().startswith("no 7")


def test_sanitizer_accepts_street_led_address_without_customer_name():
    assert sanitized_address_candidate("Jalan Sultan Ismail, Kuala Lumpur") == \
        "Jalan Sultan Ismail, Kuala Lumpur"


def test_sanitizer_preserves_leading_house_number_before_later_unit_number():
    source = "16, jalan ecohill 7/2L, setia ecohill 2, 43500 semenyih"
    assert sanitized_address_candidate(source) == source


def test_sanitizer_accepts_explicitly_labelled_named_or_unit_led_premises():
    assert sanitized_address_candidate("Address: SkyDeck, Camp Lu Ying") == \
        "SkyDeck, Camp Lu Ying"
    assert sanitized_address_candidate("Alamat: C-16-01, Trefoil @ Setia Alam") == \
        "C-16-01, Trefoil @ Setia Alam"


def test_sanitizer_still_removes_contacts_after_explicit_address_label():
    source = "Nama: Ali Alamat: 11 Jalan Mawar, Shah Alam Phone: 0123456789"
    assert sanitized_address_candidate(source) == "11 Jalan Mawar, Shah Alam"


def test_sanitizer_decodes_escaped_calendar_html_before_removing_form_fields():
    source = ("Nama: Zakwan&lt;br&gt;Alamat: B07-05, Lake Front Homes, Cyberjaya"
              "&lt;br&gt;&lt;br&gt;Package: 3x Session&lt;br&gt;Phone: 0139639267")
    assert sanitized_address_candidate(source) == \
        "B07-05, Lake Front Homes, Cyberjaya"


def test_malay_address_placeholder_is_not_treated_as_a_location():
    assert ADDRESS_PLACEHOLDER.fullmatch("tepat akan diberi)")
    assert ADDRESS_PLACEHOLDER.fullmatch("alamat tepat akan diberi")
    assert not ADDRESS_PLACEHOLDER.fullmatch(
        "9 persiaran titiwangsa, Taman tasik titiwangsa"
    )
    source = (
        "Nama: Cindy Alamat: 9 persiaran titiwangsa, Taman tasik titiwangsa "
        "( alamat tepat akan diberi) Package: 1x Session"
    )
    assert sanitized_address_candidate(source) == (
        "9 persiaran titiwangsa, Taman tasik titiwangsa"
    )


def test_ambiguous_name_prefix_and_bare_postcode_are_not_eligible():
    assert not eligible_address("Muhamad Nor Asnawi no 7 Jalan Suadamai 6/1, Cheras")
    assert not eligible_address("53300 Kuala Lumpur")


def test_candidate_selection_prefers_matching_input_postcode():
    results = [
        {"postcode": "48020", "result_type": "building", "rank": {"confidence": 0.9}},
        {"postcode": "48000", "result_type": "street", "rank": {"confidence": 0.4}},
    ]
    selected, agrees = choose_result("No 2 Jalan 3/14, Rawang 48000", results)
    assert selected["postcode"] == "48000"
    assert agrees is True


def test_precision_tiers_preserve_uncertainty():
    assert precision_tier("building", True, 0.9) == "precise_candidate"
    assert precision_tier("street", True, 0.4) == "street_candidate"
    assert precision_tier("postcode", True, 0.2) == "postcode_area_candidate"
    assert precision_tier("street", None, 0.5) == "street_candidate"
    assert precision_tier("building", False, 0.9) == "manual_review"


def test_area_analysis_tier_does_not_claim_property_precision():
    assert analysis_tier({
        "input_address": "SkyDeck Camp Lu Ying",
        "formatted": "SkyDeck, Camp Lu Ying, Selangor, Malaysia",
        "result_type": "building", "postcode_agrees": None,
        "confidence": 0.2, "match_type": "match_by_building",
        "latitude": 3.1, "longitude": 101.7,
    }) == "area_analysis_candidate"
    assert analysis_tier({
        "input_address": "SkyDeck Camp Lu Ying",
        "formatted": "SkyDeck, Camp Lu Ying, Selangor, Malaysia",
        "result_type": "building", "postcode_agrees": False,
        "confidence": 0.9, "match_type": "full_match",
        "latitude": 3.1, "longitude": 101.7,
    }) == "text_agreement_candidate"
    assert analysis_tier({
        "input_address": "Shah Alam",
        "formatted": "Shah Alam, Selangor, Malaysia",
        "result_type": "city", "postcode_agrees": None,
        "confidence": 0.9, "match_type": "full_match",
        "latitude": 3.1, "longitude": 101.7,
    }) == "text_agreement_candidate"


def test_no_postcode_street_confidence_cannot_override_contradictory_text():
    assert analysis_tier({
        "input_address": "seksyen 7 shah alam",
        "formatted": "7-Eleven, Jalan 20/2B, Section 20, 40300 Shah Alam, Malaysia",
        "result_type": "street", "postcode_agrees": None,
        "confidence": 0.9, "match_type": "full_match",
        "latitude": 3.1, "longitude": 101.7,
    }) == "manual_review"


def test_generic_persiaran_word_does_not_create_false_address_agreement():
    assert not address_text_agreement(
        "9 Persiaran Titiwangsa, Taman Tasik Titiwangsa",
        "9 Persiaran Komersial 9, Sungai Siput, Perak",
    )


def test_summary_recomputes_tier_with_current_rules():
    record = {
        "input_address": "Jalan Ampang Kuala Lumpur",
        "formatted": "Jalan Ampang, Kuala Lumpur, Malaysia",
        "result_type": "street", "postcode_agrees": None, "confidence": 0.5,
    }
    assert current_tier(record) == "street_candidate"


def test_meaningful_address_text_agreement_accepts_user_confirmed_examples():
    assert address_text_agreement(
        "1-03A glomac centro kampung sungai aku ara",
        "Glomac Centro, Lorong Masjid 2, Bandar Utama, Petaling Jaya, Malaysia",
    )
    assert address_text_agreement(
        "No.4 Jalan Bangsar 59200 KL",
        "4 Jalan Bangsar, Bangsar, 50470 Kuala Lumpur, Malaysia",
    )
    assert address_text_agreement(
        "No.48 Lorong Temenggung 41B/KS07 42100 Klang",
        "Lorong Temenggung 41B/KS07, Bandar Sentosa, 41200 Klang City, SGR, Malaysia",
    )
    assert address_text_agreement(
        "seksyen 7 shah alam", "Section 7, Shah Alam, Selangor, Malaysia",
    )
    assert address_text_agreement(
        "Taman Connaught", "Taman Connaught, Kuala Lumpur, Malaysia",
    )


def test_generic_overlap_does_not_validate_wrong_area():
    assert not address_text_agreement(
        "No.26 Japan P14C1, Presint 14, 62050 Putrajaya",
        "Presint 1, 14290 Sungai Petani, KDH, Malaysia",
    )
    assert not address_text_agreement("Jalan", "Jalan Ampang, Kuala Lumpur")


def test_shortened_provider_results_can_match_meaningful_components():
    assert address_text_agreement(
        "11 Jalan TR 2/4, Tropicana Golf and Country Resort, Petaling Jaya",
        "2/4 Jalan TR 2/4, 47810 Petaling Jaya, SGR, Malaysia",
    )
    assert address_text_agreement(
        "11, Jalan Merah Saga 4, Teratai Villas, Kayangan Heights, Shah Alam",
        "11 Kayangan Heights, 42300 Shah Alam, SGR, Malaysia",
    )
    assert address_text_agreement(
        "11-16 Pangsapuri Beringin, Taman Gombak Permai, Batu Caves",
        "Pangsapuri Beringin, Selayang, Gombak, Malaysia",
    )


def test_shared_unit_number_and_generic_name_do_not_override_different_town():
    assert not address_text_agreement(
        "11-7, Residensi Prima, Jalan Jubilee, Jalan Loke Yew, Pudu KL",
        "11-7 Jalan Prima 7/11, 47130 Puchong, SGR, Malaysia",
    )


def test_second_pass_query_removes_only_leading_premise_identifier():
    assert without_leading_premise(
        "11-7, Residensi Prima Jalan Jubilee, Pudu KL"
    ) == "Residensi Prima Jalan Jubilee, Pudu KL"
    assert without_leading_premise(
        "12A Jalan Ulek Mayang 5J/KU5, Bandar Bukit Raja"
    ) == "Jalan Ulek Mayang 5J/KU5, Bandar Bukit Raja"


def test_common_malaysian_address_variants_normalize_consistently():
    assert address_text_agreement(
        "Residensi Prima Jalan Jubilee, Jalan Like Yew, Pudu KL",
        "Residensi Jalan Jubilee, Jalan Loke Yew, Pudu, Kuala Lumpur",
    )
    assert address_text_agreement(
        "Bdr Sri Permaisuri, Sel", "Bandar Seri Permaisuri, Selangor",
    )
    assert address_text_agreement(
        "No 14 Jalan 6, Taman Vista Mutiara Bukit SG Long, 4300 Selangor",
        "4300 Jalan Bukit Sungai Long 1/6, Bandar Sungai Long, 43000 Kajang, SGR, Malaysia",
    )
    assert address_text_agreement(
        "S2C 2-6, One Ampang Avenue, South View",
        "South View One Ampang Avenue, 68000 Ampang Jaya, SGR, Malaysia",
    )
    assert address_text_agreement(
        "No 51 Jalan LEP 5/12 Taman Lestari Putra Seri Kembanagan",
        "5/12 Jalan LEP 6, 43300 Seri Kembangan, SGR, Malaysia",
    )
    assert address_text_agreement(
        "No 9, Garden Manor, Off Sierramas Utama, Sierramas, 47000 Sungai Buluh, Selangor",
        "Jalan Sierramas Utama, 47000 Sungai Buloh, SGR, Malaysia",
    )
    assert address_text_agreement(
        "3-10 Gardenview Residence, Persiaran Ceria",
        "Gardenview Residence, Cyber 12, Cyberjaya, 63000 Sepang, Selangor, Malaysia",
    )
    assert address_text_agreement(
        "08-26 Residensi plantium teratai jln kuraman kg kuatan kl",
        "08-26 Jalan Kuraman, Setapak, 53000 Kuala Lumpur, Malaysia",
    )


def test_text_agreement_tier_preserves_postcode_conflict_as_uncertainty():
    assert analysis_tier({
        "input_address": "No.4 Jalan Bangsar 59200 KL",
        "formatted": "4 Jalan Bangsar, Bangsar, 50470 Kuala Lumpur, Malaysia",
        "result_type": "street", "postcode_agrees": False,
        "confidence": 0.8, "match_type": "full_match",
        "latitude": 3.1, "longitude": 101.7,
    }) == "text_agreement_candidate"


def test_postcode_reference_distance_accepts_nearby_and_rejects_far_conflicts():
    base = {
        "input_address": "Residensi Example 55200 Kuala Lumpur",
        "formatted": "Residensi Example, Kuala Lumpur, Malaysia",
        "result_type": "amenity", "postcode_agrees": False,
        "confidence": 0.5, "match_type": "full_match",
        "latitude": 3.1, "longitude": 101.7,
    }
    assert analysis_tier({**base, "postcode_reference_distance_km": 3.0}) == \
        "proximity_candidate"
    assert analysis_tier({**base, "postcode_reference_distance_km": 13.0}) == \
        "manual_review"


def test_verified_peer_address_match_is_an_area_candidate():
    assert analysis_tier({
        "input_address": "alternate address spelling",
        "formatted": "trusted peer provider result",
        "latitude": 3.1, "longitude": 101.7,
        "peer_address_agreement": True,
        "postcode_agrees": None,
    }) == "peer_address_candidate"


def test_transient_google_hint_only_creates_coarse_area_without_text_agreement():
    assert analysis_tier({
        "input_address": "Pelangi Heights",
        "formatted": "71700 Mantin, Negeri Sembilan, Malaysia",
        "latitude": 2.8, "longitude": 101.8,
        "google_places_hint_agreement": True,
        "postcode_agrees": None,
    }) == "google_hinted_area_candidate"
    assert analysis_tier({
        "input_address": "Example 43000 Kajang",
        "formatted": "71700 Mantin, Negeri Sembilan, Malaysia",
        "latitude": 2.8, "longitude": 101.8,
        "google_places_hint_agreement": True,
        "postcode_agrees": False,
    }) == "manual_review"
    assert analysis_tier({
        "input_address": "Sample Residence",
        "formatted": "Example Area, Kuala Lumpur, Malaysia",
        "latitude": 3.1, "longitude": 101.7,
        "google_places_hint_agreement": True,
        "google_place_within_1km": True,
        "postcode_agrees": None,
    }) == "google_hinted_area_candidate"


def test_text_agreement_takes_priority_over_google_hint_and_distance():
    assert analysis_tier({
        "input_address": "S2C 2-6, One Ampang Avenue, South View",
        "formatted": "South View One Ampang Avenue, 68000 Ampang Jaya, SGR, Malaysia",
        "result_type": "building", "confidence": 0.3,
        "match_type": "match_by_building", "postcode_agrees": None,
        "latitude": 3.1, "longitude": 101.7,
        "google_places_hint_agreement": True,
        "google_place_within_1km": True,
    }) == "area_analysis_candidate"
