"""Live read-only DataFrame preview. No warehouse writes or raw exports."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import pandas as pd

root = Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):
    source = runpy.run_path(str(root / 'scripts/profile_b2b_sales_payments.py'))
rules = runpy.run_path(str(root / 'scripts/sales_payment_rules.py'))
sales = source['frames']['SALES'].copy()
payments = source['frames']['PAYMENTS'].copy()

# Snapshot-scoped IDs are lineage, not permanent bank transaction identifiers.
snapshot = hashlib.sha256(json.dumps({
    'headers': source['header_maps']['PAYMENTS'],
    'rows': payments.to_dict('records'),
}, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
payments['payment_record_id'] = snapshot + ':' + payments['source_sheet_row'].astype(str)
payments['amount_rm'] = payments['source_column_003'].map(rules['parse_rm_amount'])
parsed = payments['source_column_002'].map(rules['parse_sales_references'])
payments['reference_status'] = parsed.map(lambda item: item[1])

# Only structurally valid SINGLE sales IDs enter the lookup; collisions stay flagged.
sales_parsed = sales['source_column_007'].map(rules['parse_sales_references'])
sales_keys = sales_parsed.map(lambda item: item[0][0] if item[1] == 'single' else None)
sales_counts = sales_keys.dropna().value_counts()
link_rows = []
for payment_id, (ids, status) in zip(payments['payment_record_id'], parsed):
    for sale_id in ids:
        count = int(sales_counts.get(sale_id, 0))
        link_rows.append({
            'payment_record_id': payment_id,
            'sales_record_id': sale_id,
            'sales_match_status': 'matched' if count == 1 else 'missing' if count == 0 else 'ambiguous',
            'reference_status': status,
            # Deliberately no payment amount in this bridge: no double counting.
            'allocated_amount_rm': None,
        })
links = pd.DataFrame(link_rows, columns=[
    'payment_record_id', 'sales_record_id', 'sales_match_status',
    'reference_status', 'allocated_amount_rm',
])

assert len(payments) == len(source['frames']['PAYMENTS'])
assert payments['payment_record_id'].is_unique
assert not links.duplicated(['payment_record_id', 'sales_record_id']).any()
assert links['payment_record_id'].isin(payments['payment_record_id']).all()
assert links['allocated_amount_rm'].isna().all()
assert 'amount_rm' not in links.columns
print('PAYMENT/LINK PREVIEW — no uploads')
print('All raw payment rows retained:', len(payments))
print('Reference classifications:', payments['reference_status'].value_counts().to_dict())
print('Link rows:', len(links))
print('Link lookup results:', links['sales_match_status'].value_counts().to_dict())
print('Unparseable amounts across ALL returned rows:', int(payments['amount_rm'].isna().sum()))
print('Row preservation / unique snapshot keys / unique links / no copied amounts: PASS')
print('Amounts remain on payments only; no totals or per-sale allocations asserted.')
print('PREVIEW PASS. Google Sheets, BigQuery and Neon unchanged.')
