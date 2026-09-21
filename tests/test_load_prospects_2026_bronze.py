"""Offline loader tests: no real Google/Neon access or private .env reads."""
import runpy
from pathlib import Path
from unittest.mock import MagicMock

import dotenv
import pandas as pd
import psycopg
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/neon/load_prospects_2026_bronze.py"
RUN_SCRIPT = runpy.run_path


@pytest.fixture
def loader(monkeypatch):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a: False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://synthetic:secret@invalid/db")
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--upload"])
    source = {
        "df": pd.DataFrame({"source_sheet_row": [2, 3, 4], "source_column_001": ["00123", "", "00123"]}),
        "columns": ["source_column_001"],
        "header_map": pd.DataFrame({"dataframe_column": ["source_column_001"], "original_header": ["NO TELEFON"]}),
        "spreadsheet_id": "synthetic-id", "tab_name": "2026",
        "extraction_started_at": "2026-09-03T00:00:00+00:00",
        "extracted_at": "2026-09-03T00:00:01+00:00",
    }
    monkeypatch.setattr(runpy, "run_path", lambda *a: source)
    connect = MagicMock()
    monkeypatch.setattr(psycopg, "connect", connect)
    connection = connect.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("new",)
    cursor.fetchall.return_value = [(2, ["00123"]), (3, [""]), (4, ["00123"])]
    return source, connect, cursor


def test_new_snapshot_preserves_blanks_repeats_and_hides_values(loader, capsys):
    _, connect, cursor = loader
    result = RUN_SCRIPT(str(SCRIPT))
    assert result["new_snapshot"] is True
    records = cursor.executemany.call_args.args[1]
    assert [record[1] for record in records] == [2, 3, 4]
    assert [record[2].obj for record in records] == [["00123"], [""], ["00123"]]
    assert connect.call_args.kwargs["sslmode"] == "require"
    output = capsys.readouterr().out
    assert "New snapshot committed" in output
    assert "00123" not in output and "secret" not in output


def test_identical_content_skips_rows_even_with_new_timestamp(loader):
    source, _, cursor = loader
    first = RUN_SCRIPT(str(SCRIPT))
    cursor.executemany.reset_mock()
    cursor.fetchone.return_value = None
    source["extracted_at"] = "2026-09-04T00:00:01+00:00"
    second = RUN_SCRIPT(str(SCRIPT))
    assert second["snapshot_id"] == first["snapshot_id"]
    cursor.executemany.assert_not_called()


def test_verification_failure_exits_transaction_with_error(loader):
    _, connect, cursor = loader
    cursor.fetchall.return_value = []
    with pytest.raises(SystemExit, match="could not be confirmed"):
        RUN_SCRIPT(str(SCRIPT))
    assert connect.return_value.__exit__.call_args.args[0] is ValueError


def test_no_flag_prevents_connection(loader, monkeypatch):
    _, connect, _ = loader
    monkeypatch.setattr("sys.argv", [str(SCRIPT)])
    with pytest.raises(SystemExit, match="No upload"):
        RUN_SCRIPT(str(SCRIPT))
    connect.assert_not_called()


def test_changed_content_changes_snapshot_id(loader):
    source, _, cursor = loader
    first = RUN_SCRIPT(str(SCRIPT))
    source["df"].loc[0, "source_column_001"] = "changed"
    cursor.fetchall.return_value = [(2, ["changed"]), (3, [""]), (4, ["00123"])]
    second = RUN_SCRIPT(str(SCRIPT))
    assert second["snapshot_id"] != first["snapshot_id"]
