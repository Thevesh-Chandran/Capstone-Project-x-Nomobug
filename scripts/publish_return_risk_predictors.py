"""Publish the recent-service predictor export for live return-visit risk scores.

Input: the predictor export written by scripts/callback_live_features.py
(features/predictors/dataset_input.json). Outcome columns are removed before
publishing, the file is validated with webapp.return_risk.validate_predictors,
and it is uploaded beside the other private runtime snapshots.

  python scripts/publish_return_risk_predictors.py --export <dataset_input.json> --uri gs://<bucket>/<prefix>
  python scripts/publish_return_risk_predictors.py --export <dataset_input.json> --local <runtime folder>
  python scripts/publish_return_risk_predictors.py --run-dir outputs/reporting_release/<run_id> --uri gs://<bucket>/<prefix>

The --run-dir form (and from_release, called by the daily reporting job when
CP2_RETURN_RISK_PREDICTORS=yes) needs the frozen feature SQL inputs that
callback_live_features.py reads; see planning/CP2_RETURN_RISK_UPDATE_20261104.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webapp import return_risk, storage  # noqa: E402


def hydrate_feature_inputs(bucket_name: str) -> None:
    """Read only hash-pinned feature SQL and reference inputs, never experiment ledgers."""
    from google.cloud import storage as gcs
    pin = json.loads((ROOT / 'config/cp2_live_feature_contract.json').read_text())
    inventory = json.loads((ROOT / 'config/cp2_cloud_artifacts.json').read_text())
    prefix = 'artifacts/' + hashlib.sha256(json.dumps(pin, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()[:16] + '/'
    bucket = gcs.Client().bucket(bucket_name)
    if json.loads(bucket.blob(prefix + 'manifest.json').download_as_text()) != inventory:
        raise ValueError('Feature artifact inventory differs from its pinned manifest')
    needed = {f'dbt/target/compiled/nomobug/models/{name}' for name in pin['compiled_query_hashes']}
    needed.update({'outputs/cp2-v2/prospective_callback_v2/bundle.json',
                   'outputs/cp2-v2/source_refresh_20260927/old_calendar_private.json'})
    for relative in sorted(needed):
        expected = inventory[relative]
        body = bucket.blob(prefix + relative).download_as_bytes()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError('Feature artifact integrity mismatch')
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)


def prepare(raw: dict) -> dict:
    """Keep only the model's input columns: no outcomes, addresses or coordinates leave the run."""
    missing = [c for c in return_risk.REQUIRED if c not in raw.get('columns', [])]
    if missing:
        raise ValueError('Predictor export is missing ' + ', '.join(missing))
    keep = [raw['columns'].index(c) for c in return_risk.REQUIRED]
    cols = [raw['columns'][i] for i in keep]
    recs = []
    for r in raw['records']:
        recs.append([r[i] for i in keep] if isinstance(r, list) else {c: r.get(c) for c in cols})
    out = {'columns': cols, 'records': recs}
    return_risk.validate_predictors(out)
    return out


def write(out: dict, *, uri: str | None = None, local: str | Path | None = None) -> int:
    body = json.dumps(out, separators=(',', ':'), default=str, allow_nan=False)
    if local:
        (Path(local) / return_risk.PREDICTORS).write_text(body, encoding='utf-8')
    else:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / return_risk.PREDICTORS).write_text(body, encoding='utf-8')
            storage.publish_business(uri, tmp, name=return_risk.PREDICTORS)
    return len(out['records'])


def from_release(run_dir: Path, uri: str, client=None) -> dict:
    """Daily reporting step: derive read-only predictors from this release's sources and publish them.

    Uses the same frozen feature SQL as callback_live_features (session temp tables only), in its own
    folder under this reporting run, so the frozen collector and its evaluation are untouched.
    Weather is not needed by return_risk_v1.
    """
    try:
        from scripts import cp2_pipeline
        from scripts.callback_live_features import derive
    except ModuleNotFoundError:  # pragma: no cover
        import cp2_pipeline
        from callback_live_features import derive
    run_dir = Path(run_dir)
    if os.getenv('CP2_FEATURE_ARTIFACT_BUCKET'):
        hydrate_feature_inputs(os.environ['CP2_FEATURE_ARTIFACT_BUCKET'])
    receipt = derive(cp2_pipeline.read(run_dir / 'calendar_private.json'),
                     cp2_pipeline.read(run_dir / 'sheets_private.json')['snapshots'],
                     run_dir / 'return_risk_features', client=client)
    raw = json.loads((run_dir / 'return_risk_features/predictors/dataset_input.json').read_text(encoding='utf-8'))
    exported = prepare(raw)
    release = cp2_pipeline.read(run_dir / 'release_manifest.json')
    exported['captured_at'] = release['extracted_at']['calendar']
    exported['source_release_id'] = release['run_id']
    services = write(exported, uri=uri)
    return {'status': 'PUBLISHED', 'services': services, 'predictor_rows': receipt.get('predictor_rows')}


def from_published_release(uri: str) -> dict:
    """Recover only the operational predictor export from the latest validated release."""
    from google.cloud import bigquery
    from scripts.cp2_reporting_release import PROJECT, LOCATION, LIMIT, safe_json
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        config = bigquery.QueryJobConfig(maximum_bytes_billed=LIMIT)
        query = f'SELECT manifest_json FROM `{PROJECT}.audit.release_runs` WHERE status="PUBLISHED" ORDER BY event_at DESC LIMIT 1'
        rows = list(client.query(query, job_config=config).result(timeout=120))
        if not rows:
            raise ValueError('No published release is available')
        manifest = json.loads(rows[0]['manifest_json'])
        import re
        run_id = manifest['run_id']
        if not re.fullmatch(r'[0-9]{14}[0-9a-f]{6}', run_id):
            raise ValueError('Invalid published release identity')
        stable = client.get_table(f'{PROJECT}.gold.sales_monthly_recorded')
        if f'cp2r_{run_id}_gold.sales_monthly_recorded' not in (stable.view_query or ''):
            raise ValueError('Published release no longer matches current reporting views')
        run_dir = ROOT / 'outputs' / 'return_risk_recovery' / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        def snapshot(key):
            name = manifest['snapshot_tables'][key]
            if not re.fullmatch(r'[a-z][a-z0-9_]*_[0-9a-f]{64}', name):
                raise ValueError('Invalid published snapshot identity')
            table_id = f'{PROJECT}.bronze.{name}'
            table = client.get_table(table_id)
            metadata = json.loads(table.description or '{}')
            if metadata.get('snapshot_id') != name.rsplit('_', 1)[1]:
                raise ValueError('Published snapshot metadata mismatch')
            order = 'calendar_event_row' if key == 'calendar' else 'source_sheet_row'
            records = [dict(r) for r in client.query(f'SELECT * FROM `{table_id}` ORDER BY {order}', job_config=config).result(timeout=120)]
            if len(records) != table.num_rows:
                raise ValueError('Published snapshot row count mismatch')
            metadata['extracted_at'] = manifest['extracted_at'][key]
            return {'table_name': name, 'metadata': metadata, 'records': records}
        safe_json(run_dir / 'release_manifest.json', manifest)
        safe_json(run_dir / 'calendar_private.json', snapshot('calendar'))
        safe_json(run_dir / 'sheets_private.json', {'snapshots': {key: snapshot(key)
            for key in ('SALES', 'PAYMENT LINK', 'WARRANTY CLAIM')}})
        return from_release(run_dir, uri, client=client)
    finally:
        client.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--export', help='an existing predictors/dataset_input.json')
    src.add_argument('--run-dir', help='a reporting run folder holding calendar_private.json and sheets_private.json')
    src.add_argument('--published-release', action='store_true', help='recover the operational export from the latest published release')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--uri')
    g.add_argument('--local')
    a = ap.parse_args()
    if a.published_release:
        if not a.uri:
            raise SystemExit('--published-release requires --uri')
        print(from_published_release(a.uri))
        return
    if a.run_dir:
        if not a.uri:
            raise SystemExit('--run-dir publishes to --uri')
        print(from_release(Path(a.run_dir), a.uri))
        return
    n = write(prepare(json.loads(Path(a.export).read_text(encoding='utf-8'))), uri=a.uri, local=a.local)
    print(f'wrote {n} services to {a.local or a.uri}')


if __name__ == '__main__':
    main()
