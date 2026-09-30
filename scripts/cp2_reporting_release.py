"""Stage, reconcile and publish an immutable CP2 reporting release.

The only stable dashboard objects changed are Silver/Gold views. Candidate
datasets and Bronze tables are retained for rollback and audit. A failed
pre-promotion check never touches the stable views.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from google.cloud import bigquery
from google.api_core.exceptions import NotFound

from scripts import cp2_pipeline
from scripts import operational_bronze_core
from scripts import validate_business_kpis


ROOT = Path(__file__).resolve().parents[1]
PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
LIMIT = 100 * 1024 * 1024
COLLECTOR_PRINCIPAL = f"cp2-prospective-job@{PROJECT}.iam.gserviceaccount.com"
SNAPSHOT_LIMIT = 64  # Bounded through October with existing history; stop for review.
BASELINE_CALENDAR = "calendar_events_78147d417f3d97d3c1d9ef0be59638fd7850e4195108e1fc7b879483c7f35b66"
BASELINE_GEOCODES = "calendar_event_geocodes_all_v2"
TAB_VARS = {"B2B FOLLOW UP": "b2b_snapshot_table", "SALES": "sales_snapshot_table",
    "PAYMENTS": "payments_snapshot_table", "PAYMENT LINK": "payment_link_snapshot_table",
    "WARRANTY CLAIM": "warranty_claim_snapshot_table",
    "Commercial Clients": "commercial_clients_snapshot_table", "REFUND": "refund_snapshot_table",
    "Recurring Payments": "recurring_payments_snapshot_table"}
AUDIT_SCHEMA = [bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("event_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("manifest_json", "STRING"),
    bigquery.SchemaField("error_type", "STRING")]
BACKUP_SCHEMA = [bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("saved_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("view_backups_json", "STRING", mode="REQUIRED")]


def safe_json(path: Path, value: dict) -> None:
    cp2_pipeline.atomic_json(path, value)


def public_manifest(run_id: str, sheets: dict, calendar: dict, serials: dict) -> dict:
    if set(sheets) != set(TAB_VARS) | {"2026"}:
        raise ValueError("Incomplete approved Sheets inventory")
    result = {"run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(),
        "project": PROJECT, "location": LOCATION, "snapshot_tables": {},
        "extracted_at": {}}
    for tab, item in sheets.items():
        name = item["table_name"]
        if not re.fullmatch(r"[a-z0-9_]+_[0-9a-f]{64}", name):
            raise ValueError("Invalid immutable snapshot name")
        result["snapshot_tables"][tab] = name
        result["extracted_at"][tab] = item["metadata"]["extracted_at"]
    result["snapshot_tables"]["calendar"] = calendar["table_name"]
    result["extracted_at"]["calendar"] = calendar["metadata"]["extracted_at"]
    result["snapshot_tables"]["payments_date_serials"] = serials["table_name"]
    result["extracted_at"]["payments_date_serials"] = serials["extracted_at"]
    return result


def dbt_variables(manifest: dict) -> dict:
    tables = manifest["snapshot_tables"]
    variables = {key: tables[tab] for tab, key in TAB_VARS.items()}
    variables.update({"calendar_snapshot_table": tables["calendar"],
        "payments_date_serials_snapshot_table": tables["payments_date_serials"],
        "prospects_snapshot_id": tables["2026"].rsplit("_", 1)[1],
        "prospects_snapshot_extracted_at": manifest["extracted_at"]["2026"],
        "release_schema_prefix": "cp2r_" + manifest["run_id"] + "_",
        "release_run_id": manifest["run_id"]})
    for tab, key in TAB_VARS.items():
        variables["release_extracted_at_" + key.removesuffix("_snapshot_table")] = manifest["extracted_at"][tab]
    variables["release_extracted_at_prospects"] = manifest["extracted_at"]["2026"]
    variables["release_extracted_at_calendar"] = manifest["extracted_at"]["calendar"]
    variables["release_extracted_at_payments_date_serials"] = manifest["extracted_at"]["payments_date_serials"]
    variables["calendar_geocodes_table"] = manifest["derived_quality_tables"]["calendar_geocodes"]
    return variables


def audit(client: bigquery.Client, run_id: str, status: str, manifest: dict | None = None,
          error: BaseException | None = None) -> None:
    table = f"{PROJECT}.audit.release_runs"
    row = {"run_id": run_id, "event_at": datetime.now(timezone.utc).isoformat(),
        "status": status, "manifest_json": json.dumps(manifest, sort_keys=True) if manifest else None,
        "error_type": type(error).__name__ if error else None}
    config = bigquery.LoadJobConfig(schema=AUDIT_SCHEMA, write_disposition="WRITE_APPEND")
    client.load_table_from_json([row], table, job_config=config, location=LOCATION).result(timeout=120)


def ensure_audit(client: bigquery.Client) -> None:
    dataset_id = f"{PROJECT}.audit"
    try:
        dataset = client.get_dataset(dataset_id)
    except NotFound:
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = LOCATION
        dataset = client.create_dataset(dataset, exists_ok=True)
    if dataset.location.lower() != LOCATION:
        raise ValueError("Audit dataset region mismatch")
    for name, schema in (("release_runs", AUDIT_SCHEMA), ("release_backups", BACKUP_SCHEMA)):
        table_id = dataset_id + "." + name
        try:
            table = client.get_table(table_id)
        except NotFound:
            table = client.create_table(bigquery.Table(table_id, schema=schema), exists_ok=True)
        if [(field.name, field.field_type, field.mode) for field in table.schema] != [
                (field.name, field.field_type, field.mode) for field in schema]:
            raise ValueError("Audit table schema mismatch")


def persist_view_backups(client: bigquery.Client, run_id: str, records: list[dict]) -> None:
    row = {"run_id": run_id, "saved_at": datetime.now(timezone.utc).isoformat(),
        "view_backups_json": json.dumps(records, sort_keys=True)}
    settings = bigquery.LoadJobConfig(schema=BACKUP_SCHEMA, write_disposition="WRITE_APPEND")
    client.load_table_from_json([row], f"{PROJECT}.audit.release_backups",
        job_config=settings, location=LOCATION).result(timeout=120)


def load_view_backups(client: bigquery.Client, run_id: str) -> list[dict]:
    settings = bigquery.QueryJobConfig(maximum_bytes_billed=LIMIT,
        query_parameters=[bigquery.ScalarQueryParameter("run_id", "STRING", run_id)])
    query = f"SELECT view_backups_json FROM `{PROJECT}.audit.release_backups` WHERE run_id = @run_id"
    rows = list(client.query(query, job_config=settings, location=LOCATION).result(timeout=120))
    if len(rows) != 1:
        raise ValueError("Expected one durable backup for release")
    return json.loads(rows[0]["view_backups_json"])


def release_statuses(client: bigquery.Client, run_id: str) -> list[str]:
    settings = bigquery.QueryJobConfig(maximum_bytes_billed=LIMIT,
        query_parameters=[bigquery.ScalarQueryParameter("run_id", "STRING", run_id)])
    query = f"SELECT status FROM `{PROJECT}.audit.release_runs` WHERE run_id = @run_id ORDER BY event_at"
    return [row["status"] for row in client.query(query, job_config=settings,
        location=LOCATION).result(timeout=120)]


def snapshot_preflight(client: bigquery.Client, items: list[dict]) -> None:
    dataset = client.get_dataset(f"{PROJECT}.bronze")
    if dataset.location.lower() != LOCATION or dataset.default_table_expiration_ms is not None:
        raise ValueError("Bronze region or expiry mismatch")
    existing = {table.table_id for table in client.list_tables(dataset)}
    for item in items:
        name = item["table_name"]
        if name not in existing and sum(x.startswith(item["prefix"] + "_") for x in existing) >= SNAPSHOT_LIMIT:
            raise ValueError(f"Snapshot retention review required for {item['prefix']}")


def remap_geocodes(client: bigquery.Client, calendar_table: str) -> dict:
    """Carry coordinates only for identical Calendar identities and address text."""
    if not re.fullmatch(r"calendar_events_[0-9a-f]{64}", calendar_table):
        raise ValueError("Invalid Calendar snapshot table")
    dataset = client.get_dataset(f"{PROJECT}.quality")
    if dataset.location.lower() != LOCATION:
        raise ValueError("Quality dataset region mismatch")
    table_name = "calendar_event_geocodes_for_" + calendar_table.rsplit("_", 1)[1]
    table_id = f"{PROJECT}.quality.{table_name}"
    metadata = {"source_calendar_table": calendar_table, "baseline_calendar_table": BASELINE_CALENDAR,
        "baseline_geocodes_table": BASELINE_GEOCODES, "reuse_rule": "same_calendar_event_identity_and_exact_summary_location_description"}
    try:
        table = client.get_table(table_id)
    except NotFound:
        query = f"""
            SELECT n.calendar_event_row, g.* EXCEPT(calendar_event_row)
            FROM `{PROJECT}.quality.{BASELINE_GEOCODES}` AS g
            JOIN `{PROJECT}.bronze.{BASELINE_CALENDAR}` AS old_event
              USING (calendar_event_row)
            JOIN `{PROJECT}.bronze.{calendar_table}` AS n
              ON old_event.calendar_id = n.calendar_id AND old_event.event_id = n.event_id
            WHERE old_event.summary IS NOT DISTINCT FROM n.summary
              AND old_event.location IS NOT DISTINCT FROM n.location
              AND old_event.description IS NOT DISTINCT FROM n.description
        """
        settings = bigquery.QueryJobConfig(destination=table_id, write_disposition="WRITE_EMPTY",
            maximum_bytes_billed=LIMIT)
        client.query(query, job_config=settings, location=LOCATION).result(timeout=180)
        table = client.get_table(table_id)
        table.description = json.dumps(metadata, sort_keys=True)
        client.update_table(table, ["description"])
    if json.loads(table.description or "{}") != metadata or not table.num_rows:
        raise ValueError("Calendar geocode remap lineage/row count mismatch")
    return {"table_name": table_name, "rows": table.num_rows, "reuse_rule": metadata["reuse_rule"]}


def dbt_build(variables: dict, run_dir: Path) -> None:
    dbt = Path(sys.executable).with_name("dbt.exe" if sys.platform == "win32" else "dbt")
    operational_models = sorted(path.stem for path in (ROOT / "dbt" / "models").glob("*.sql"))
    command = [str(dbt), "build", "--project-dir", str(ROOT / "dbt"),
        "--profiles-dir", str(ROOT / "dbt"), "--vars", json.dumps(variables),
        "--select", "+tag:gold", *operational_models,
        "--exclude", "tag:analytics_ml",
        "--target-path", str(run_dir / "dbt_target")]
    environment = os.environ.copy()
    environment["NOMOBUG_BQ_MAX_BYTES_BILLED"] = str(LIMIT)
    with (run_dir / "dbt.log").open("w", encoding="utf-8") as log:
        finished = subprocess.run(command, cwd=ROOT, env=environment, stdout=log,
            stderr=subprocess.STDOUT, timeout=840, check=False)
    if finished.returncode:
        raise RuntimeError(f"dbt candidate build failed ({finished.returncode}); see private dbt.log")


def view_inventory(client: bigquery.Client, stage_prefix: str) -> list[tuple[str, str, str]]:
    inventory = []
    for schema in ("silver", "gold"):
        candidate = stage_prefix + schema
        dataset = client.get_dataset(f"{PROJECT}.{candidate}")
        if dataset.location.lower() != LOCATION:
            raise ValueError("Candidate dataset region mismatch")
        for table in client.list_tables(dataset):
            if table.table_type == "VIEW":
                inventory.append((schema, table.table_id, candidate))
    if not inventory or not any(item[0] == "gold" for item in inventory):
        raise ValueError("No candidate Gold views")
    return inventory


def grant_collector_candidate_reader(client: bigquery.Client, stage_prefix: str) -> None:
    """Grant the private collector read access before stable views point here."""
    if not re.fullmatch(r"cp2r_[0-9]{14}[0-9a-f]{6}_", stage_prefix):
        raise ValueError("Invalid candidate dataset prefix")
    for schema in ("silver", "gold"):
        dataset_id = f"{PROJECT}.{stage_prefix}{schema}"
        dataset = client.get_dataset(dataset_id)
        if dataset.location.lower() != LOCATION:
            raise ValueError("Candidate dataset region mismatch")
        entries = list(dataset.access_entries)
        matching = [entry for entry in entries if entry.entity_type == "userByEmail"
                    and entry.entity_id == COLLECTOR_PRINCIPAL]
        if matching and (len(matching) != 1 or matching[0].role != "READER"):
            raise ValueError("Unexpected collector candidate access")
        if not matching:
            entries.append(bigquery.AccessEntry(role="READER", entity_type="userByEmail",
                                                entity_id=COLLECTOR_PRINCIPAL))
            dataset.access_entries = entries
            client.update_dataset(dataset, ["access_entries"])
        confirmed = client.get_dataset(dataset_id)
        if not any(entry.entity_type == "userByEmail" and
                   entry.entity_id == COLLECTOR_PRINCIPAL and entry.role == "READER"
                   for entry in confirmed.access_entries):
            raise ValueError("Collector candidate access was not persisted")


def promote(client: bigquery.Client, inventory: list[tuple[str, str, str]], run_dir: Path) -> None:
    """Repoint stable views; restore every changed definition on partial failure."""
    backups = []
    for schema, name, candidate in inventory:
        stable_id = f"{PROJECT}.{schema}.{name}"
        try:
            old = client.get_table(stable_id)
        except NotFound:
            backups.append({"schema": schema, "name": name, "existed": False})
        else:
            if old.table_type != "VIEW":
                # Materialized facts and seeds remain in their candidate dataset;
                # only privacy-approved reporting views get stable wrappers.
                raise ValueError(f"Stable object is not a view: {schema}.{name}")
            backups.append({"schema": schema, "name": name, "existed": True,
                "view_query": old.view_query, "description": old.description or ""})
    safe_json(run_dir / "view_backups_private.json", {"views": backups})
    persist_view_backups(client, run_dir.name, backups)
    changed = []
    try:
        for schema, name, candidate in inventory:
            stable_id = f"{PROJECT}.{schema}.{name}"
            query = f"SELECT * FROM `{PROJECT}.{candidate}.{name}`"
            description = "CP2 approved release wrapper; source manifest in audit.release_runs"
            record = next(r for r in backups if r["schema"] == schema and r["name"] == name)
            if record["existed"]:
                table = client.get_table(stable_id)
                table.view_query, table.description = query, description
                client.update_table(table, ["view_query", "description"])
            else:
                table = bigquery.Table(stable_id)
                table.view_query, table.description = query, description
                client.create_table(table)
            changed.append((schema, name))
    except Exception:
        failures = []
        for record in reversed(backups):
            if (record["schema"], record["name"]) not in changed:
                continue
            stable_id = f"{PROJECT}.{record['schema']}.{record['name']}"
            try:
                if not record["existed"]:
                    client.delete_table(stable_id)
                else:
                    old = client.get_table(stable_id)
                    old.view_query, old.description = record["view_query"], record["description"]
                    client.update_table(old, ["view_query", "description"])
            except Exception as rollback_error:
                failures.append(f"{record['schema']}.{record['name']}: {type(rollback_error).__name__}")
        if failures:
            raise RuntimeError("Partial promotion rollback failed: " + ", ".join(failures))
        raise


def finish_release(client: bigquery.Client, run_dir: Path, manifest: dict) -> dict:
    run_id = manifest["run_id"]
    variables = dbt_variables(manifest)
    dbt_build(variables, run_dir)
    stage_prefix = variables["release_schema_prefix"]
    grant_collector_candidate_reader(client, stage_prefix)
    validation = validate_business_kpis.validate(run_dir / "kpi_validation",
        project=PROJECT, location=LOCATION,
        silver_schema=stage_prefix + "silver", gold_schema=stage_prefix + "gold",
        serials_table=manifest["snapshot_tables"]["payments_date_serials"])
    if validation["status"] != "pass_with_business_caveats":
        raise ValueError("Candidate KPI reconciliation failed")
    audit(client, run_id, "VALIDATED", manifest)
    inventory = view_inventory(client, stage_prefix)
    promote(client, inventory, run_dir)
    audit(client, run_id, "PUBLISHED", manifest)
    safe_json(run_dir / "result.json", {"status": "PUBLISHED", "run_id": run_id,
        "view_count": len(inventory), "manifest": manifest})
    return {"status": "PUBLISHED", "run_id": run_id, "view_count": len(inventory)}


def run() -> dict:
    if os.getenv("NOMOBUG_BQ_UPLOAD_APPROVED") != "yes":
        raise ValueError("NOMOBUG_BQ_UPLOAD_APPROVED=yes required")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6]
    run_dir = ROOT / "outputs" / "reporting_release" / run_id
    run_dir.mkdir(parents=True)
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    manifest = None
    try:
        ensure_audit(client)
        audit(client, run_id, "STARTED")
        cp2_pipeline.source_stage(run_dir)
        sheets = cp2_pipeline.read(run_dir / "sheets_private.json")["snapshots"]
        calendar = cp2_pipeline.read(run_dir / "calendar_private.json")
        from scripts import load_calendar_bronze
        from google.cloud.bigquery import SchemaField
        for item in sheets.values():
            item["schema"] = [SchemaField.from_api_repr(field) for field in item["schema"]]
        regenerated = load_calendar_bronze._snapshot(
            calendar["records"], [{"id": value} for value in calendar["source_calendar_ids"]],
            load_calendar_bronze.DEFAULT_START,
            datetime.fromisoformat(calendar["metadata"]["window_end"]).date())
        if regenerated["table_name"] != calendar["table_name"]:
            raise ValueError("Calendar snapshot identity changed before upload")
        calendar["schema"] = regenerated["schema"]
        calendar["prefix"] = "calendar_events"
        all_items = list(sheets.values()) + [calendar]
        snapshot_preflight(client, all_items)
        for item in sheets.values():
            operational_bronze_core.load_and_verify(client, PROJECT, LOCATION, item)
        load_calendar_bronze._verify_load(client, PROJECT, LOCATION, calendar)
        geocodes = remap_geocodes(client, calendar["table_name"])
        receipt_path = run_dir / "serials_private.json"
        command = [sys.executable, str(ROOT / "scripts/load_payment_date_serials.py"), "--upload",
            "--source-table", sheets["PAYMENTS"]["table_name"], "--receipt-json", str(receipt_path)]
        with (run_dir / "serials.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                timeout=300, check=False)
        if result.returncode:
            raise RuntimeError("Payment date sidecar failed; see private serials.log")
        serials = cp2_pipeline.read(receipt_path)
        manifest = public_manifest(run_id, sheets, calendar, serials)
        manifest["derived_quality_tables"] = {"calendar_geocodes": geocodes["table_name"]}
        manifest["quality_coverage"] = {"reused_calendar_geocodes": geocodes["rows"],
            "calendar_rows": len(calendar["records"]), "reuse_rule": geocodes["reuse_rule"]}
        safe_json(run_dir / "release_manifest.json", manifest)
        audit(client, run_id, "BRONZE_VERIFIED", manifest)
        return finish_release(client, run_dir, manifest)
    except (Exception, SystemExit) as error:
        safe_json(run_dir / "failure.json", {"status": "FAILED", "run_id": run_id,
            "error_type": type(error).__name__, "message": str(error)})
        audit(client, run_id, "FAILED", manifest, error)
        raise
    finally:
        client.close()


def resume(run_id: str) -> dict:
    """Retry a locally interrupted candidate without rereading or changing source pins."""
    if os.getenv("NOMOBUG_BQ_UPLOAD_APPROVED") != "yes":
        raise ValueError("NOMOBUG_BQ_UPLOAD_APPROVED=yes required")
    if not re.fullmatch(r"[0-9]{14}[0-9a-f]{6}", run_id):
        raise ValueError("Invalid run ID")
    run_dir = ROOT / "outputs" / "reporting_release" / run_id
    manifest = cp2_pipeline.read(run_dir / "release_manifest.json")
    if manifest["run_id"] != run_id or manifest["project"] != PROJECT or manifest["location"] != LOCATION:
        raise ValueError("Release manifest identity mismatch")
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        statuses = release_statuses(client, run_id)
        if "PUBLISHED" in statuses or "ROLLED_BACK" in statuses:
            raise ValueError("Release already published or rolled back")
        for table_name in manifest["snapshot_tables"].values():
            table = client.get_table(f"{PROJECT}.bronze.{table_name}")
            if table.table_type != "TABLE" or json.loads(table.description or "{}").get("snapshot_id") != table_name.rsplit("_", 1)[1]:
                raise ValueError("Resume source snapshot identity mismatch")
        geocodes = manifest["derived_quality_tables"]["calendar_geocodes"]
        client.get_table(f"{PROJECT}.quality.{geocodes}")
        audit(client, run_id, "RESUMED", manifest)
        return finish_release(client, run_dir, manifest)
    except Exception as error:
        safe_json(run_dir / "failure.json", {"status": "FAILED", "run_id": run_id,
            "error_type": type(error).__name__, "message": str(error)})
        audit(client, run_id, "FAILED", manifest, error)
        raise
    finally:
        client.close()


def rollback(run_id: str) -> dict:
    if not re.fullmatch(r"[0-9]{14}[0-9a-f]{6}", run_id):
        raise ValueError("Invalid run ID")
    if os.getenv("NOMOBUG_BQ_UPLOAD_APPROVED") != "yes":
        raise ValueError("NOMOBUG_BQ_UPLOAD_APPROVED=yes required for rollback")
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        records = load_view_backups(client, run_id)
        # Refuse to revert a newer release or an independently edited view.
        for record in records:
            stable = client.get_table(f"{PROJECT}.{record['schema']}.{record['name']}")
            expected = f"SELECT * FROM `{PROJECT}.cp2r_{run_id}_{record['schema']}.{record['name']}`"
            if stable.table_type != "VIEW" or stable.view_query.strip() != expected:
                raise ValueError("Published view changed since this release; rollback stopped")
        for record in reversed(records):
            stable_id = f"{PROJECT}.{record['schema']}.{record['name']}"
            if not record.get("existed", True):
                client.delete_table(stable_id)
            else:
                stable = client.get_table(stable_id)
                stable.view_query, stable.description = record["view_query"], record["description"]
                client.update_table(stable, ["view_query", "description"])
        audit(client, run_id, "ROLLED_BACK")
        return {"status": "ROLLED_BACK", "run_id": run_id, "view_count": len(records)}
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=("run", "resume", "rollback"), default="run")
    parser.add_argument("--run-id", help="Required for resume/rollback")
    args = parser.parse_args()
    try:
        result = rollback(args.run_id) if args.action == "rollback" else resume(args.run_id) if args.action == "resume" else run()
        print(json.dumps(result))
    except Exception as exc:
        print(f"Reporting release failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
