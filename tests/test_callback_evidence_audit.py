from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from scripts import audit_callback_evidence as a
from scripts import freeze_callback_prospective as p


def row(date="2026-10-04"):
    return {"population": "matched_packages_recorded_callback_30d", "sales_record_id": "fixture-sale", "anchor_date": date}


def event(title="GPC 1/3 fixture", date="2026-10-04"):
    return {"calendar_id": "fixture-calendar", "event_id": "fixture-event", "summary": title,
            "status": "confirmed", "start_raw": date+"T10:00:00+08:00", "end_raw": date+"T11:00:00+08:00"}


def receipt(date="2026-10-04"):
    record = {"bundle_sha256": "a"*64, "row": row(date), "source_receipt": {
        "calendar_event_keys_by_prediction_key": {
            "matched_packages_recorded_callback_30d|fixture-sale|"+date+"T00:00:00.000": a.calendar_window_key(event(date=date))}}}
    record["record_sha256"] = p.record_digest(record)
    return record


def audit(entries, rows, **kwargs):
    return a.eligibility_drift(entries, rows, bundle_sha256="a"*64,
                              cohort_start="2026-10-01", cohort_end="2026-10-27", **kwargs)


def test_historical_metadata_refuses_updated_source_or_row_count():
    table = SimpleNamespace(modified=datetime(2026,9,27,tzinfo=timezone.utc), num_rows=5598)
    a.validate_metadata(table, table.modified.isoformat(), 5598)
    with pytest.raises(ValueError, match="epoch changed"):
        a.validate_metadata(table, "2026-09-28T00:00:00+00:00", 5598)
    with pytest.raises(ValueError, match="epoch changed"):
        a.validate_metadata(table, table.modified.isoformat(), 5599)


def test_historical_source_check_never_joins_live_silver_and_binds_stable_identity():
    import json
    sql = a.historical_sql(json.loads(a.PIN.read_text()))
    assert ".silver." not in sql
    assert "r.event_id=f.event_id AND r.calendar_name=f.calendar_name" in sql
    assert "raw_date IS DISTINCT FROM anchor_date" in sql
    assert "historical_callback_count" in sql
    assert "DAYOFWEEK" not in sql


def test_coverage_agreement_is_not_accuracy_or_maturity_proof():
    result = audit([receipt()], [row()])
    assert result["coverage_keys_agree"]
    assert result["retained_services"] == 1
    assert result["accuracy_claim_ready"] is False


def test_receipt_changes_duplicates_and_other_bundle_are_rejected():
    record = receipt()
    record["row"]["sales_record_id"] = "altered"
    with pytest.raises(ValueError, match="changed"):
        audit([record], [row()])
    with pytest.raises(ValueError, match="Duplicate prospective"):
        audit([receipt(), receipt()], [row()])
    with pytest.raises(ValueError, match="Duplicate extracted"):
        audit([receipt()], [row(), row()])
    record = receipt()
    record["bundle_sha256"] = "b"*64
    with pytest.raises(ValueError, match="bundle differs"):
        audit([record], [row()])


def test_missing_prediction_and_excluded_logged_anchor_are_visible():
    result = audit([receipt()], [row("2026-10-05")])
    assert result["changed_services"] == 2
    assert not result["coverage_keys_agree"]
    assert result["change_counts"] == {"logged_service_missing_from_extraction": 1, "extracted_service_without_receipt": 1}


def test_postponed_original_and_active_replacement_stay_separate():
    replacement = dict(event(date="2026-10-05"), event_id="active-replacement")
    result = audit([receipt()], [row("2026-10-05")], current_events=[event("CANCELLED GPC 1/3 fixture"), replacement])
    assert result["changes_private"][0]["reason"] == "old_appointment_postponed_active_replacement_requires_own_identity"
    assert result["changes_private"][1]["reason"] == "missing_or_late_prediction_cannot_be_backfilled"


def test_later_placeholder_is_flagged_even_if_extracted_key_still_present():
    result = audit([receipt()], [row()], current_events=[event("HOLD awaiting client confirmation")])
    assert result["changes_private"][0]["kind"] == "logged_service_source_now_ineligible"
    assert result["changes_private"][0]["reason"] == "later_marked_hold_placeholder_not_confirmed_service"
    assert not result["coverage_keys_agree"]


def test_sunday_alone_is_never_ineligible():
    # 4 October 2026 is Sunday; the owner confirmed Sunday services also occur.
    result = audit([receipt()], [row()], current_events=[event()])
    assert result["coverage_keys_agree"]


def test_exact_owner_review_expires_when_event_moves():
    import hashlib
    review = {"event_identity_hash": hashlib.sha256(b"fixture-calendar|fixture-event").hexdigest(),
              "expected_start_at_utc": "2026-10-04T02:00:00+00:00",
              "expected_end_at_utc": "2026-10-04T03:00:00+00:00"}
    result = audit([receipt()], [row()], current_events=[event()], appointment_reviews=[review])
    assert result["changes_private"][0]["reason"] == "owner_confirmed_temporary_slot_exact_reviewed_window"
    result = audit([receipt("2026-10-05")], [row("2026-10-05")],
                   current_events=[event(date="2026-10-05")], appointment_reviews=[review])
    assert result["coverage_keys_agree"]


def test_moved_event_window_is_not_invented_as_same_logged_appointment():
    result = audit([receipt()], [], current_events=[event("HOLD awaiting confirmation", date="2026-10-05")])
    assert result["changes_private"][0]["reason"] == "eligibility_or_identity_changed_needs_source_review"


def test_historical_dbt_test_never_joins_old_anchor_row_to_current_events():
    sql = (a.b.ROOT/"dbt/tests/warranty_callback_horizon_invariants.sql").read_text()
    assert "ref('calendar_events')" not in sql
    assert "warranty_signal_within_30d is null" in sql
    assert "group by population, sales_record_id, anchor_date" in sql
