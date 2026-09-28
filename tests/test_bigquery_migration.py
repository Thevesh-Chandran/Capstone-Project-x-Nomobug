"""Mock-only migration tests: never use ADC, Google APIs or private .env."""
import json
import runpy
from pathlib import Path
from unittest.mock import MagicMock

import dotenv
import pandas as pd
import pytest
from google.cloud import bigquery
from google.api_core.exceptions import NotFound

ROOT = Path(__file__).resolve().parents[1]
RUN = runpy.run_path


@pytest.fixture
def bq(monkeypatch):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a: False)
    monkeypatch.setenv("NOMOBUG_BQ_PROJECT", "test-project")
    monkeypatch.setenv("NOMOBUG_BQ_LOCATION", "US")
    monkeypatch.setenv("NOMOBUG_BQ_UPLOAD_APPROVED", "yes")
    monkeypatch.setattr("sys.argv", ["loader", "--upload"])
    source = {
        "df": pd.DataFrame({"source_sheet_row": [2, 3, 4], "source_column_001": ["00123", "", "00123"]}),
        "columns": ["source_column_001"], "spreadsheet_id": "private-id", "tab_name": "2026",
        "header_map": pd.DataFrame({"dataframe_column": ["source_column_001"], "original_header": ["NO TELEFON"]}),
        "extracted_at": "2026-09-03T00:00:01Z", "extraction_started_at": "2026-09-03T00:00:00Z",
    }
    contract = RUN(str(ROOT / 'scripts/prospects_source_contract.py'))
    columns = [f'source_column_{n:03d}' for n in range(1, 25)]
    for column in columns[1:]:
        source['df'][column] = ''
    source['columns'] = columns
    source['header_map'] = pd.DataFrame({'dataframe_column': columns, 'original_header': contract['EXPECTED_HEADERS']})
    monkeypatch.setattr(runpy, "run_path", lambda path: contract if Path(path).name == 'prospects_source_contract.py' else source)
    client = MagicMock()
    monkeypatch.setattr(bigquery, "Client", lambda **k: client)
    client.get_dataset.return_value = MagicMock(location="US", default_table_expiration_ms=None)
    client.list_tables.return_value = []
    table = MagicMock()
    client.get_table.side_effect = [NotFound("missing"), table]
    def load(records, table_id, job_config, **kwargs):
        table.schema = job_config.schema
        table.description = job_config.destination_table_description
        table.table_id = table_id.split(".")[-1]
        client.list_rows.return_value = records[::-1]  # No assumed API ordering.
        return MagicMock()
    client.load_table_from_json.side_effect = load
    return client, source, table


def test_bq_load_atomic_config_preserves_rows_and_retry_skips(bq, capsys):
    client, _, table = bq
    first = RUN(str(ROOT / "scripts/load_prospects_2026_bigquery.py"))
    config = client.load_table_from_json.call_args.kwargs["job_config"]
    assert config.write_disposition == "WRITE_EMPTY"
    assert first["returned"][0]["source_column_001"] == "00123"
    client.get_table.side_effect = None
    client.get_table.return_value = table
    client.load_table_from_json.reset_mock()
    second = RUN(str(ROOT / "scripts/load_prospects_2026_bigquery.py"))
    assert second["digest"] == first["digest"]
    assert not second["new_snapshot"]
    client.load_table_from_json.assert_not_called()
    client.query.assert_not_called()
    output = capsys.readouterr().out
    assert "00123" not in output and "private-id" not in output


def test_bq_approval_gate_prevents_upload(bq, monkeypatch):
    client, _, _ = bq
    monkeypatch.setenv("NOMOBUG_BQ_UPLOAD_APPROVED", "no")
    with pytest.raises(SystemExit, match="Upload blocked"):
        RUN(str(ROOT / "scripts/load_prospects_2026_bigquery.py"))
    client.get_dataset.assert_not_called()


def test_bq_snapshot_limit_stops_without_fallback(bq):
    client, _, _ = bq
    client.list_tables.return_value = [MagicMock(table_id=f"prospects_2026_{n}") for n in range(5)]
    with pytest.raises(SystemExit, match="Five raw snapshots"):
        RUN(str(ROOT / "scripts/load_prospects_2026_bigquery.py"))
    client.load_table_from_json.assert_not_called()


def test_bq_region_mismatch_stops(bq):
    client, _, _ = bq
    client.get_dataset.return_value.location = "EU"
    with pytest.raises(SystemExit, match="location mismatch"):
        RUN(str(ROOT / "scripts/load_prospects_2026_bigquery.py"))
    client.load_table_from_json.assert_not_called()


def test_bq_reader_reconstructs_shared_contract(bq):
    client, _, table = bq
    loaded = RUN(str(ROOT / "scripts/load_prospects_2026_bigquery.py"))
    client.get_table.side_effect = None
    client.get_table.return_value = table
    client.list_tables.return_value = [table]
    result = RUN(str(ROOT / "scripts/read_prospects_2026_bigquery.py"))
    assert result["stored_df"]["raw_values"].tolist() == [[value] + [''] * 23 for value in ['00123', '', '00123']]
    assert result["batch"]["snapshot_id"] == loaded["digest"]
    assert result["batch"]["header_map"][0]["original_header"] == "No"
    client.query.assert_not_called()


def test_bq_checker_metadata_only(bq):
    client, _, _ = bq
    RUN(str(ROOT / "scripts/check_bigquery_connection.py"))
    assert client.get_dataset.call_count == 6
    client.query.assert_not_called()
    client.create_dataset.assert_not_called()
