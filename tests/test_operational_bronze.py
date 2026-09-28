"""Mock-only loader checks: no Google access or credentials."""
import json
import runpy
from pathlib import Path
from unittest.mock import MagicMock
import pandas as pd
import pytest
from google.api_core.exceptions import NotFound

core = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/operational_bronze_core.py'))

def sample():
    df = pd.DataFrame({'source_sheet_row': [5, 6, 7], 'source_column_001': ['001', '', '001']})
    lineage = {'spreadsheet_id': 'test', 'workbook': 'Test', 'header_row': 4,
        'started_at': '2026-09-01T00:00:00Z', 'extracted_at': '2026-09-01T00:00:01Z'}
    return df, lineage

def prepared():
    df, lineage = sample()
    return core['prepare_snapshot']('SALES', df, {'source_column_001': 'ID'}, lineage, ['ID'], 'sales')

def test_hash_ignores_read_time_but_not_values():
    df, lineage = sample()
    first = prepared()
    lineage['extracted_at'] = '2026-09-02T00:00:01Z'
    second = core['prepare_snapshot']('SALES', df, {'source_column_001': 'ID'}, lineage, ['ID'], 'sales')
    assert first['table_name'] == second['table_name']
    df.loc[0, 'source_column_001'] = '1'
    third = core['prepare_snapshot']('SALES', df, {'source_column_001': 'ID'}, lineage, ['ID'], 'sales')
    assert third['table_name'] != first['table_name']

@pytest.mark.parametrize('fault', ['header', 'row', 'empty'])
def test_source_guard(fault):
    df, lineage = sample()
    header = 'WRONG' if fault == 'header' else 'ID'
    if fault == 'row':
        df.loc[0, 'source_sheet_row'] = 99
    if fault == 'empty':
        df = df.iloc[:0]
    with pytest.raises(ValueError):
        core['prepare_snapshot']('SALES', df, {'source_column_001': header}, lineage, ['ID'], 'sales')

def mock_table(snapshot):
    return MagicMock(schema=snapshot['schema'], description=json.dumps(snapshot['metadata']))

def test_load_then_retry_preserves_duplicates_and_blanks():
    snap = prepared()
    client = MagicMock()
    table = mock_table(snap)
    client.get_table.side_effect = [NotFound('missing'), table]
    client.list_rows.return_value = list(reversed(snap['records']))
    result = core['load_and_verify'](client, 'test-project', 'US', snap)
    assert result['rows'] == 3 and result['status'] == 'LOADED'
    assert client.load_table_from_json.call_args.kwargs['job_config'].write_disposition == 'WRITE_EMPTY'
    client.get_table.side_effect = None
    client.get_table.return_value = table
    client.load_table_from_json.reset_mock()
    assert core['load_and_verify'](client, 'test-project', 'US', snap)['status'] == 'REUSED'
    client.load_table_from_json.assert_not_called()
    client.query.assert_not_called()

def test_stored_value_mismatch_stops():
    snap = prepared()
    client = MagicMock()
    client.get_table.return_value = mock_table(snap)
    client.list_rows.return_value = snap['records'][:-1]
    with pytest.raises(ValueError, match='Stored rows'):
        core['load_and_verify'](client, 'test-project', 'US', snap)

def test_header_description_mismatch_stops():
    snap = prepared()
    client = MagicMock()
    table = mock_table(snap)
    table.schema = []
    client.get_table.return_value = table
    with pytest.raises(ValueError, match='Stored schema'):
        core['load_and_verify'](client, 'test-project', 'US', snap)
