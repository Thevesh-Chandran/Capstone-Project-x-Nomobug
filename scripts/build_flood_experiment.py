"""Build only flood enrichment and its source/model invariants."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]


def main():
    with bigquery.Client(project='profound-keel-500007-s4', location='asia-southeast1') as client:
        view = client.get_table('profound-keel-500007-s4.silver.prospects_2026')
        digests = set(re.findall(r'prospects_2026_([0-9a-f]{64})', view.view_query or ''))
        if len(digests) != 1:
            raise SystemExit('Cannot resolve pinned Prospects snapshot')
        digest = digests.pop()
        metadata = json.loads(client.get_table(
            f'profound-keel-500007-s4.bronze.prospects_2026_{digest}').description)
    variables = json.dumps({'prospects_snapshot_id': digest,
                            'prospects_snapshot_extracted_at': metadata['extracted_at']})
    dbt = Path(sys.executable).with_name('dbt.exe' if sys.platform == 'win32' else 'dbt')
    environment = os.environ.copy()
    environment['NOMOBUG_BQ_MAX_BYTES_BILLED'] = str(100 * 1024 * 1024)
    result = subprocess.run([
        str(dbt), 'build', '--project-dir', str(ROOT / 'dbt'),
        '--profiles-dir', str(ROOT / 'dbt'), '--vars', variables,
        '--select', 'warranty_callback_flood_dataset',
        'source:flood_quality.gfm_flood_context_by_anchor',
        'source:flood_quality.gdacs_reported_flood_context_by_anchor',
        '--threads', '4', '--no-send-anonymous-usage-stats'],
        cwd=ROOT, env=environment)
    if result.returncode:
        raise SystemExit('Flood enrichment build failed')


if __name__ == '__main__':
    main()
