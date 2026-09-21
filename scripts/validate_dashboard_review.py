"""Publish corrected views, then run one bounded reconciliation; stop on quota."""
import json
import re
import subprocess
import sys
from pathlib import Path

from google.cloud import bigquery
from google.api_core.exceptions import Forbidden

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'profound-keel-500007-s4'
MODELS = ['dashboard_recurrence_windows', 'dashboard_treatment_difficulty',
          'dashboard_payment_link_monthly']


def main():
    with bigquery.Client(project=PROJECT, location='asia-southeast1') as client:
        view = client.get_table(f'{PROJECT}.silver.prospects_2026')
        ids = set(re.findall(r'prospects_2026_([0-9a-f]{64})', view.view_query or ''))
        if len(ids) != 1:
            raise SystemExit('Cannot resolve pinned Prospects snapshot')
        digest = ids.pop()
        metadata = json.loads(client.get_table(
            f'{PROJECT}.bronze.prospects_2026_{digest}').description)
        variables = json.dumps({'prospects_snapshot_id': digest,
            'prospects_snapshot_extracted_at': metadata['extracted_at']})
        executable = str(Path(sys.executable).with_name('dbt.exe'))
        common = ['--project-dir', str(ROOT / 'dbt'), '--profiles-dir',
                  str(ROOT / 'dbt'), '--vars', variables,
                  '--no-send-anonymous-usage-stats']
        subprocess.run([executable, 'compile', *common, '--select', *MODELS,
                        'dashboard_extended_metric_invariants'], cwd=ROOT, check=True)
        if '--check-only' not in sys.argv:
            subprocess.run([executable, 'run', *common, '--select', *MODELS],
                           cwd=ROOT, check=True)
        sql = (ROOT / 'dbt/target/compiled/nomobug/tests/'
               'dashboard_extended_metric_invariants.sql').read_text(encoding='utf-8')
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False))
        print(f'Estimated bytes: {dry.total_bytes_processed}')
        if dry.total_bytes_processed > 104857600:
            raise SystemExit('Reconciliation exceeds 100 MiB cap')
        try:
            # This reconciliation expands several regex-heavy views. Keep the
            # strict 100 MiB cost cap, but allow enough wall time for BigQuery
            # to finish the bounded scan on an on-demand slot pool.
            rows = list(client.query(sql, job_config=bigquery.QueryJobConfig(
                maximum_bytes_billed=104857600, job_timeout_ms=600000),
                job_retry=None).result(timeout=630))
        except Forbidden as exc:
            if 'QueryUsagePerDay' in str(exc):
                raise SystemExit('Live validation blocked by QueryUsagePerDay quota; '
                                 'no reconciliation pass claimed.') from None
            raise
        if rows:
            for row in rows:
                print(row.failure)
            raise SystemExit('Dashboard reconciliation FAILED')
        print('Dashboard reconciliation PASS')


if __name__ == '__main__':
    main()
