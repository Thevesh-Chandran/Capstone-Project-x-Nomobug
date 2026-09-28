import hashlib
from scripts.trace_claim_service_dates import case_resolution


def test_owner_resolution_preserves_only_reviewed_snapshot_case_scope():
    snapshot='frozen_calendar_snapshot'
    fingerprint=hashlib.sha256(f'{snapshot}|12|2026-06-03'.encode()).hexdigest()
    policy={'status':'owner_resolved','date_authority':'Calendar','snapshot_table':snapshot,
            'case_fingerprints':[fingerprint]}
    assert not case_resolution(12,'2026-06-03',snapshot,policy)['requires_review']
    assert case_resolution(13,'2026-06-03',snapshot,policy)['requires_review']
    assert case_resolution(12,'2026-06-04',snapshot,policy)['requires_review']
    assert case_resolution(12,'2026-06-03','new_snapshot',policy)['requires_review']


def test_missing_or_unresolved_policy_does_not_close_cases():
    assert case_resolution(12,'2026-06-03','snapshot',{})['requires_review']
