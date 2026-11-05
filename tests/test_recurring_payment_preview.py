"""Private tracker export and dependency expansion safeguards."""
import csv
from decimal import Decimal

import pytest
from scripts.preview_recurring_payment_tracker import expand_model, render_tracker, write_csv, verify_tracker_sources


def test_tracker_rejects_payments_even_as_an_indirect_dependency():
    nodes = {"model.nomobug.tracker": {"depends_on": {"nodes": ["model.nomobug.history"]}},
             "model.nomobug.history": {"depends_on": {"nodes": ["source.nomobug.operational_bronze.payments"]}}}
    with pytest.raises(ValueError, match="unapproved source"):
        verify_tracker_sources("model.nomobug.tracker", nodes)


def test_tracker_accepts_only_sales_and_recurring_sources():
    nodes = {"model.nomobug.tracker": {"depends_on": {"nodes": [
        "source.nomobug.operational_bronze.sales", "source.nomobug.operational_bronze.recurring_payments"]}}}
    verify_tracker_sources("model.nomobug.tracker", nodes)


def test_export_neutralizes_spreadsheet_formulas_without_changing_numeric_amounts(tmp_path):
    target = tmp_path / "tracker.csv"
    write_csv(target, [{"name": '=HYPERLINK("https://example.invalid")',
                        "amount": Decimal("-12.50")},
                       {"name": "+example", "amount": Decimal("100.00")}], ["name", "amount"])
    with target.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["name"].startswith("'=")
    assert rows[1]["name"] == "'+example"
    assert rows[0]["amount"] == "-12.50"


def test_preview_expands_each_model_dependency_to_the_declared_source():
    nodes = {
        "model.x.child": {"compiled_code": "select * from `p.bronze.pinned`",
                          "depends_on": {"nodes": []}, "relation_name": "`p.s.child`"},
        "model.x.parent": {"compiled_code": "select * from `p.s.child`",
                           "depends_on": {"nodes": ["model.x.child"]}}}
    assert expand_model("model.x.parent", nodes, {}) == (
        "select * from (\nselect * from `p.bronze.pinned`\n)")


def test_dependency_ending_in_comment_cannot_swallow_parent_sql():
    nodes = {
        "model.x.child": {"compiled_code": "select 1 -- source note",
                          "depends_on": {"nodes": []}, "relation_name": "`p.s.child`"},
        "model.x.parent": {"compiled_code": "select * from `p.s.child` group by 1",
                           "depends_on": {"nodes": ["model.x.child"]}}}
    assert "-- source note\n) group by 1" in expand_model("model.x.parent", nodes, {})


def test_private_html_escapes_source_notes_and_does_not_claim_reminder_readiness(tmp_path):
    target = tmp_path / "tracker.html"
    render_tracker([{"customer_name_raw": '<script>alert("source")</script>',
                     "lifecycle_review_required": False, "custom_payment_note": True,
                     "candidate_schedule_cells": 0, "payment_review_rows": 0,
                     "sale_id_rows": 1, "schedule_link_review_rows": 0,
                     "tracker_as_of_date": "2026-10-04"}], "release-example", target)
    contents = target.read_text(encoding="utf-8")
    assert '<script>alert("source")</script>' not in contents
    assert "&lt;script&gt;" in contents
    assert "No client reminders are enabled" in contents
    assert "does not refresh automatically" in contents
    assert "PAYMENTS is excluded from this tracker" in contents
    assert "Recorded payment history" not in contents
