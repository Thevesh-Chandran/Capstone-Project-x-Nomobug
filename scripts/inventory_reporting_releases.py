"""Read-only release catalogue. Preserve every release referenced by saved rollback history."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from google.cloud import bigquery

PROJECT = 'profound-keel-500007-s4'
PATTERN = re.compile(r'cp2(?:r|qa)_[a-z0-9]+_(?:gold|silver)')
ROOT = Path(__file__).resolve().parents[1]

def dependencies(text):
    return set(PATTERN.findall(text or ''))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/project_audit' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_releases'))
    out = parser.parse_args().output_dir.resolve()
    out.relative_to((ROOT / 'outputs').resolve())
    client = bigquery.Client(project=PROJECT, location='asia-southeast1')
    out.mkdir(parents=True, exist_ok=True)
    names = sorted(d.dataset_id for d in client.list_datasets())
    releases = {n for n in names if PATTERN.fullmatch(n)}
    reasons = {n: set() for n in releases}
    cfg = bigquery.QueryJobConfig(maximum_bytes_billed=104857600)
    def dataset_views(name):
        return [(f'{name}.{row.table_name}', dependencies(row.view_definition)) for row in client.query(
            f'SELECT table_name, view_definition FROM `{PROJECT}.{name}.INFORMATION_SCHEMA.VIEWS`',job_config=cfg).result()]
    with ThreadPoolExecutor(max_workers=6) as pool:
        views = dict(pair for group in pool.map(dataset_views,names) for pair in group)
    for view, deps in views.items():
        if view.split('.')[0] not in releases:
            for name in deps & releases:
                reasons[name].add('Current view: ' + view)
    for row in client.query(f'SELECT view_backups_json FROM `{PROJECT}.audit.release_backups`', job_config=cfg).result():
        for name in dependencies(row.view_backups_json) & releases:
            reasons[name].add('Saved rollback history')
    for folder in ['scripts','config','infra','webapp','dbt','.github']:
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and path.suffix in {'.py','.json','.sql','.yaml','.yml','.toml'}:
                for name in dependencies(path.read_text(encoding='utf-8',errors='ignore')) & releases:
                    reasons[name].add('Local reference: '+path.relative_to(ROOT).as_posix())
    changed = True
    while changed:
        changed = False
        for view, deps in views.items():
            parent = view.split('.')[0]
            if parent in reasons and reasons[parent]:
                for name in deps & releases:
                    reason = 'Dependency of retained release: '+parent
                    if reason not in reasons[name]:
                        reasons[name].add(reason); changed = True
    rows = [{'dataset':n,'status':'retain' if reasons[n] else 'review_only','reasons':sorted(reasons[n])} for n in sorted(releases)]
    (out/'release_inventory.json').write_text(json.dumps({'checked_at':datetime.now(timezone.utc).isoformat(),'releases':rows},indent=2),encoding='utf-8')
    latest = list(client.query(f"SELECT manifest_json FROM `{PROJECT}.audit.release_runs` WHERE status='PUBLISHED' ORDER BY event_at DESC LIMIT 1",job_config=cfg).result())
    if latest:
        (out/'latest_release_manifest.json').write_text(latest[0].manifest_json,encoding='utf-8')
    print(json.dumps({'release_datasets':len(rows),'retained':sum(bool(reasons[n]) for n in releases),'review_only':sum(not reasons[n] for n in releases),'latest_manifest':bool(latest)}))

if __name__=='__main__':
    main()
