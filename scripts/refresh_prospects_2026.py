"""Manual live API -> verified Bronze -> dbt Silver/tests -> aggregate checkpoint.

Run one refresh at a time. No scheduling, deletion or Neon fallback.
"""
import argparse
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
from datetime import datetime

from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--refresh', action='store_true', help='Explicitly allow live extraction and warehouse writes')
args = parser.parse_args()
if not args.refresh:
    raise SystemExit('No work performed. Use --refresh to extract, verify Bronze, and rebuild Silver.')

load_dotenv(root / '.env')
if os.getenv('NOMOBUG_BQ_PROJECT') != 'profound-keel-500007-s4' or os.getenv('NOMOBUG_BQ_LOCATION', '').lower() != 'asia-southeast1':
    raise SystemExit('Project/region must match the current dbt profile. No work performed.')
dbt = Path(sys.executable).with_name('dbt.exe' if os.name == 'nt' else 'dbt')
if not dbt.is_file():
    raise SystemExit('Activate the project virtual environment with dbt installed first.')

# Reuse the tested loader. Its approval, header, storage and exact-value checks
# all finish before it returns. A failure raises and stops this script.
sys.argv = ['load_prospects_2026_bigquery.py', '--upload']
loaded = runpy.run_path(str(root / 'scripts/load_prospects_2026_bigquery.py'))
metadata = loaded['verified_metadata']
snapshot_id = metadata['snapshot_id']
if not re.fullmatch(r'[0-9a-f]{64}', snapshot_id):
    raise SystemExit('Invalid snapshot identity; Silver not changed.')
extracted_at = datetime.fromisoformat(metadata['extracted_at'])
if extracted_at.tzinfo is None:
    raise SystemExit('Snapshot timestamp has no timezone; Silver not changed.')
variables = json.dumps({
    'prospects_snapshot_id': snapshot_id,
    'prospects_snapshot_extracted_at': extracted_at.isoformat(),
})
print('\nBuilding Silver from the exact verified snapshot:', snapshot_id, flush=True)
result = subprocess.run([
    str(dbt), 'build', '--project-dir', str(root / 'dbt'),
    '--profiles-dir', str(root / 'dbt'), '--vars', variables,
    '--select', 'prospects_2026', 'acquisition_mapping_examples',
    '--no-send-anonymous-usage-stats',
], cwd=root)
if result.returncode:
    raise SystemExit('Refresh FAILED. Stop here. Bronze remains stored; dbt may already have replaced Silver before a test failed. No automatic rollback or deletion.')
runpy.run_path(str(root / 'scripts/check_prospects_silver_batch.py'))
print('REFRESH PASS: verified Bronze -> Silver build/tests -> checkpoint. Neon unchanged.')
