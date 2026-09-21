"""Offline storage-check tests, using only synthetic results."""
import runpy
from pathlib import Path
from unittest.mock import MagicMock

import dotenv
import pandas as pd
import pytest
import sqlalchemy

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/neon/check_neon_storage.py"


@pytest.mark.parametrize("stored,expected_status", [(3, "PASS"), (2, "REVIEW REQUIRED")])
def test_storage_read_only_counts_and_privacy(monkeypatch, capsys, stored, expected_status):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a: False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://synthetic:secret@invalid/db")
    engine = MagicMock()
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *a, **k: engine)
    results = iter([
        pd.DataFrame({"database_bytes": [1048576]}),
        pd.DataFrame({"table_name": ["prospects_2026_batches", "prospects_2026_rows"], "total_bytes": [8192, 32768]}),
        pd.DataFrame({"loaded_at_utc": ["2026-09-03T00:00:00Z"], "expected_rows": [3], "stored_rows": [stored]}),
    ])
    queries = []
    def fake_read(query, connection):
        queries.append(str(query))
        return next(results)
    monkeypatch.setattr(pd, "read_sql", fake_read)
    result = runpy.run_path(str(SCRIPT))
    connection = engine.connect.return_value.__enter__.return_value
    assert "READ ONLY" in str(connection.execute.call_args_list[0].args[0])
    assert all(query.strip().startswith("SELECT") for query in queries)
    assert result["database_df"].loc[0, "database_mib"] == 1
    output = capsys.readouterr().out
    assert expected_status in output
    assert "secret" not in output and "invalid" not in output
    engine.dispose.assert_called_once()
