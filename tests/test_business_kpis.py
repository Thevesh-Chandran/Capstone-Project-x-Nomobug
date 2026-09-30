"""Acceptance-validator failure modes; no live source/API calls."""
from datetime import date
from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("business_kpis", ROOT / "scripts/validate_business_kpis.py")
kpi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kpi)


def test_join_expansion_fails_instead_of_hiding_duplicate_payment():
    with pytest.raises(ValueError, match="Duplicate"):
        kpi.compare_rows([{"row": 1, "amount": Decimal(100)}],
                         [{"row": 1, "amount": Decimal(100)}, {"row": 1, "amount": Decimal(100)}],
                         "row", ["amount"], "payments")


def test_equal_totals_do_not_hide_missing_and_extra_source_members():
    result = kpi.compare_rows([{"row": 1, "amount": Decimal(100)}],
                              [{"row": 2, "amount": Decimal(100)}], "row", ["amount"], "payments")
    assert result["status"] == "fail"
    assert result["missing_rows"] == result["unexpected_rows"] == 1


def test_unknown_amount_does_not_become_zero():
    result = kpi.compare_rows([{"row": 1, "amount": None}], [{"row": 1, "amount": Decimal(0)}],
                              "row", ["amount"], "payments")
    assert result["value_mismatches"] == 1
    assert kpi.amount("RM 490 / RM 190") is None
    assert kpi.amount("1,00") is None
    assert kpi.amount("RM -1,200.50") == Decimal("-1200.50")


def test_combined_payment_uses_one_source_amount_and_ignores_future_rows():
    raw = [{"source_sheet_row": 2, "source_column_001": "22 January", "source_column_002": "CUST1/CUST2", "source_column_003": "1000"},
           {"source_sheet_row": 3, "source_column_001": "1 October", "source_column_002": "CUST3", "source_column_003": "500"}]
    serials = [{"source_sheet_row": 2, "payment_date_display_raw": "22 January", "unformatted_value": "45679", "unformatted_type": "serial"},
               {"source_sheet_row": 3, "payment_date_display_raw": "1 October", "unformatted_value": "46296", "unformatted_type": "serial"}]
    records = kpi.expected_payments(raw, serials)
    assert records[0]["referenced_sale_count"] == 2
    monthly = kpi.monetary_months(records, "payments", date(2026, 9, 27))
    assert sum(r["recorded_payment_entry_amount_rm"] or Decimal(0) for r in monthly) == Decimal(1000)


def test_date_sidecar_cannot_attach_a_different_display_date():
    with pytest.raises(ValueError, match="differs"):
        kpi.expected_payments([{"source_sheet_row": 2, "source_column_001": "22 January", "source_column_002": "CUST1", "source_column_003": "100"}],
                             [{"source_sheet_row": 2, "payment_date_display_raw": "23 January", "unformatted_value": "45679", "unformatted_type": "serial"}])


def test_only_serial_date_resolves_year_and_myt_controls_calendar_day():
    assert kpi.serial_date("45657.8", "serial") == date(2024, 12, 31)
    assert kpi.serial_date("1 January", "text") is None
    assert kpi.local_date("2026-03-01T17:30:00Z") == date(2026, 3, 2)
    assert kpi.local_date("2026-03-01T17:30:00") is None


def sale_row(row, sale_id, premise, sessions, timestamp="1/1/2026", close="1-Jan"):
    return {"source_sheet_row": row, "source_column_003": timestamp, "source_column_004": close,
            "source_column_007": sale_id, "source_column_013": premise, "source_column_014": sessions,
            "source_column_026": "any pest", "source_column_028": "490"}


def test_warranty_rules_do_not_grant_commercial_or_one_session_entitlement():
    raw = [sale_row(2, "CUST1", "COMMERCIAL", "12"), sale_row(3, "CUST2", "RESIDENTIAL", "1"),
           sale_row(4, "CUST3", "RESIDENTIAL", "3"), sale_row(5, "CUST4", "RESIDENTIAL", "6")]
    rows = kpi.expected_sales(raw, set())
    assert [r["warranty_policy_eligible"] for r in rows] == [False, False, True, True]
    assert rows[2]["warranty_policy_rule"] == "POST_FINAL_SERVICE_30D"
    assert rows[3]["warranty_policy_rule"].endswith("UNLIMITED_CLAIMS")


def test_cancelled_package_retained_but_not_in_amount_or_count():
    rows = kpi.expected_sales([sale_row(2, "CUST1", "RESIDENTIAL", "3")], {"CUST1"})
    monthly = kpi.monetary_months(rows, "sales", date(2026, 9, 27))
    assert monthly[0]["package_rows"] == 1
    assert monthly[0]["countable_package_rows"] == 0
    assert monthly[0]["recorded_package_face_value_rm"] is None


def test_sale_year_between_conflicting_timestamps_stays_unknown():
    raw = [sale_row(2, "CUST1", "RESIDENTIAL", "3", "2025-12-01"),
           sale_row(3, "CUST2", "RESIDENTIAL", "3", "", "1-Jan"),
           sale_row(4, "CUST3", "RESIDENTIAL", "3", "2026-01-02")]
    records = kpi.expected_sales(raw, set())
    assert records[1]["closed_date"] is None
    assert records[1]["closed_date_year_source"] == "unresolved"


def test_owner_review_and_consultation_precedence_for_callback_signal():
    assert kpi.calendar_category("GPC 4/3 service", "confirmed") == "warranty"
    assert kpi.calendar_category("Inspection 2/1", "confirmed") == "consultation"
    assert kpi.calendar_category("GPC 1/1 NO WARRANTY", "confirmed") == "service"
    assert kpi.calendar_category("GPC 1/1 NO WARRANTY CALLBACK", "confirmed") == "warranty"
    assert kpi.calendar_category("GPC 4/3", "confirmed", "Not a warranty claim") == "service"
    assert kpi.calendar_category("GPC 4/3", "confirmed", "Unclear") == "label_unresolved"
    assert kpi.calendar_category("GPC WARRANTY", "cancelled", "Confirmed warranty claim") == "cancelled"
    assert kpi.calendar_category("CANCELLED GPC 4/3", "confirmed") == "cancelled"
    assert kpi.calendar_category("CANCELED GPC 2/12", "confirmed") == "cancelled"


def test_followup_placeholders_are_not_prospect_or_confirmed_sale():
    raw = [{"source_sheet_row": 2, "source_column_002": "", "source_column_008": "", "source_column_012": "", "source_column_013": ""},
           {"source_sheet_row": 3, "source_column_002": "synthetic", "source_column_008": "CLOOSED", "source_column_012": "WON pending", "source_column_013": "31-Feb"}]
    rows = kpi.expected_prospects(raw)
    assert len(rows) == 1
    assert rows[0]["conversation_status"] == "CLOSED"
    assert rows[0]["first_reply_date"] is None
    assert rows[0]["remark_is_exact_won"] is False


def test_fresh_drift_is_reported_without_publishing_or_hiding_changes():
    sources = {name: [{"source_sheet_row": 2, "source_column_001": "old"}] for name in ("sales", "payments", "refund", "claims", "prospects", "b2b")}
    fresh = {"snapshots": {"SALES": {"records": [{"source_sheet_row": 2, "source_column_001": "new"},
                                                      {"source_sheet_row": 3, "source_column_001": ""}], "metadata": {}}}}
    result = kpi.fresh_source_drift({"sources": sources}, fresh)
    assert result["reporting_gold_repointed"] is False
    assert result["sources"]["SALES"]["status"] == "drift_detected"
    assert result["sources"]["SALES"]["changed_existing_kpi_input_rows"] == 1
    assert result["sources"]["SALES"]["added_nonblank_kpi_input_rows"] == 0
    assert result["sources"]["PAYMENTS"]["status"] == "fresh_source_not_supplied"


def test_validation_evidence_is_private_and_immutable(tmp_path):
    with pytest.raises(ValueError):
        kpi.private_output(tmp_path / "public")
    (ROOT / "outputs").mkdir(exist_ok=True)
    with pytest.raises(ValueError, match="already exists"):
        kpi.private_output(ROOT / "outputs")
