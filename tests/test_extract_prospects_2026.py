"""Synthetic API fixtures only; never contact Google or read private configuration."""

import json
import runpy
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import dotenv
import google.oauth2.credentials
import googleapiclient.discovery
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_prospects_2026.py"


@pytest.fixture
def fake_google(tmp_path, monkeypatch):
    # Explicit overrides prevent any access to real tokens, source IDs or .env.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    for key, payload in {
        "NOMOBUG_GOOGLE_TOKEN": {},
        "NOMOBUG_GOOGLE_SOURCE_IDS": {"spreadsheet_ids": ["synthetic-id"]},
        "NOMOBUG_GOOGLE_METADATA": {"spreadsheets": [{
            "spreadsheetId": "synthetic-id", "properties": {"title": "Prospects List - Nomobug"}
        }]},
    }.items():
        file = tmp_path / (key + ".json")
        file.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setenv(key, str(file))
    credentials = MagicMock(valid=True)
    monkeypatch.setattr(google.oauth2.credentials.Credentials, "from_authorized_user_file",
                        lambda *args: credentials)
    service = MagicMock()
    monkeypatch.setattr(googleapiclient.discovery, "build", lambda *args, **kwargs: service)
    sheets = service.spreadsheets.return_value
    sheets.get.return_value.execute.return_value = {
        "properties": {"title": "Prospects List - Nomobug"},
        "sheets": [{"properties": {"title": "2026", "sheetId": 1}}],
    }
    sheets.values.return_value.get.return_value.execute.return_value = {
        "values": [["No", "NO TELEFON", "STATUS", "STATUS", ""],
                   ["1", "00123", "OPEN"], [], ["1", "00123", "OPEN"],
                   ["2", "00123", "CLOSED", "", "", "extra cell"]]
    }
    return service, credentials, tmp_path


def test_preserves_all_rows_headers_and_values(fake_google, capsys):
    service, _, _ = fake_google
    result = runpy.run_path(str(SCRIPT))
    df = result["df"]
    assert len(df) == 4
    assert df["source_sheet_row"].tolist() == [2, 3, 4, 5]
    assert df.loc[0, "source_column_002"] == "00123"
    assert df.loc[3, "source_column_002"] == "00123"  # legitimate repeat retained
    assert df.loc[3, "source_column_006"] == "extra cell"  # wider than header
    assert result["header_map"]["original_header"].tolist() == ["No", "NO TELEFON", "STATUS", "STATUS", "", ""]
    assert df.columns.is_unique
    assert result["blank_rows"].sum() == 1
    assert result["exact_repeats"] == 1
    output = capsys.readouterr().out
    assert "00123" not in output and "synthetic-id" not in output
    assert "Row-count check: PASS" in output
    request = service.spreadsheets.return_value.values.return_value.get.call_args.kwargs
    assert request["range"] == "'2026'" and request["valueRenderOption"] == "FORMATTED_VALUE"
    service.close.assert_called_once()


@pytest.mark.parametrize("values, message", [([], "no header/data"), ([["Wrong header"]], "NO TELEFON")])
def test_empty_or_changed_header_stops(fake_google, values, message):
    service, _, _ = fake_google
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {"values": values}
    with pytest.raises(SystemExit, match=message):
        runpy.run_path(str(SCRIPT))


def test_header_only_is_not_hidden_failure(fake_google):
    service, _, _ = fake_google
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {"values": [["NO TELEFON"]]}
    result = runpy.run_path(str(SCRIPT))
    assert result["df"].empty
    assert result["column_profile"]["blank_percent"].isna().all()


def test_completeness_preserves_values_and_original_headers(fake_google, capsys):
    service, _, _ = fake_google
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [["NO TELEFON", "STATUS\nOPEN / CLOSED", ""],
                   ["00123", "   ", "0"], ["00123", "N/A", "FALSE"], []]
    }
    result = runpy.run_path(str(SCRIPT))
    profile = result["column_profile"]
    assert profile["filled_cells"].tolist() == [2, 1, 2]
    assert profile["blank_cells"].tolist() == [1, 2, 1]
    assert profile["blank_percent"].tolist() == [33.33, 66.67, 33.33]
    assert profile["distinct_nonblank"].tolist() == [1, 1, 2]
    assert profile["original_header"].tolist() == ["NO TELEFON", "STATUS OPEN / CLOSED", "(blank header)"]
    assert result["header_map"].loc[1, "original_header"] == "STATUS\nOPEN / CLOSED"
    assert result["df"].loc[0, "source_column_002"] == "   "
    assert "00123" not in capsys.readouterr().out


def test_template_candidates_preserve_repeats_and_unknown_values(fake_google):
    service, _, _ = fake_google
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [["1st F/UP", "NO TELEFON", " ENGAGE ", "No", ""],
                   ["24-Aug"], ["24-Aug"],
                   ["24-Aug", "00123"], ["24-Aug", "", "23 August"],
                   ["24-Aug", "", "", "5"],
                   ["24-Aug", "", "", "", "unknown"], [], ["   "]]
    }
    result = runpy.run_path(str(SCRIPT))
    assert result["row_flags"]["row_class"].tolist() == [
        "followup_only_candidate", "followup_only_candidate",
        "phone_or_first_reply_present", "phone_or_first_reply_present",
        "other_values_needs_review", "other_values_needs_review",
        "blank_returned_row", "blank_returned_row",
    ]
    assert len(result["df"]) == 8
    assert result["exact_repeats"] == 1
    assert result["row_summary"]["rows"].sum() == 8
    assert result["df"].loc[7, "source_column_001"] == "   "
    assert "row_class" not in result["df"].columns


def test_review_group_counts_without_disclosing_values(fake_google, capsys):
    service, _, _ = fake_google
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [["NO TELEFON", "No", "REMARK", "1st F/UP", ""],
                   ["", "1", "   ", "24-Aug"],
                   ["", "2", "private-remark", "24-Aug"],
                   ["", "", "", "", "private-unknown"],
                   ["00123", "3", "private-phone-row"], ["", "", "", "24-Aug"]]
    }
    result = runpy.run_path(str(SCRIPT))
    assert result["review_mask"].sum() == 3
    assert result["number_only_count"] == 1
    assert result["other_detail_count"] == 2
    assert result["review_profile"]["filled_in_review_rows"].tolist() == [2, 1, 2, 1]
    assert len(result["df"]) == 5
    assert result["df"].loc[0, "source_column_003"] == "   "
    output = capsys.readouterr().out
    for private_value in ["private-remark", "private-unknown", "private-phone-row", "00123", "24-Aug"]:
        assert private_value not in output
    assert "Review-group count check: PASS" in output


def test_unapproved_workbook_stops_before_api(fake_google, monkeypatch):
    service, _, folder = fake_google
    file = folder / "denied.json"
    file.write_text('{"spreadsheet_ids": []}', encoding="utf-8")
    monkeypatch.setenv("NOMOBUG_GOOGLE_SOURCE_IDS", str(file))
    with pytest.raises(SystemExit, match="approved"):
        runpy.run_path(str(SCRIPT))
    service.spreadsheets.assert_not_called()


def test_expired_auth_error_does_not_expose_details(fake_google):
    service, credentials, _ = fake_google
    credentials.valid = False
    credentials.refresh.side_effect = RefreshError("synthetic-secret")
    with pytest.raises(SystemExit, match="authentication failed") as error:
        runpy.run_path(str(SCRIPT))
    assert "synthetic-secret" not in str(error.value)
    service.spreadsheets.assert_not_called()


def test_api_error_does_not_expose_response(fake_google):
    service, _, _ = fake_google
    request = service.spreadsheets.return_value.values.return_value.get.return_value
    request.execute.side_effect = HttpError(MagicMock(status=403, reason="Forbidden"), b'{"error":{"message":"synthetic-secret"}}')
    with pytest.raises(SystemExit, match="HTTP 403") as error:
        runpy.run_path(str(SCRIPT))
    assert "synthetic-secret" not in str(error.value)
    service.close.assert_called_once()
