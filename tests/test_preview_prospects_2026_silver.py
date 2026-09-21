"""Synthetic Bronze responses only. No real credentials or network calls."""
import runpy
from pathlib import Path
from unittest.mock import MagicMock

import dotenv
import pandas as pd
import pytest
import sqlalchemy

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/preview_prospects_2026_silver.py"


@pytest.fixture
def bronze(monkeypatch):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a: False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://synthetic:secret@invalid/db")
    monkeypatch.setenv("NOMOBUG_WAREHOUSE", "neon")
    engine = MagicMock()
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *a, **k: engine)
    headers = ["No", "NO TELEFON", "ENGAGE", "1st F/UP", "2nd F/UP", "3rd F/UP", "4th F/UP", "5th F/UP", ""]
    rows = [
        ["", "", "", "auto", "", "", "", "", ""],
        ["1", "", "", "auto", "", "", "", "", ""],
        ["2", "00123", "23 August", "", "", "", "", "", ""],
        ["3", "00123", "2026-99-99", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "private-unknown"],
        ["", "", "", "", "", "", "", "", "   "],
    ]
    header_map = [{"dataframe_column": f"source_column_{i:03d}", "original_header": h} for i, h in enumerate(headers, 1)]
    batch = pd.DataFrame([dict(snapshot_id="synthetic-id", extracted_at="2026-09-03T00:00:00Z",
                               source_row_count=len(rows), source_column_count=len(headers), header_map=header_map)])
    stored = pd.DataFrame({"source_sheet_row": list(range(2, 8)), "raw_values": rows})
    queries = []
    def read_sql(query, connection, **kwargs):
        queries.append(str(query))
        return batch if len(queries) == 1 else stored
    monkeypatch.setattr(pd, "read_sql", read_sql)
    return batch, stored, engine, queries


def test_preview_preserves_values_and_flags_shapes_only(bronze, capsys):
    _, _, engine, queries = bronze
    result = runpy.run_path(str(SCRIPT))
    assert result["preview_df"]["row_class"].tolist() == [
        "followup_only_placeholder", "numbered_only_placeholder", "prospect_candidate",
        "prospect_candidate", "other_values_needs_review", "blank_returned_row"]
    assert result["preview_df"].loc[3, "first_reply_format"] == "iso_year_month_day_shape"
    assert result["preview_df"].loc[2, "first_reply_format"] == "day_named_month_no_year"
    assert result["df"].loc[2, "source_column_002"] == "00123"
    assert result["df"].loc[5, "source_column_009"] == "   "
    assert len(result["df"]) == 6
    connection = engine.connect.return_value.__enter__.return_value
    assert "READ ONLY" in str(connection.execute.call_args_list[0].args[0])
    assert all(q.strip().startswith("SELECT") for q in queries)
    output = capsys.readouterr().out
    for private in ["00123", "private-unknown", "secret", "synthetic-id", "23 August"]:
        assert private not in output
    engine.dispose.assert_called_once()


def test_all_column_profile_uses_candidates_and_preserves_raw(bronze, capsys):
    batch, stored, _, _ = bronze
    batch.iloc[0]["header_map"][-1]["original_header"] = "PLATFORM"
    stored.iloc[2]["raw_values"][-1] = " Ads  Website "
    stored.iloc[3]["raw_values"][-1] = "ads website"
    result = runpy.run_path(str(SCRIPT))
    profile = result["field_profile"]
    assert len(profile) == 9
    assert (profile["filled"] + profile["blank"]).eq(2).all()
    platform = profile.iloc[-1]
    assert platform["distinct_raw"] == 2
    assert platform["distinct_comparison"] == 1
    assert platform["outer_whitespace"] == 1
    assert result["df"].loc[2, "source_column_009"] == " Ads  Website "
    assert result["repeat_phone_rows"] == 2
    assert result["repeat_phone_values"] == 1
    assert "Ads  Website" not in capsys.readouterr().out


def test_phone_structure_is_not_silent_normalisation(bronze):
    _, stored, _, _ = bronze
    stored.iloc[2]["raw_values"][1] = "+60 (12)-345"
    stored.iloc[3]["raw_values"][1] = "two/numbers"
    result = runpy.run_path(str(SCRIPT))
    assert result["phone_shapes"].tolist() == ["spaces_brackets_or_hyphens", "other_needs_review"]
    assert result["df"].loc[2, "source_column_002"] == "+60 (12)-345"


def test_broken_lineage_stops(bronze):
    _, stored, _, _ = bronze
    stored.loc[0, "source_sheet_row"] = 99
    with pytest.raises(SystemExit, match="shape/lineage"):
        runpy.run_path(str(SCRIPT))


def test_duplicate_required_header_stops(bronze):
    batch, _, _, _ = bronze
    batch.iloc[0]["header_map"][-1]["original_header"] = "ENGAGE"
    with pytest.raises(SystemExit, match="missing or duplicated"):
        runpy.run_path(str(SCRIPT))


def test_bigquery_backend_uses_same_profile_without_neon(bronze, monkeypatch):
    batch, stored, engine, queries = bronze
    original_run = runpy.run_path
    monkeypatch.setenv("NOMOBUG_WAREHOUSE", "bigquery")
    monkeypatch.setattr(runpy, "run_path", lambda *a: {"batch": batch.iloc[0], "stored_df": stored})
    result = original_run(str(SCRIPT))
    assert result["warehouse"] == "bigquery"
    assert len(result["df"]) == 6
    engine.connect.assert_not_called()
    assert queries == []
