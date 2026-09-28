"""Build reviewed labels and fixed-horizon datasets without dashboard work."""
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
        ids = set(re.findall(r'prospects_2026_([0-9a-f]{64})', view.view_query or ''))
        if len(ids) != 1:
            raise SystemExit('Cannot resolve pinned Prospects snapshot')
        digest = ids.pop()
        metadata = json.loads(client.get_table(f'profound-keel-500007-s4.bronze.prospects_2026_{digest}').description)
    variables = json.dumps({'prospects_snapshot_id':digest,
        'prospects_snapshot_extracted_at':metadata['extracted_at']})
    dbt = Path(sys.executable).with_name('dbt.exe' if sys.platform == 'win32' else 'dbt')
    selection = [
        'calendar_warranty_review_overrides', 'calendar_events',
        'calendar_service_event_facts', 'warranty_risk_3session_dataset',
        'warranty_coverage_service_episodes', 'warranty_anchor_environment_features',
        'warranty_fixed_horizon_dataset',
        'warranty_callback_fixed_horizon_dataset',
        'source:landcover_quality.worldcover_2021_context_by_location',
    ]
    environment = os.environ.copy()
    # The reviewed 3x model expands multiple bounded history joins (~120 MiB).
    # Other build scripts retain the profile's 100 MiB default.
    environment['NOMOBUG_BQ_MAX_BYTES_BILLED'] = str(250 * 1024 * 1024)
    result = subprocess.run([str(dbt), 'build', '--project-dir', str(ROOT/'dbt'),
        '--profiles-dir', str(ROOT/'dbt'), '--vars', variables, '--select', *selection,
        '--threads', '4',
        '--no-send-anonymous-usage-stats'], cwd=ROOT, env=environment)
    if result.returncode:
        raise SystemExit('Warranty experiment build failed')


if __name__ == '__main__':
    main()
