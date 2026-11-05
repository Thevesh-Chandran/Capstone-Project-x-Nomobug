"""Stage aggregate-only additions, check them, then publish reversible wrappers.

Existing reporting parents remain untouched. The attention view reads stable
approved parents so it follows successful daily releases without a new collector.
Every query is bounded to 100 MiB. No IAM or report sharing changes are made.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from google.cloud import bigquery
from google.api_core.exceptions import NotFound

from scripts.cp2_reporting_release import PROJECT, LOCATION, LIMIT, verify_management_privacy
from scripts.build_cp2_decision_support import ROOT, sha

MODELS = ["dashboard_model_review", "dashboard_feature_comparison", "dashboard_followup_baselines", "dashboard_attention"]
SEEDS = ["cp2_review_capacity", "cp2_environment_comparison", "cp2_followup_baselines"]


def query(client, sql):
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False), timeout=60)
    if dry.total_bytes_processed > LIMIT:
        raise ValueError("Query exceeds 100 MiB guard")
    job = client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=LIMIT,
        job_timeout_ms=300000), job_retry=None, timeout=60)
    return list(job.result(timeout=330)), {"job_id": job.job_id, "bytes": job.total_bytes_processed}


def publish():
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "outputs/project_value_review" / run
    out.mkdir(parents=True, exist_ok=False)
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    prefix = "decision_" + run.lower() + "_"
    receipt = {"run": run, "status": "staging", "jobs": [], "sources": {}, "backups": {}}
    target = ROOT / "dbt/target/compiled/nomobug"
    replacement = {f"`{PROJECT}`.`gold`.`{n}`": f"`{PROJECT}.quality.{prefix+n}`" for n in SEEDS + MODELS}

    def staged(sql):
        for old, new in replacement.items():
            sql = sql.replace(old, new)
        return sql

    def record():
        (out / "publish_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    changed = []
    try:
        for name in SEEDS:
            path = ROOT / "dbt/seeds" / (name + ".csv")
            receipt["sources"][name] = sha(path)
            with path.open("rb") as handle:
                job = client.load_table_from_file(handle, f"{PROJECT}.quality.{prefix+name}",
                    job_config=bigquery.LoadJobConfig(source_format="CSV", skip_leading_rows=1,
                        autodetect=True, write_disposition="WRITE_EMPTY"))
                job.result(timeout=120)
        for name in MODELS:
            sql = staged((target / "models/gold" / (name + ".sql")).read_text())
            t = bigquery.Table(f"{PROJECT}.quality.{prefix+name}")
            t.view_query = sql
            t.description = "CP2 staged aggregate decision support " + run
            client.create_table(t)
            # Reuse the management schema gate against each candidate object.
            fields = client.get_table(t.reference).schema
            verify_management_privacy(SimpleNamespace(get_table=lambda _: SimpleNamespace(schema=fields)),
                                      [("gold", name, "quality")])
            rows, log = query(client, f"SELECT COUNT(*) AS row_count FROM `{PROJECT}.quality.{prefix+name}`")
            receipt["jobs"].append(log)
            receipt.setdefault("row_counts", {})[name] = rows[0]["row_count"]
        sql = staged((target / "tests/decision_support_invariants.sql").read_text())
        failures, log = query(client, sql)
        receipt["jobs"].append(log)
        if failures:
            raise ValueError("Decision-support aggregate invariants failed")
        # Independent parent-to-attention reconciliation at each separate grain.
        reconcile = f"""WITH a AS (SELECT * FROM `{PROJECT}.quality.{prefix}dashboard_attention`)
        SELECT 'bookings' AS failure FROM (SELECT 1) WHERE
          (SELECT COALESCE(SUM(item_count),0) FROM a WHERE category='Upcoming visits') !=
          (SELECT COALESCE(SUM(scheduled_event_rows),0) FROM `{PROJECT}.gold.dashboard_scheduling_capacity`
           WHERE service_date >= CURRENT_DATE('Asia/Kuala_Lumpur') AND service_date < DATE_ADD(CURRENT_DATE('Asia/Kuala_Lumpur'), INTERVAL 7 DAY))
        UNION ALL SELECT 'reminders' FROM (SELECT 1) WHERE
          (SELECT COALESCE(SUM(item_count),0) FROM a WHERE category='Payment reminders') !=
          (SELECT COALESCE(SUM(scheduled_reminder_date_rows),0) FROM `{PROJECT}.gold.dashboard_recurring_reminder_schedule`
           WHERE reminder_date >= CURRENT_DATE('Asia/Kuala_Lumpur') AND reminder_date < DATE_ADD(CURRENT_DATE('Asia/Kuala_Lumpur'), INTERVAL 7 DAY))
        UNION ALL SELECT 'balances' FROM (SELECT 1) WHERE
          (SELECT COALESCE(SUM(amount_rm),0) FROM a WHERE category='Recorded contract balances') !=
          (SELECT COALESCE(SUM(positive_recorded_remaining_balance_rm),0) FROM `{PROJECT}.gold.dashboard_recurring_payment_quality`)"""
        failures, log = query(client, reconcile)
        receipt["jobs"].append(log)
        if failures:
            raise ValueError("Independent parent reconciliation failed")
        for name in MODELS:
            try:
                old = client.get_table(f"{PROJECT}.gold.{name}")
                if old.table_type != "VIEW":
                    raise ValueError("Existing target is not a view")
                receipt["backups"][name] = {"query": old.view_query, "description": old.description}
            except NotFound:
                receipt["backups"][name] = None
        receipt["status"] = "validated_before_publish"
        record()
        for name in MODELS:
            identifier = f"{PROJECT}.gold.{name}"
            table = bigquery.Table(identifier)
            table.view_query = f"SELECT * FROM `{PROJECT}.quality.{prefix+name}`"
            table.description = "CP2 aggregate decision support; receipt " + run + "; stable parents refresh daily"
            if receipt["backups"][name] is None:
                client.create_table(table)
            else:
                client.update_table(table, ["view_query", "description"])
            changed.append(name)
        verify_management_privacy(client, [("gold", n, "gold") for n in MODELS])
        receipt["status"] = "published"
        record()
        print(json.dumps({"status": receipt["status"], "row_counts": receipt["row_counts"], "receipt": str(out / 'publish_receipt.json')}))
    except BaseException:
        for name in reversed(changed):
            backup = receipt["backups"][name]
            identifier = f"{PROJECT}.gold.{name}"
            if backup is None:
                client.delete_table(identifier)
            else:
                table = bigquery.Table(identifier)
                table.view_query, table.description = backup["query"], backup["description"]
                client.update_table(table, ["view_query", "description"])
        receipt["status"] = "failed_published_wrappers_restored"
        record()
        raise
    finally:
        client.close()


if __name__ == "__main__":
    publish()
