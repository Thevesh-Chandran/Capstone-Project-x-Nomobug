from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pilot_geoapify_calendar import analysis_tier


def test_manual_user_verified_coordinate_is_accepted() -> None:
    record = {
        "input_address": "Example residence",
        "formatted": "Unrelated stale provider result",
        "latitude": 3.1,
        "longitude": 101.7,
        "coordinate_source": "manual_user_verified",
    }
    assert analysis_tier(record) == "manual_verified"


def test_external_area_reference_is_not_claimed_as_property_precision() -> None:
    record = {
        "input_address": "9 Persiaran Titiwangsa",
        "formatted": "Persiaran Titiwangsa, Kuala Lumpur",
        "latitude": 3.1798,
        "longitude": 101.7025,
        "coordinate_source": "external_area_reference",
    }
    assert analysis_tier(record) == "area_reference_verified"
