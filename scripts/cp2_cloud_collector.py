"""Private Cloud Run entry point for the frozen prospective collector.

Object storage is the durable source of immutable receipts. BigQuery contains a
restricted, idempotent index for evaluation; no customer fields enter logs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import threading
import uuid

from google.api_core.exceptions import PreconditionFailed
from google.cloud import bigquery, storage

from scripts import cp2_pipeline as pipeline
from scripts import cp2_pipeline_tick as tick

ROOT = pipeline.ROOT
PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
AUDIT_TABLE = f"{PROJECT}.audit.prospective_predictions"
ARTIFACTS = {
    "outputs/cp2-v2/source_refresh_20260927/old_calendar_private.json",
    "outputs/cp2-v2/prospective_callback_v2/bundle.json",
    "outputs/cp2-v2/prospective_callback_v2/challenger_all_history.joblib",
    "outputs/cp2-v2/prospective_callback_v2/priority_all_history.joblib",
    "outputs/cp2-v2/prospective_callback_v2/reference_all_history.joblib",
    "outputs/cp2-v2/prospective_callback_v2/training_replay_private.csv",
}
STATE = ("watch_events.json", "last_tick.json", "last_attempt.json", "last_success.json")


def artifact_prefix():
    """Version the private artifact inventory by its exact live-feature pin."""
    pin = pipeline.read(ROOT / "config/cp2_live_feature_contract.json")
    canonical = json.dumps(pin, sort_keys=True, separators=(",", ":")).encode()
    return "artifacts/" + sha256(canonical).hexdigest()[:16] + "/"


def _download(blob, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(blob.download_as_bytes())


def hydrate_artifacts(bucket):
    """Load only audited private artifacts; never copy them into the image."""
    registry = pipeline.read(ROOT / "config/cp2_model_current.json")
    pin = pipeline.read(ROOT / "config/cp2_live_feature_contract.json")
    compiled = {f"dbt/target/compiled/nomobug/models/{name}" for name in pin["compiled_query_hashes"]}
    expected = ARTIFACTS | compiled
    prefix = artifact_prefix()
    manifest = json.loads(bucket.blob(prefix + "manifest.json").download_as_text())
    pinned = pipeline.read(ROOT / "config/cp2_cloud_artifacts.json")
    if set(manifest) != expected or manifest != pinned:
        raise ValueError("Cloud artifact inventory differs from the frozen collector contract")
    for relative, digest in manifest.items():
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Invalid cloud artifact digest")
        target = ROOT / relative
        if not target.exists() or sha256(target.read_bytes()).hexdigest() != digest:
            _download(bucket.blob(prefix + relative), target)
        if sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("Cloud artifact integrity mismatch")
    if pipeline.digest(ROOT / "outputs/cp2-v2/prospective_callback_v2/bundle.json") != registry["bundle_sha256"]:
        raise ValueError("Cloud model differs from frozen registry")
    for name, digest in pin["compiled_query_hashes"].items():
        path = ROOT / "dbt/target/compiled/nomobug/models" / name
        if sha256(path.read_text(encoding="utf-8").encode()).hexdigest() != digest:
            raise ValueError("Cloud compiled SQL differs from live feature pin")


def hydrate_state(bucket):
    base = pipeline.BASE
    for name in STATE:
        (base / name).unlink(missing_ok=True)
        blob = bucket.blob("state/" + name)
        if blob.exists():
            _download(blob, base / name)
    logs = base / "prospective_logs"
    if logs.exists():
        for path in logs.glob("*.json"):
            path.unlink()
    for blob in bucket.list_blobs(prefix="prospective_logs/"):
        if re.fullmatch(r"prospective_logs/[a-f0-9]{64}\.json", blob.name):
            _download(blob, base / blob.name)
    day = datetime.now(timezone.utc).astimezone(pipeline.LOCAL).date().isoformat()
    for name in ("weather_private.json", "weather_receipt.json"):
        target = base / "weather_cache" / day / name
        blob = bucket.blob(f"weather_cache/{day}/{name}")
        if not target.exists() and blob.exists():
            _download(blob, target)


def persist_state(bucket):
    base = pipeline.BASE
    for name in STATE:
        path = base / name
        if path.exists():
            bucket.blob("state/" + name).upload_from_filename(str(path), content_type="application/json")
    day = datetime.now(timezone.utc).astimezone(pipeline.LOCAL).date().isoformat()
    for name in ("weather_private.json", "weather_receipt.json"):
        path = base / "weather_cache" / day / name
        if path.exists():
            blob = bucket.blob(f"weather_cache/{day}/{name}")
            if not blob.exists():
                blob.upload_from_filename(str(path), content_type="application/json",
                                          if_generation_match=0)


def mirror_predictions(bucket):
    """Repair the BigQuery index from immutable receipts after any partial failure."""
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    existing_query = f"SELECT prediction_key_sha256, record_sha256 FROM `{AUDIT_TABLE}`"
    existing = {row.prediction_key_sha256: row.record_sha256 for row in client.query(
        existing_query, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=100 * 1024 * 1024)).result(timeout=60)}
    count = 0
    for path in (pipeline.BASE / "prospective_logs").glob("*.json"):
        record = pipeline.read(path)
        if record["record_sha256"] != tick.record_digest(record):
            raise ValueError("Prospective receipt integrity mismatch")
        remote = bucket.blob("prospective_logs/" + path.name)
        if not remote.exists() or sha256(remote.download_as_bytes()).hexdigest() != sha256(path.read_bytes()).hexdigest():
            raise ValueError("BigQuery index requires an exact durable receipt")
        row = record["row"]
        key = path.stem
        if key in existing:
            if existing[key] != record["record_sha256"]:
                raise ValueError("BigQuery prediction index conflicts with immutable receipt")
            continue
        query = f"""MERGE `{AUDIT_TABLE}` AS t
            USING (SELECT @key AS prediction_key_sha256) AS s
            ON t.prediction_key_sha256 = s.prediction_key_sha256
            WHEN NOT MATCHED THEN INSERT
            (prediction_key_sha256, record_sha256, bundle_sha256, logged_at_utc,
             anchor_date, risk_probability, receipt_gcs_uri)
            VALUES (@key, @record, @bundle, @logged, @anchor, @risk, @uri)"""
        parameters = [
            bigquery.ScalarQueryParameter("key", "STRING", key),
            bigquery.ScalarQueryParameter("record", "STRING", record["record_sha256"]),
            bigquery.ScalarQueryParameter("bundle", "STRING", record["bundle_sha256"]),
            bigquery.ScalarQueryParameter("logged", "TIMESTAMP", record["logged_at_utc"]),
            bigquery.ScalarQueryParameter("anchor", "DATE", str(row["anchor_date"])[:10]),
            bigquery.ScalarQueryParameter("risk", "FLOAT64", float(row["challenger_all_history"])),
            bigquery.ScalarQueryParameter("uri", "STRING", f"gs://{bucket.name}/prospective_logs/{path.name}"),
        ]
        client.query(query, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=100 * 1024 * 1024, query_parameters=parameters)).result(timeout=60)
        existing[key] = record["record_sha256"]
        count += 1
    return count


def run_tick(*, full_smoke=False, final_evaluation=False):
    name = os.environ["NOMOBUG_CP2_COLLECTOR_BUCKET"]
    bucket = storage.Client(project=PROJECT).bucket(name)
    lock = bucket.blob("control/active_tick.json")
    lock_payload = json.dumps({"started_at_utc": datetime.now(timezone.utc).isoformat(),
                               "id": uuid.uuid4().hex})
    try:
        lock.upload_from_string(lock_payload, content_type="application/json", if_generation_match=0)
    except PreconditionFailed:
        lock.reload()
        if datetime.now(timezone.utc) - lock.updated < timedelta(minutes=22):
            return {"status": "another_cloud_tick_active"}
        # Each worker has a hard 18-minute self-termination below. A lock older
        # than 22 minutes is abandoned and may be replaced using its generation.
        try:
            lock.delete(if_generation_match=lock.generation)
            lock.upload_from_string(lock_payload, content_type="application/json", if_generation_match=0)
        except PreconditionFailed:
            return {"status": "another_cloud_tick_active"}
    generation = lock.generation
    watchdog = threading.Timer(18 * 60, os._exit, args=(1,))
    watchdog.daemon = True
    watchdog.start()
    try:
        hydrate_artifacts(bucket)
        hydrate_state(bucket)
        if final_evaluation:
            destination = bucket.blob("evaluations/cloud_2026.json")
            if destination.exists():
                return {"status": "already_finalized"}
            result_path = ROOT / "outputs/cp2-v2/prospective_callback_v2/prospective_cloud_evaluation.json"
            # Only a durable cloud result is final. A warm instance may retain
            # a local result from a request that failed before its upload.
            result_path.unlink(missing_ok=True)
            evaluated = pipeline.final_evaluation(cloud=True)
            destination.upload_from_filename(str(result_path), content_type="application/json",
                                             if_generation_match=0)
            result = {"status": "finalized", "cohort_anchors": evaluated["cohort_anchors"],
                      "evaluation_rows": evaluated["evaluation_rows"]}
        elif full_smoke:
            state = pipeline.run()
            result = {"status": state["status"], "run_id": state["run_id"],
                      "full_pipeline_smoke": True,
                      "prospectively_logged": state["stages"]["prospective"]["receipt"].get("logged_rows", 0)}
            bucket.blob("state/full_smoke.json").upload_from_string(
                json.dumps(result), content_type="application/json")
        else:
            result = tick.poll()
        persist_state(bucket)
        result["bigquery_indexed_predictions"] = mirror_predictions(bucket)
        return result
    finally:
        watchdog.cancel()
        lock.delete(if_generation_match=generation)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path not in {"/tick", "/smoke-full", "/evaluate-cloud"}:
            self.send_error(404)
            return
        try:
            result = run_tick(full_smoke=self.path == "/smoke-full",
                              final_evaluation=self.path == "/evaluate-cloud")
            status = (409 if result.get("status") == "another_cloud_tick_active" else
                      500 if result.get("status") in {
                          "refresh_failed", "refresh_without_complete_prospective_logging"} else 200)
        except Exception as error:
            # Log only the exception class; source bodies and identifiers stay private.
            result = {"status": "failed", "error_type": type(error).__name__}
            status = 500
        payload = json.dumps(result).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    HTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
