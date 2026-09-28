"""Read-only exception batch. Raw IDs/names remain in memory; print counts only."""
import contextlib
import io
from pathlib import Path
import runpy
import sys
import pandas as pd

root = Path(__file__).resolve().parents[1]
# Reuse the complete API read, suppress its long profile, and keep the DataFrames.
with contextlib.redirect_stdout(io.StringIO()):
    source = runpy.run_path(str(root / 'scripts/profile_b2b_sales_payments.py'))
sales = source['frames']['SALES']
payments = source['frames']['PAYMENTS']
headers = source['header_maps']
for tab, column, expected in [('SALES', 'source_column_008', 'AD'),
                              ('PAYMENTS', 'source_column_003', 'AMOUNT (RM)')]:
    if ' '.join(headers[tab][column].upper().split()) != expected:
        raise SystemExit('Required column changed; stop for mapping review.')

# Customer ID is the owner's sales-record ID, not a persistent person ID.
sales_ids = sales['source_column_007'].str.strip()
payment_ids = payments['source_column_002'].str.strip()
unmatched = payment_ids.ne('') & ~payment_ids.isin(sales_ids[sales_ids.ne('')])
exceptions = payments.loc[unmatched].copy()
print('UNMATCHED PAYMENTS:', len(exceptions), 'rows;', payment_ids[unmatched].nunique(), 'sales-record IDs')
print('Unmatched source row numbers:', exceptions['source_sheet_row'].tolist())

# Diagnostic comparisons only; NEVER rewrite or auto-match these IDs.
case_keys = sales_ids.str.upper()
compact_keys = case_keys.str.replace(r'\s+', '', regex=True)
print('Unmatched rows that match by case only:', int(payment_ids[unmatched].str.upper().isin(case_keys).sum()))
print('Unmatched rows that match after case/space removal:', int(payment_ids[unmatched].str.upper().str.replace(r'\s+', '', regex=True).isin(compact_keys).sum()))
print('Unmatched IDs numeric-only:', int(payment_ids[unmatched].str.fullmatch(r'\d+').sum()))
if '--review-values' in sys.argv:
    print('Private unmatched ID review (source row | recorded ID | compact SALES matches):')
    for index, row in payments.loc[unmatched].iterrows():
        raw_id = payment_ids.loc[index]
        compact = raw_id.upper().replace(' ', '')
        matches = sorted(set(sales_ids[compact_keys.eq(compact) & sales_ids.ne('')]))
        print(f"  {row['source_sheet_row']} | {raw_id!r} | {matches}")

amounts = payments['source_column_003'].str.strip()
candidate = payment_ids.ne('')
numeric = pd.to_numeric(amounts.str.replace(',', '', regex=False), errors='coerce')
invalid = candidate & numeric.isna()
print('\nAMOUNT EXCEPTIONS:', int(invalid.sum()))
print('Amount exception source rows:', payments.loc[invalid, 'source_sheet_row'].tolist())
# Syntax categories avoid dumping free text (which may contain private details).
syntax = pd.Series('OTHER_TEXT', index=amounts.index)
syntax.loc[amounts.eq('')] = 'BLANK'
syntax.loc[amounts.str.fullmatch(r'#[A-Z0-9/?!]+')] = 'SHEET_ERROR'
syntax.loc[amounts.str.fullmatch(r'(?i)RM\s*[\d,.]+')] = 'RM_PREFIX'
syntax.loc[amounts.str.fullmatch(r'\([\d,.]+\)')] = 'PARENTHESES'
syntax.loc[amounts.str.fullmatch(r'[-–—]+')] = 'DASH'
print('Exception syntax:', syntax[invalid].value_counts().to_dict())
if '--review-values' in sys.argv:
    print('Private amount review (source row | sales reference | recorded amount):')
    for index, row in payments.loc[invalid].iterrows():
        print(f"  {row['source_sheet_row']} | {payment_ids.loc[index]!r} | {amounts.loc[index]!r}")

raw_columns = list(headers['PAYMENTS'])
duplicates = payments.loc[candidate, raw_columns].duplicated(keep=False)
print('\nEXACT DUPLICATE PAYMENT CANDIDATES (all raw columns):')
print('Source rows:', payments.loc[candidate].loc[duplicates, 'source_sheet_row'].tolist())
if '--review-values' in sys.argv:
    for index, row in payments.loc[candidate].loc[duplicates].iterrows():
        print(f"  duplicate review: {row['source_sheet_row']} | {payment_ids.loc[index]!r} | "
              f"date={row['source_column_001']!r} | amount={amounts.loc[index]!r}")
print('No deletion: identical recorded values do not prove a duplicated receipt.')

ad = sales['source_column_008'].str.strip().str.upper().str.replace(r'\s+', ' ', regex=True)
possible_return = ad.str.contains(r'OLD|RETURN', regex=True)
print('\nRETURNING-CLIENT LABEL CANDIDATES (not yet automatically mapped):')
print(ad[sales_ids.ne('') & possible_return].value_counts().to_string())
print('Blank Ad among ID-present sales:', int((sales_ids.ne('') & ad.eq('')).sum()))
rules = runpy.run_path(str(root / 'scripts/sales_payment_rules.py'))
recorded_return = ad.map(rules['recorded_returning_client'])
print('Recorded returning-client signal rows:', int((sales_ids.ne('') & recorded_return).sum()))
print('Missing signal does not prove a new customer. B2B COLD is not OLD.')
strict_amount = amounts.map(rules['parse_rm_amount'])
print('Strict decimal parse exceptions among ID-present payments:', int((candidate & strict_amount.isna()).sum()))
print('EXCEPTION INSPECTION COMPLETE. No records changed, uploaded, deleted or exported.')
