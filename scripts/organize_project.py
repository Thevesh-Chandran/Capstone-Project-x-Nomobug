"""Remove regenerable caches and produce a path-preserving project inventory."""
from pathlib import Path
import json
import shutil
import stat
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

def main():
    evidence = ROOT / 'outputs/project_audit/20261016_cleanup'
    evidence.mkdir(parents=True, exist_ok=True)
    previous = evidence / 'local_cleanup.json'
    removed = json.loads(previous.read_text()).get('removed_regenerable_caches', []) if previous.exists() else []
    # dbt/target contains eight cryptographically pinned collector inputs.
    # Treat it as protected runtime evidence, not disposable build output.
    candidates = [ROOT / '.pytest_cache', ROOT / 'dbt/logs']
    candidates += [ROOT / p for p in ['tmp/pip-probe', 'tmp/portal_cloud_build',
        'tmp/reporting_business_build', 'tmp/__pycache__',
        '.codex-tmp/portal-20261015', '.codex-tmp/portal-20261015-reviewed',
        '.codex-tmp/collector-20261015-reviewed']]
    for parent in ['scripts', 'tests', 'webapp']:
        candidates.extend((ROOT / parent).rglob('__pycache__'))
    for path in candidates:
        path = path.resolve()
        if not path.is_relative_to(ROOT) or not path.is_dir():
            continue
        size = sum(p.stat().st_size for p in path.rglob('*') if p.is_file())
        def clear_readonly(function, filename, exception):
            Path(filename).chmod(stat.S_IWRITE | stat.S_IREAD)
            function(filename)
        shutil.rmtree(path, onexc=clear_readonly)
        removed.append({'path': str(path.relative_to(ROOT)), 'bytes': size})
    inventory = []
    for parent in ['data', 'outputs', 'tmp', '.codex-tmp']:
        base = ROOT / parent
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            files = [p for p in child.rglob('*') if p.is_file()]
            inventory.append({'path': str(child.relative_to(ROOT)), 'files': len(files),
                              'bytes': sum(p.stat().st_size for p in files)})
    (evidence / 'local_cleanup.json').write_text(json.dumps({
        'at_utc': datetime.now(timezone.utc).isoformat(), 'root': str(ROOT),
        'removed_regenerable_caches': removed, 'inventory': inventory,
        'protected': ['secrets', '.env', '.git', 'model bundles', 'protocols',
                      'prediction receipts', 'immutable source snapshots']}, indent=2))
    print(json.dumps({'removed_caches': len(removed),
                      'removed_bytes': sum(r['bytes'] for r in removed),
                      'inventory': str(evidence / 'local_cleanup.json')}))

if __name__ == '__main__':
    main()
