"""Build and test the safe Calendar Silver view after Bronze verification."""
import json
import re
import subprocess
import sys
from pathlib import Path

from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'profound-keel-500007-s4'
LOCATION = 'asia-southeast1'
CALENDAR_TABLE = 'calendar_events_78147d417f3d97d3c1d9ef0be59638fd7850e4195108e1fc7b879483c7f35b66'


def main():
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        table = client.get_table(f'{PROJECT}.bronze.{CALENDAR_TABLE}')
        metadata = json.loads(table.description or '{}')
        if metadata.get('snapshot_id') != CALENDAR_TABLE.split('_')[-1] or table.num_rows != 11214:
            raise SystemExit('Calendar Bronze metadata/row count changed; repoint deliberately before building.')
        view = client.get_table(f'{PROJECT}.silver.prospects_2026')
        ids = set(re.findall(r'prospects_2026_([0-9a-f]{64})', view.view_query or ''))
        if len(ids) != 1:
            raise SystemExit('Cannot resolve current Prospects lineage for dbt parsing.')
        digest = ids.pop()
        prospect_metadata = json.loads(client.get_table(f'{PROJECT}.bronze.prospects_2026_{digest}').description)
        variables = json.dumps({'prospects_snapshot_id': digest,
            'prospects_snapshot_extracted_at': prospect_metadata['extracted_at']})
    finally:
        client.close()
    dbt = Path(sys.executable).with_name('dbt.exe' if sys.platform == 'win32' else 'dbt')
    command = [str(dbt), 'build', '--project-dir', str(ROOT / 'dbt'),
        '--profiles-dir', str(ROOT / 'dbt'), '--vars', variables,
        '--select', 'tag:calendar', '--no-send-anonymous-usage-stats']
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode:
        raise SystemExit('CALENDAR SILVER FAILED. Review dbt output; do not publish downstream marts.')
    print('CALENDAR SILVER BUILD PASS. Raw descriptions/locations are not exposed in Silver.')


if __name__ == '__main__':
    main()
