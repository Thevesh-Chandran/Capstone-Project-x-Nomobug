"""Validate and export a private tracker from the latest published release.

Read-only BigQuery queries; no source edits, publication, or reminder delivery.
The daily reporting build includes the same tagged dbt models after deployment.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import subprocess
import sys

from google.cloud import bigquery
from scripts import cp2_reporting_release as release

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["recurring_contract_candidates",
          "recurring_payment_date_candidates", "recurring_contract_payment_tracker",
          "dashboard_recurring_payment_quality", "dashboard_recurring_reminder_schedule"]


def expand_model(node_id: str, nodes: dict, cache: dict) -> str:
    if node_id in cache:
        return cache[node_id]
    node = nodes[node_id]
    sql = node["compiled_code"]
    for dependency in node["depends_on"]["nodes"]:
        if dependency.startswith("model."):
            child = nodes[dependency]
            sql = sql.replace(child["relation_name"],
                              "(\n" + expand_model(dependency, nodes, cache) + "\n)")
    cache[node_id] = sql
    return sql


def verify_tracker_sources(node_id: str, nodes: dict) -> None:
    allowed = {"source.nomobug.operational_bronze.sales",
               "source.nomobug.operational_bronze.recurring_payments"}
    visited = set()
    def visit(current):
        if current in visited:
            return
        visited.add(current)
        if current.startswith("source."):
            if current not in allowed:
                raise ValueError("Recurring tracker uses an unapproved source: " + current)
            return
        for dependency in nodes[current]["depends_on"]["nodes"]:
            visit(dependency)
    visit(node_id)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        # Quoting alone does not prevent spreadsheet formula evaluation.
        for row in rows:
            writer.writerow({key: ("'" + value if isinstance(value, str)
                and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value)
                for key, value in row.items()})


def render_tracker(rows: list[dict], run_id: str, output: Path) -> None:
    columns = [("sales_record_id", "Sale / contract ID"),
               ("customer_name_raw", "Client / source notes"),
               ("billing_arrangement", "Payment arrangement"),
               ("sales_remaining_balance_rm", "SALES balance (RM)"),
               ("sales_deposit_recorded_rm", "SALES deposit paid (RM)"),
               ("sales_balance_paid_recorded_rm", "SALES balance paid (RM)"),
               ("sales_total_recorded_paid_rm", "SALES total recorded paid (RM)"),
               ("next_proposed_due_date", "Next proposed date — verify"),
               ("review", "Review result")]
    body = []
    for original in rows:
        row = dict(original)
        matches = row.get("recorded_balance_calculation_matches")
        checks = ["Recorded balance calculation checked" if matches is True
                  else "Recorded balance calculation needs checking"]
        if row.get("sales_remaining_balance_rm") is not None and row["sales_remaining_balance_rm"] <= 0:
            checks.append("No positive balance recorded")
        else:
            checks.append("Reminder schedule available; individual paid instalments and reminder delivery are not recorded")
        if row["lifecycle_review_required"]:
            checks.append("Cancellation / hold / refund note")
        if row["custom_payment_note"]:
            checks.append("Custom payment terms in source notes")
        if row.get("specific_payment_terms_note"):
            checks.append("Specific timing/amount note must be reconciled with generated dates")
        if not row["candidate_schedule_cells"]:
            checks.append("No source reminder schedule")
        if row["sale_id_rows"] != 1 or row["schedule_link_review_rows"]:
            checks.append("Ambiguous source link")
        row["review"] = "; ".join(checks)
        cells = []
        for key, _ in columns:
            value = row.get(key)
            cells.append("<td>" + escape(str(value) if value is not None else "—") + "</td>")
        body.append('<tr data-active="' + ("true" if row.get("staff_reminder_schedule_ready") is True else "false") + '">' + "".join(cells) + "</tr>")
    headings = "".join("<th>" + escape(label) + "</th>" for _, label in columns)
    output.write_text("""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CP2 contract payment tracker — private review</title>
<style>body{font:15px system-ui;margin:24px;color:#172432;background:#f6f8fb}
h1{font-size:26px}p{max-width:1000px;line-height:1.5}input{padding:10px;width:min(450px,90%)}
.table{overflow:auto;background:white;margin-top:16px}table{border-collapse:collapse;width:100%}
th,td{padding:12px;text-align:left;border-bottom:1px solid #dce3eb;vertical-align:top}
th{background:#e5eef7;white-space:nowrap}td{min-width:110px}small{color:#526475}</style>
<h1>Contract payment tracker — private review</h1>
<p>Paid amounts and remaining balances come from SALES. PAYMENTS is excluded from this tracker.
Dates in Recurring Payments are the dates staff should send reminders. Green only means the date has passed;
it does not mean paid or reminder sent. SALES deposit plus cumulative Balance Paid tracks progress toward
the full sale value. A past reminder date does not prove an overdue payment. Actual payment dates and
individual paid instalments are unavailable. Fully recorded-paid arrangements remain in history and
are excluded from the active reminder list.
No client reminders are enabled.</p><p><small>Source release: """ + escape(run_id) +
        "; reviewed on " + escape(str(rows[0]["tracker_as_of_date"]) if rows else "no rows") +
        ". This is a dated review export; it does not refresh automatically.</small></p>" +
        '<label>Find a client or sale ID <input id="filter" type="search"></label>' +
        '<label> Show <select id="scope"><option value="all">All arrangements / history</option><option value="active">Active reminder schedule</option></select></label>' +
        '<div class="table"><table><thead><tr>' + headings +
        "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>" +
        """<script>function filterRows(){const q=document.getElementById('filter').value.toLowerCase();
const active=document.getElementById('scope').value==='active';
document.querySelectorAll('tbody tr').forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(q)||(active&&r.dataset.active!=='true')});}
document.getElementById('filter').addEventListener('input',filterRows);
document.getElementById('scope').addEventListener('change',filterRows);</script></html>""",
        encoding="utf-8")


def run(output: Path) -> dict:
    output = output.resolve()
    output.relative_to((ROOT / "outputs").resolve())
    if output.exists():
        raise ValueError("Use a new output directory to preserve previous evidence")
    output.mkdir(parents=True)
    settings = bigquery.QueryJobConfig(maximum_bytes_billed=release.LIMIT)
    client = bigquery.Client(project=release.PROJECT, location=release.LOCATION)
    jobs = []
    try:
        query = f"""SELECT run_id, manifest_json FROM `{release.PROJECT}.audit.release_runs`
            WHERE status = 'PUBLISHED' ORDER BY event_at DESC LIMIT 1"""
        published = list(client.query(query, job_config=settings).result(timeout=120))
        if len(published) != 1:
            raise ValueError("No published release")
        manifest = json.loads(published[0]["manifest_json"])
        run_id = published[0]["run_id"]
        if not re.fullmatch(r"[0-9]{14}[0-9a-f]{6}", run_id) or manifest["run_id"] != run_id:
            raise ValueError("Invalid release identity")
        # Verify the stable source wrappers actually point at that release.
        for name in ["sales", "recurring_payments"]:
            table = client.get_table(f"{release.PROJECT}.silver.{name}")
            expected = f"SELECT * FROM `{release.PROJECT}.cp2r_{run_id}_silver.{name}`"
            if table.table_type != "VIEW" or table.view_query.strip() != expected:
                raise ValueError("Stable sources differ from latest published release")
        variables = release.dbt_variables(manifest)
        target = output / "dbt_target"
        command = [str(Path(sys.executable).with_name("dbt.exe" if sys.platform == "win32" else "dbt")),
                   "compile", "--project-dir", str(ROOT / "dbt"),
                   "--profiles-dir", str(ROOT / "dbt"), "--vars", json.dumps(variables),
                   "--select", "+tag:recurring_tracking", "--target-path", str(target),
                   "--no-send-anonymous-usage-stats"]
        with (output / "dbt.log").open("w", encoding="utf-8") as stream:
            subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                           timeout=240, check=True)
        nodes = json.loads((target / "manifest.json").read_text(encoding="utf-8"))["nodes"]
        cache, results = {}, {}
        for name in MODELS:
            verify_tracker_sources("model.nomobug." + name, nodes)
            sql = expand_model("model.nomobug." + name, nodes, cache)
            (output / (name + ".sql")).write_text(sql, encoding="utf-8")
            job = client.query(sql, job_config=settings)
            iterator = job.result(timeout=120)
            fields = [field.name for field in iterator.schema]
            data = [dict(row) for row in iterator]
            write_csv(output / (name + "_private.csv"), data, fields)
            results[name] = data
            jobs.append({"name": name, "job_id": job.job_id,
                         "bytes_processed": job.total_bytes_processed})
        for node_id, node in nodes.items():
            related = any(dependency in {"model.nomobug." + name for name in MODELS}
                          for dependency in node.get("depends_on", {}).get("nodes", []))
            if node_id.startswith("test.") and (related or "recurring_tracking" in node.get("tags", [])):
                if "compiled_code" not in node:
                    continue
                sql = expand_model(node_id, nodes, cache)
                job = client.query(sql, job_config=settings)
                failures = list(job.result(timeout=120))
                jobs.append({"name": node["name"], "job_id": job.job_id,
                             "bytes_processed": job.total_bytes_processed})
                if failures:
                    raise ValueError("Tracker invariant failed: " + node["name"])
        tracker = results["recurring_contract_payment_tracker"]
        render_tracker(tracker, run_id, output / "tracker_private.html")
        summary = {"status": "validated_read_only_preview", "source_release": run_id,
            "source_extracted_at": {key: manifest["extracted_at"][key]
                                    for key in ("SALES", "Recurring Payments")},
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "candidate_contract_rows": len(tracker),
            "explicit_recurring_rows": sum(row["explicit_recurring_arrangement"] for row in tracker),
            "custom_note_rows": sum(row["custom_payment_note"] for row in tracker),
            "retained_nonpositive_balance_rows": sum(row["sales_remaining_balance_rm"] is not None
                and row["sales_remaining_balance_rm"] <= 0 for row in tracker),
            "payment_source": "SALES_ONLY_PAYMENTS_EXCLUDED",
            "actual_payment_dates_available": False,
            "reminder_date_meaning": "STAFF_REMINDER_DATE",
            "green_cell_meaning": "DATE_PASSED_ONLY",
            "active_reminder_schedule_rows": sum(row["staff_reminder_schedule_ready"] is True for row in tracker),
            "reviewed_balance_match_rows": sum(row["recorded_balance_calculation_matches"] is True for row in tracker),
            "balance_review_rows": sum(row["recorded_balance_calculation_matches"] is not True for row in tracker),
            "reminder_schedule_cells": len(results["recurring_payment_date_candidates"]),
            "query_jobs": jobs, "maximum_bytes_billed_per_query": release.LIMIT,
            "automatic_reminders_enabled": False, "published": False}
        (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
