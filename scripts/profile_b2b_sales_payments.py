"""Read-only live API profiling; all returned rows retained in DataFrames.

No raw exports, warehouse uploads, source edits or automatic sign-in.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import GoogleAuthError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

root = Path(__file__).resolve().parents[1]
load_dotenv(root / '.env')
paths = {}
for name, default in {
    'NOMOBUG_GOOGLE_TOKEN': 'secrets/google_token.json',
    'NOMOBUG_GOOGLE_SOURCE_IDS': 'secrets/google_source_ids.json',
    'NOMOBUG_GOOGLE_METADATA': 'data/profiles/google_source_metadata.json',
}.items():
    path = Path(os.getenv(name) or default)
    paths[name] = path if path.is_absolute() else root / path

metadata = json.loads(paths['NOMOBUG_GOOGLE_METADATA'].read_text(encoding='utf-8-sig'))
approved = json.loads(paths['NOMOBUG_GOOGLE_SOURCE_IDS'].read_text(encoding='utf-8-sig'))['spreadsheet_ids']
try:
    credentials = Credentials.from_authorized_user_file(str(paths['NOMOBUG_GOOGLE_TOKEN']), [
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/calendar.readonly',
    ])
    if not credentials.valid:
        credentials.refresh(Request())
except (GoogleAuthError, ValueError, OSError):
    raise SystemExit('Sign-in needs renewal: python scripts/renew_google_access.py') from None

# These header rows come from the existing source inventory; verify below.
targets = [
    ('Prospects List - Nomobug', 'B2B FOLLOW UP', 1),
    ('SESSION & PAYMENT (NMB)- CHIA', 'SALES', 4),
    ('SESSION & PAYMENT (NMB)- CHIA', 'PAYMENTS', 1),
]
if globals().get('include_all_approved_tabs', False):
    targets += [('Prospects List - Nomobug', '2026', 1)]
    targets += [('SESSION & PAYMENT (NMB)- CHIA', tab, 1) for tab in [
        'PAYMENT LINK', 'WARRANTY CLAIM', 'Commercial Clients', 'REFUND', 'Recurring Payments',
    ]]
elif globals().get('include_all_operational_tabs', False):
    targets += [('SESSION & PAYMENT (NMB)- CHIA', tab, 1) for tab in [
        'PAYMENT LINK', 'WARRANTY CLAIM', 'Commercial Clients', 'REFUND', 'Recurring Payments',
    ]]
frames = {}
header_maps = {}
source_lineage = {}
service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
print('Live profiling started UTC:', datetime.now(timezone.utc).isoformat())
try:
    for workbook, requested_tab, header_row in targets:
        # Keep the canonical contract key separate from a decorative live title.
        tab = requested_tab
        matches = [s for s in metadata['spreadsheets'] if s['properties']['title'] == workbook]
        if len(matches) != 1 or matches[0]['spreadsheetId'] not in approved:
            raise SystemExit('Source selection is missing or ambiguous; stop for inventory review.')
        source_id = matches[0]['spreadsheetId']
        live = service.spreadsheets().get(spreadsheetId=source_id,
            fields='properties(title,locale,timeZone),sheets(properties(title))').execute(num_retries=2)
        live_titles = [s['properties']['title'] for s in live['sheets']]
        # Observed recurring tab sometimes has a decorative star; require one match.
        if requested_tab == 'Recurring Payments' and tab not in live_titles:
            alternatives = [t for t in live_titles if t.rstrip(' ⭐') == requested_tab]
            if len(alternatives) == 1:
                tab = alternatives[0]
        if live['properties']['title'] != workbook or tab not in live_titles:
            raise SystemExit('Live workbook/tab changed; stop for review.')
        started_at = datetime.now(timezone.utc).isoformat()
        values = service.spreadsheets().values().get(spreadsheetId=source_id,
            range="'" + tab.replace("'", "''") + "'", valueRenderOption='FORMATTED_VALUE',
            majorDimension='ROWS').execute(num_retries=2).get('values', [])
        source_lineage[requested_tab] = {'spreadsheet_id': source_id, 'workbook': workbook,
            'source_tab': tab,
            'header_row': header_row, 'started_at': started_at,
            'extracted_at': datetime.now(timezone.utc).isoformat()}
        if len(values) < header_row:
            raise SystemExit('Expected header row missing.')
        width = max(map(len, values))
        headers = values[header_row - 1] + [''] * (width - len(values[header_row - 1]))
        # Stable positional labels prevent duplicate/blank headers losing data.
        columns = [f'source_column_{n:03d}' for n in range(1, width + 1)]
        df = pd.DataFrame([row + [''] * (width - len(row)) for row in values[header_row:]], columns=columns)
        df.insert(0, 'source_sheet_row', range(header_row + 1, len(values) + 1))
        frames[requested_tab] = df
        header_maps[requested_tab] = dict(zip(columns, headers))
        print('\nSOURCE:', workbook, '/', requested_tab, '| live tab:', tab, '| header row:', header_row)
        print('Locale/timezone:', live['properties'].get('locale'), live['properties'].get('timeZone'))
        print('Returned data rows:', len(df), '| columns:', width)
        cleaned = df[columns].apply(lambda col: col.str.strip())
        print('Entirely blank returned rows:', int(cleaned.eq('').all(axis=1).sum()))
        print('Exact repeated rows beyond first:', int(df[columns].duplicated().sum()))
        profile = []
        for column, header in zip(columns, headers):
            nonblank = cleaned[column][cleaned[column].ne('')]
            profile.append({'column': column, 'header': ' '.join(header.split()),
                'filled': len(nonblank), 'blank': len(df) - len(nonblank),
                'distinct_trimmed': nonblank.nunique()})
        print(pd.DataFrame(profile).to_string(index=False))
except (GoogleAuthError, HttpError, OSError):
    raise SystemExit('Google read failed. No source or warehouse changes; do not paste tokens.') from None
finally:
    service.close()

# Verify the observed linking fields before using their positions below.
for tab, column, expected in [
    ('SALES', 'source_column_007', 'CUSTOMER ID'),
    ('PAYMENTS', 'source_column_002', 'CUSTOMER ID'),
    ('PAYMENTS', 'source_column_003', 'AMOUNT (RM)'),
    ('B2B FOLLOW UP', 'source_column_003', 'PHONE NO.'),
]:
    if ' '.join(header_maps[tab][column].upper().split()) != expected:
        raise SystemExit('Linking field changed; skip joins and review the headers.')

# Trim only: no numeric coercion, leading-zero removal or customer-ID guessing.
sales_ids = frames['SALES']['source_column_007'].str.strip()
payment_ids = frames['PAYMENTS']['source_column_002'].str.strip()
sales_counts = sales_ids[sales_ids.ne('')].value_counts()
payment_counts = payment_ids[payment_ids.ne('')].value_counts()
common_ids = sales_counts.index.intersection(payment_counts.index)
print('\nCUSTOMER ID LINK CHECK (exact after trimming; all dates):')
print('Sales rows with ID:', int(sales_counts.sum()), '| distinct IDs:', len(sales_counts))
print('Sales duplicated ID groups:', int(sales_counts.gt(1).sum()))
print('Payment rows with ID:', int(payment_counts.sum()), '| distinct IDs:', len(payment_counts))
print('Payment repeated ID groups:', int(payment_counts.gt(1).sum()))
print('Payment rows matching Sales ID:', int(payment_ids.isin(sales_counts.index).sum()))
print('Payment rows with nonblank unmatched ID:', int((payment_ids.ne('') & ~payment_ids.isin(sales_counts.index)).sum()))
print('Distinct unmatched payment IDs:', len(payment_counts.index.difference(sales_counts.index)))
print('Sales IDs with no payment ID match:', len(sales_counts.index.difference(payment_counts.index)))
print('Expected rows from an inner join on ID:', int((sales_counts[common_ids] * payment_counts[common_ids]).sum()))
print('Repeated payment IDs can be valid instalments. Do not sum Sales total after this join.')

for tab, key_column in [('SALES', 'source_column_007'), ('PAYMENTS', 'source_column_002'), ('B2B FOLLOW UP', 'source_column_003')]:
    df = frames[tab]
    candidate = df[key_column].str.strip().ne('')
    print('\nCANDIDATE QUALITY:', tab, '| key-present rows:', int(candidate.sum()))
    # No record removal: these are temporary profiling subsets, not Silver filters.
    raw = df.loc[candidate, list(header_maps[tab])]
    print('Exact repeated candidate rows beyond first:', int(raw.duplicated().sum()))
    if tab == 'PAYMENTS':
        amounts = df.loc[candidate, 'source_column_003'].str.strip()
        # Provisional syntax check, not final financial parsing (parentheses/currency need review).
        numeric = pd.to_numeric(amounts.str.replace(',', '', regex=False), errors='coerce')
        print('Amounts not parseable after comma removal:', int(numeric.isna().sum()))
        print('Zero amounts:', int(numeric.eq(0).sum()), '| negative amounts:', int(numeric.lt(0).sum()))
    if tab == 'B2B FOLLOW UP':
        phone = df.loc[candidate, key_column].str.strip()
        print('Distinct trimmed phones:', phone.nunique(), '| repeated phone groups:', int(phone.value_counts().gt(1).sum()))
        print('No Customer ID column observed: phone is a candidate link, not a verified sale match.')
        print('Status counts:', df.loc[candidate, 'source_column_007'].str.strip().value_counts().to_dict())

print('\nPROFILE READ COMPLETE. Counts cover all returned rows, not confirmed business records.')
print('Header mappings and row grain still require review before joins or loading.')
print('No raw files saved. Sheets, BigQuery and Neon unchanged.')
