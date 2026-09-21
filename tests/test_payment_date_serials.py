"""Date-sidecar lineage checks without API or warehouse calls."""
import runpy
from pathlib import Path

import pytest


prepare_rows = runpy.run_path(str(Path(__file__).resolve().parents[1] /
    'scripts/load_payment_date_serials.py'))['prepare_rows']


def stored_rows():
    return [
        {'source_sheet_row': 2, 'payment_date_raw': '31 December', 'sales_references_raw': 'CUST1'},
        {'source_sheet_row': 3, 'payment_date_raw': '1 January', 'sales_references_raw': 'CUST2'},
        {'source_sheet_row': 4, 'payment_date_raw': '', 'sales_references_raw': ''},
    ]


def test_preserves_serials_text_and_trailing_blanks():
    rows = prepare_rows(stored_rows(), [['31 December', 'CUST1'], ['1 January', 'CUST2']],
        [[45657, 'CUST1'], ['mistyped', 'CUST2']])
    assert [(row['unformatted_value'], row['unformatted_type']) for row in rows] == [
        ('45657', 'serial'), ('mistyped', 'text'), ('', 'blank')]


@pytest.mark.parametrize('formatted', [
    [['31 December', 'WRONG'], ['1 January', 'CUST2']],
    [['30 December', 'CUST1'], ['1 January', 'CUST2']],
])
def test_stale_live_row_is_rejected(formatted):
    with pytest.raises(ValueError, match='differs from Bronze'):
        prepare_rows(stored_rows(), formatted, [[45657], [45658]])


def test_new_live_rows_are_rejected():
    with pytest.raises(ValueError, match='more rows'):
        prepare_rows(stored_rows(), [[], [], [], []], [[], [], [], []])
