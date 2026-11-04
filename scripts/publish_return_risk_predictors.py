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
callback_live_features.py reads; see planning/CP2_REMAINING_TASKS_20261102.md Task H.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webapp import return_risk, storage  # noqa: E402


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
    receipt = derive(cp2_pipeline.read(run_dir / 'calendar_private.json'),
                     cp2_pipeline.read(run_dir / 'sheets_private.json')['snapshots'],
                     run_dir / 'return_risk_features', client=client)
    raw = json.loads((run_dir / 'return_risk_features/predictors/dataset_input.json').read_text(encoding='utf-8'))
    services = write(prepare(raw), uri=uri)
    return {'status': 'PUBLISHED', 'services': services, 'predictor_rows': receipt.get('predictor_rows')}


def main() -> None:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--export', help='an existing predictors/dataset_input.json')
    src.add_argument('--run-dir', help='a reporting run folder holding calendar_private.json and sheets_private.json')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--uri')
    g.add_argument('--local')
    a = ap.parse_args()
    if a.run_dir:
        if not a.uri:
            raise SystemExit('--run-dir publishes to --uri')
        print(from_release(Path(a.run_dir), a.uri))
        return
    n = write(prepare(json.loads(Path(a.export).read_text(encoding='utf-8'))), uri=a.uri, local=a.local)
    print(f'wrote {n} services to {a.local or a.uri}')


if __name__ == '__main__':
    main()
