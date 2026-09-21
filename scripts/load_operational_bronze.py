"""All eight operational source layouts checked before writes. Default is a live read-only plan."""
import argparse
import contextlib
import io
import os
from pathlib import Path
import runpy
from dotenv import load_dotenv
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.auth.exceptions import GoogleAuthError

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--upload', action='store_true')
args = parser.parse_args()
load_dotenv(root / '.env')
if args.upload and os.getenv('NOMOBUG_BQ_UPLOAD_APPROVED') != 'yes':
    raise SystemExit('Upload blocked: existing NOMOBUG_BQ_UPLOAD_APPROVED=yes gate is required.')
project = os.getenv('NOMOBUG_BQ_PROJECT', '').strip()
location = os.getenv('NOMOBUG_BQ_LOCATION', '').strip()
if project != 'profound-keel-500007-s4' or location.lower() != 'asia-southeast1':
    raise SystemExit('Unexpected project/region. No work performed.')
contracts = runpy.run_path(str(root / 'scripts/operational_source_contracts.py'))
core = runpy.run_path(str(root / 'scripts/operational_bronze_core.py'))
with contextlib.redirect_stdout(io.StringIO()):
    source = runpy.run_path(str(root / 'scripts/profile_b2b_sales_payments.py'),
        init_globals={'include_all_operational_tabs': True})
snapshots = []
try:
    for tab, expected in contracts['HEADERS'].items():
        snapshot = core['prepare_snapshot'](tab, source['frames'][tab], source['header_maps'][tab],
            source['source_lineage'][tab], expected, contracts['PREFIXES'][tab])
        snapshots.append(snapshot)
        print(tab, '| rows:', len(snapshot['records']), '| headers/positions: PASS')
except ValueError as error:
    raise SystemExit(str(error)) from None
if not args.upload:
    print('PLAN PASS. No uploads. Run with --upload to load these sources after checking the plan.')
    raise SystemExit(0)

client = bigquery.Client(project=project, location=location)
try:
    dataset = client.get_dataset(f'{project}.bronze')
    if dataset.location.lower() != location.lower() or dataset.default_table_expiration_ms is not None:
        raise ValueError('Dataset region/expiry mismatch')
    existing_names = [t.table_id for t in client.list_tables(dataset)]
    # Preflight every retention gate before writing the first table.
    for snapshot in snapshots:
        if snapshot['table_name'] not in existing_names:
            if sum(name.startswith(snapshot['prefix'] + '_') for name in existing_names) >= 5:
                raise ValueError('Five snapshots already stored for a source; retention review required')
    verified = []
    for snapshot in snapshots:
        result = core['load_and_verify'](client, project, location, snapshot)
        verified.append(result)
        print(result['status'], result['table'], '| rows:', result['rows'], '| exact values: PASS')
    print(f'OPERATIONAL BRONZE PASS: {len(verified)} verified snapshots. No Silver writes. Neon unchanged.')
except (GoogleAPICallError, GoogleAuthError, ValueError, TimeoutError):
    raise SystemExit('BATCH NOT CONFIRMED. Earlier tables or timed-out jobs may have committed. Rerun verifies/reuses identical snapshots. No deletion, Silver publication or Neon fallback.') from None
finally:
    client.close()
