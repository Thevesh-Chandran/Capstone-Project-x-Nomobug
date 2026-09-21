"""Metadata preflight + compile/read-only validation, or explicit --build deployment."""
import argparse
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
from google.cloud import bigquery

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build', action='store_true')
args = parser.parse_args()
project = 'profound-keel-500007-s4'
client = bigquery.Client(project=project, location='asia-southeast1')
contracts = runpy.run_path(str(root / 'scripts/operational_source_contracts.py'))
# Explicit verified snapshots. Repoint deliberately after a later Bronze batch.
tables = {
    'B2B FOLLOW UP': 'b2b_follow_up_9108505ec89b8d23513fae1a2aba7e0d63466b7ceb1dc1ea99b451167047231d',
    'SALES': 'sales_6d1d3d3155b4ca3f57df14237b344cc2be163516d7b22f4f8ab1a305de80c2b8',
    'PAYMENTS': 'payments_edbb6850cf6e869051a3d067090e04c87b6c0167d7e2881de47f26d3706c21e4',
    'PAYMENT LINK': 'payment_link_f040f2944375cbb9d35e39db828c9aeb8c9e30444d6d9f9bbd14fa880611a976',
    'WARRANTY CLAIM': 'warranty_claim_c20e5659ea3fff3f6e8c7ea5740c0bf6c0590bc8888e01f5128e240f0c9edf13',
    'Commercial Clients': 'commercial_clients_60e12ac95a426cddd7fdc03c2de5e92337feb525b559260617147e11d58576fd',
    'REFUND': 'refund_e5b24aae95b0502a1221f9c556ac0cc9d90fe58cf8b5823517fad501f59b6cf8',
    'Recurring Payments': 'recurring_payments_5f68eb4fd2c39e1913717dea880bbde75b0cc29c429adc14009c9c0f0cac03c2',
}
try:
    for dataset in ['bronze', 'silver']:
        if client.get_dataset(f'{project}.{dataset}').location.lower() != 'asia-southeast1':
            raise SystemExit('Dataset location mismatch.')
    for tab, name in tables.items():
        table = client.get_table(f'{project}.bronze.{name}')
        metadata = json.loads(table.description or '{}')
        if metadata.get('source_tab') != tab or not name.endswith('_' + metadata.get('snapshot_id', 'INVALID')):
            raise SystemExit('Snapshot metadata mismatch.')
        if table.num_rows != metadata['source_row_count']:
            raise SystemExit('Snapshot row-count mismatch.')
        observed = [' '.join((field.description or '').split()) for field in table.schema[1:]]
        if observed != contracts['HEADERS'][tab]:
            raise SystemExit('Snapshot header mismatch.')
        print(tab, '| verified snapshot rows:', table.num_rows)

    # dbt parses the whole project. Supply CURRENT Prospects lineage for parsing
    # only; tag selection excludes its model and tests from this deployment.
    view = client.get_table(f'{project}.silver.prospects_2026')
    ids = set(re.findall(r'prospects_2026_([0-9a-f]{64})', view.view_query or ''))
    if len(ids) != 1:
        raise SystemExit('Cannot resolve current Prospects lineage for dbt parsing.')
    digest = ids.pop()
    metadata = json.loads(client.get_table(f'{project}.bronze.prospects_2026_{digest}').description)
    variables = json.dumps({'prospects_snapshot_id': digest,
        'prospects_snapshot_extracted_at': metadata['extracted_at']})
    dbt = Path(sys.executable).with_name('dbt.exe' if sys.platform == 'win32' else 'dbt')
    command = [str(dbt), 'build' if args.build else 'compile', '--project-dir', str(root / 'dbt'),
        '--profiles-dir', str(root / 'dbt'), '--vars', variables,
        '--select', 'tag:operational', '--no-send-anonymous-usage-stats']
    result = subprocess.run(command, cwd=root)
    if result.returncode:
        raise SystemExit('DBT FAILED. Stop. A build may have changed views before a test failed; no automatic rollback.')

    if not args.build:
        # Inline dependencies to validate without creating warehouse views.
        expanded = {}
        compiled = root / 'dbt/target/compiled/nomobug'
        settings = bigquery.QueryJobConfig(maximum_bytes_billed=104857600)
        for model in ['b2b_follow_up', 'sales', 'payments', 'payment_link',
                      'warranty_claim', 'commercial_clients', 'refund',
                      'recurring_payments', 'payment_sales_links']:
            sql = (compiled / 'models' / f'{model}.sql').read_text(encoding='utf-8')
            for dependency, dependency_sql in expanded.items():
                sql = sql.replace(f'`{project}`.`silver`.`{dependency}`', '(' + dependency_sql + ')')
                sql = sql.replace(f'`{project}.silver.{dependency}`', '(' + dependency_sql + ')')
            expanded[model] = sql
            count = list(client.query('select count(*) as n from (' + sql + ')', job_config=settings).result())[0]['n']
            print('READ-ONLY SQL PASS:', model, '| rows:', count)
        for test in ['operational_raw_preserved', 'payment_link_invariants',
                     'operational_parser_examples', 'operational_remaining_invariants']:
            sql = (compiled / 'tests' / f'{test}.sql').read_text(encoding='utf-8')
            for model, model_sql in expanded.items():
                sql = sql.replace(f'`{project}`.`silver`.`{model}`', '(' + model_sql + ')')
                sql = sql.replace(f'`{project}.silver.{model}`', '(' + model_sql + ')')
            failures = list(client.query('select count(*) as n from (' + sql + ')', job_config=settings).result())[0]['n']
            if failures:
                raise SystemExit(f'{test}: {failures} failures. No deployment performed.')
            print('READ-ONLY TEST PASS:', test)
        print('OPERATIONAL SILVER PREFLIGHT PASS. No views created or changed.')
    else:
        print('OPERATIONAL SILVER BUILD PASS. Prospects and Neon unchanged.')
finally:
    client.close()
