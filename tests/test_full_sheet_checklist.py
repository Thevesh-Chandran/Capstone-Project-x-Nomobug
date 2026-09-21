import csv
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]

def test_full_checklist_covers_nine_tabs_and_205_positions():
    with (ROOT / 'config/full_sheet_column_checklist.csv').open(encoding='utf-8', newline='') as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 205
    expected = {'2026': 24, 'B2B FOLLOW UP': 25, 'SALES': 43, 'PAYMENTS': 12,
        'PAYMENT LINK': 9, 'WARRANTY CLAIM': 18, 'Commercial Clients': 30,
        'REFUND': 11, 'Recurring Payments': 33}
    assert dict(Counter(row['tab'] for row in rows)) == expected
    assert len({(row['tab'], row['column_position']) for row in rows}) == 205
    assert all(row['remaining_check'] for row in rows)
    bank = [row for row in rows if row['tab'] == 'REFUND' and 'Bank' in row['source_header']]
    assert len(bank) == 2 and all(row['column_treatment'] == 'exclude_from_analytics' for row in bank)

def test_operational_dictionary_has_all_80_raw_aliases():
    with (ROOT / 'config/operational_column_dictionary.csv').open(encoding='utf-8', newline='') as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 80
    assert len({(r['source_tab'], r['readable_raw_name']) for r in rows}) == 80
    sql = (ROOT / 'dbt/macros/operational_raw_aliases.sql').read_text(encoding='utf-8')
    for model in ['b2b_follow_up', 'sales', 'payments']:
        sql += (ROOT / f'dbt/models/{model}.sql').read_text(encoding='utf-8')
    assert all('as ' + row['readable_raw_name'] in sql for row in rows)
