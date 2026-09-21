import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from inspect_calendar_address_blocks import address_block, normalized_candidate_key, POSTCODE


def test_unlabelled_multiline_postcode_not_phone():
    description = (
        "Example Customer\nNo. 9, Jln Contoh 1/2,\n"
        "Taman Contoh,\n58000 Kuala Lumpur\n\n011-0000 0000"
    )
    block, _ = address_block(description, "No. 9, Jln Contoh 1/2,")
    assert block == "No. 9, Jln Contoh 1/2,\nTaman Contoh,\n58000 Kuala Lumpur"
    assert POSTCODE.search(block).group() == "58000"
    assert "011-0000" not in block


def test_html_break_and_no_postcode():
    description = (
        "Example Customer<br>no 7 jalan contoh 6/1, Cheras<br><br>"
        "0120000000<br><a href='mailto:a@example.com'>a@example.com</a>"
    )
    block, _ = address_block(description, "no 7 jalan contoh 6/1, Cheras")
    assert block == "no 7 jalan contoh 6/1, Cheras"
    assert not POSTCODE.search(block)


def test_blank_stops_before_contact():
    block, _ = address_block("Alamat: Jalan 5, 57000 KL\n\nPhone: 0123456789", "Jalan 5, 57000 KL")
    assert block == "Jalan 5, 57000 KL"


def test_no_extracted_line_stays_unknown():
    assert address_block("Phone: 0123456789", None) == (None, "no_extracted_line")


def test_candidate_key_normalizes_format_not_different_house():
    assert normalized_candidate_key("No. 9, Jalan Contoh\n58000 KL") == \
        normalized_candidate_key("no 9 jalan contoh 58000 kl")
    assert normalized_candidate_key("No. 10, Jalan Contoh 58000 KL") != \
        normalized_candidate_key("No. 9, Jalan Contoh 58000 KL")
    assert normalized_candidate_key("店 9, Jalan Contoh") != \
        normalized_candidate_key("9, Jalan Contoh")
