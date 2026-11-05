"""One-time owner-authorized amendment before collection starts; keep prior bytes."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from scripts.cp2_collection_policy import record_digest, LOCAL

ROOT = Path(__file__).resolve().parents[1]

def main():
    path = ROOT/'config/cp2_october10_cohort.json'
    old = path.read_bytes()
    expected = '7224062bf8a41110769aa4d2b6d951aec4ccb562d00d6a5631301c4a3684a4d3'
    assert sha256(old).hexdigest() == expected, 'Amendment already declared or source changed'
    now = datetime.now(timezone.utc)
    assert now.astimezone(LOCAL).date().isoformat() < '2026-10-10', 'Cannot amend after collection begins'
    archive = ROOT/'planning/protocol_archive/cp2_october10_before_extension.json'
    archive.parent.mkdir(exist_ok=True)
    with archive.open('xb') as handle:
        handle.write(old)
    protocol = json.loads(old)
    protocol.update(declared_at_utc=now.isoformat(), cohort_end='2026-10-30',
        earliest_final_evaluation_date='2026-11-30',
        amendment='precollection_extension_to_october30_v1', supersedes_protocol_sha256=expected,
        authorization='Owner selected finish by 30 November; collect through 30 October, before collection started.')
    protocol['eligibility'] = protocol['eligibility'].replace('10–27 October','10–30 October')
    protocol['record_sha256'] = record_digest(protocol)
    raw = (json.dumps(protocol, indent=2, ensure_ascii=False)+'\n').encode()
    path.write_bytes(raw)
    registry_path = ROOT/'config/cp2_model_current.json'
    registry = json.loads(registry_path.read_text())
    registry.update(october10_cohort=['2026-10-10','2026-10-30'],
        october10_cohort_protocol_sha256=sha256(raw).hexdigest(),
        october10_earliest_final_evaluation='2026-11-30')
    registry_path.write_bytes((json.dumps(registry, indent=2)+'\n').encode())
    print(json.dumps({'protocol_sha256':sha256(raw).hexdigest(),'declared_at_utc':now.isoformat(),
        'cohort_end':'2026-10-30','final_evaluation':'2026-11-30','prior_protocol_preserved':True}))

if __name__ == '__main__':
    main()
