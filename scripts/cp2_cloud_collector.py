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
JOURNAL_MAX_BYTES = 256 * 1024
ELIGIBILITY_AUDIT_MAX_BYTES = 1024 * 1024


def persist_run_journal(bucket, run_dir):
    """Keep bounded, immutable stage evidence without source rows or error bodies."""
    path = run_dir / "run.json"
    if not path.exists():
        return
    raw = path.read_bytes()
    if len(raw) > JOURNAL_MAX_BYTES:
        raise ValueError("Collector run manifest exceeds journal bound")
    state = json.loads(raw)
    run_id = state.get("run_id", "")
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z_[a-f0-9]{8}", run_id) or run_dir.name != run_id:
        raise ValueError("Invalid collector journal run identity")
    journal = {"schema_version": 1, "run_id": run_id,
               "source_manifest_sha256": sha256(raw).hexdigest(), "stages": {}}
    for field in ("status", "started_at_utc", "finished_at_utc", "attempts", "failed_stage", "error_type"):
        if field in state:
            journal[field] = state[field]
    for name, stage in state.get("stages", {}).items():
        if name not in pipeline.STAGES:
            raise ValueError("Unknown collector journal stage")
        record = {key: stage[key] for key in ("status", "started_at_utc", "finished_at_utc") if key in stage}
        if "receipt" in stage:
            receipt = json.dumps(stage["receipt"], sort_keys=True, separators=(",", ":")).encode()
            record["receipt_sha256"] = sha256(receipt).hexdigest()
            if name == 'prospective':
                safe = stage['receipt']
                record['collection_summary'] = {key:safe[key] for key in
                    ('logged_rows','already_logged_rows','eligible_now','cohort_anchors_in_refresh')
                    if isinstance(safe.get(key), int)}
                if safe.get('reason') in {'no_matched_paid_service_anchors','no_service_inside_frozen_prospective_time_gate'}:
                    record['collection_summary']['reason'] = safe['reason']
                allowed = {'eligible_anchor','unmatched_or_ambiguous_sale','excluded_sale','missing_sale_date',
                    'calendar_before_sale_date','unsupported_premise','not_paid_service','package_sequence_mismatch',
                    'uncertain_package','duplicate_paid_session','not_in_frozen_predictor_population'}
                record['collection_summary']['population_reason_counts'] = {key:value for key,value in
                    safe.get('population_reason_counts', {}).items() if key in allowed and type(value) is int}
        journal["stages"][name] = record
    audit_path = run_dir / 'eligibility_drift_private.json'
    if audit_path.exists():
        audit_raw = audit_path.read_bytes()
        if len(audit_raw) > ELIGIBILITY_AUDIT_MAX_BYTES:
            raise ValueError('Eligibility audit exceeds private storage bound')
        audit = json.loads(audit_raw)
        audit_sha = sha256(audit_raw).hexdigest()
        # Full customer-linked differences stay only in the restricted bucket.
        # The sanitized journal carries integrity and aggregate counts only.
        private_audit = bucket.blob(f'runs/{run_id}/eligibility_audit/{audit_sha}.json')
        try:
            private_audit.upload_from_string(audit_raw, content_type='application/json',
                if_generation_match=0, timeout=10, retry=None, checksum='crc32c')
        except PreconditionFailed:
            private_audit.reload(timeout=10, retry=None)
            if sha256(private_audit.download_as_bytes(if_generation_match=private_audit.generation,
                    timeout=10, retry=None)).hexdigest() != audit_sha:
                raise ValueError('Durable eligibility audit integrity mismatch')
        journal['eligibility_audit'] = {'sha256': audit_sha,
            **{key:audit[key] for key in ('status', 'logged_services', 'extracted_services',
                                         'changed_services') if key in audit}}
    payload = json.dumps(journal, sort_keys=True, separators=(",", ":")).encode()
    if len(payload) > JOURNAL_MAX_BYTES:
        raise ValueError("Collector journal exceeds size bound")
    digest = sha256(payload).hexdigest()
    blob = bucket.blob(f"runs/{run_id}/journal/{digest}.json")
    try:
        blob.upload_from_string(payload, content_type="application/json", if_generation_match=0,
                                timeout=10, retry=None, checksum="crc32c")
    except PreconditionFailed:
        # An exact repeated checkpoint is idempotent; verify its pinned contents.
        blob.reload(timeout=10, retry=None)
        if sha256(blob.download_as_bytes(if_generation_match=blob.generation,
                                        timeout=10, retry=None)).hexdigest() != digest:
            raise ValueError("Durable collector journal integrity mismatch")


def journaled_callbacks(bucket, run_dirs):
    """Build stage callbacks shared by collection and the final outcome refresh."""
    callbacks = {}
    for name, callback in pipeline.stage_callbacks().items():
        def wrapped(run_dir, callback=callback):
            run_dirs.add(run_dir)
            persist_run_journal(bucket, run_dir)
            return callback(run_dir)
        callbacks[name] = wrapped
    return callbacks


def journaled_pipeline_run(bucket, **kwargs):
    """Capture each stage boundary and terminal failure before the instance exits."""
    run_dirs = set()
    try:
        return pipeline.run(callbacks=journaled_callbacks(bucket, run_dirs), **kwargs)
    finally:
        for run_dir in run_dirs:
            persist_run_journal(bucket, run_dir)


def journaled_final_evaluation(bucket, *, october5=False, october10=False, recovery=False):
    """Retain final-refresh and eligibility-audit hashes even on rejection."""
    run_dirs = set()
    try:
        selection={'recovery':True} if recovery else {'october10':True} if october10 else {'october5':True} if october5 else {'cloud':True}
        return pipeline.final_evaluation(**selection,
                                        refresh_callbacks=journaled_callbacks(bucket, run_dirs))
    finally:
        for run_dir in run_dirs:
            persist_run_journal(bucket, run_dir)


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


def preflight_dependencies():
    """Reject a new revision before traffic moves if contracts are not ready."""
    bucket = storage.Client(project=PROJECT).bucket(os.environ["NOMOBUG_CP2_COLLECTOR_BUCKET"])
    hydrate_artifacts(bucket)
    calendar_sql = (ROOT / "dbt/target/compiled/nomobug/models/calendar_events.sql").read_text(
        encoding="utf-8")
    if "r.event_identity_hash" in calendar_sql:
        client = bigquery.Client(project=PROJECT, location=LOCATION)
        try:
            fields = {field.name for field in client.get_table(
                f"{PROJECT}.gold.calendar_warranty_review_overrides").schema}
        finally:
            client.close()
        if "event_identity_hash" not in fields:
            raise ValueError("Published Gold warranty review schema is incompatible with live SQL")
    registry_path=ROOT/'config/cp2_model_current.json'
    if registry_path.exists() and pipeline.read(registry_path).get('recovery_cohort_protocol_sha256'):
        from scripts.freeze_callback_prospective import cohort_contract
        bundle=ROOT/'outputs/cp2-v2/prospective_callback_v2'
        contract=cohort_contract(bundle,pipeline.read(bundle/'bundle.json'),ROOT/'config/cp2_recovery_cohort.json')
        cloud_protocol=bucket.blob('protocols/cp2_recovery_20261016.json').download_as_bytes()
        if len(cloud_protocol)>256*1024 or sha256(cloud_protocol).hexdigest()!=contract['protocol_sha256']:
            raise ValueError('Recovery declaration differs from immutable cloud protocol')


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


def preserve_october10_evidence(bucket, result_path, labels_path, *, object_name='evaluations/private/october10_complete_evidence.json'):
    """One immutable object commits matching original result and source labels."""
    result_raw, labels_raw = Path(result_path).read_bytes(), Path(labels_path).read_bytes()
    if len(labels_raw) + len(result_raw) > 10 * 1024 * 1024:
        raise ValueError('Final evidence exceeds storage bound')
    if json.loads(result_raw).get('source_labels_sha256') != sha256(labels_raw).hexdigest():
        raise ValueError('Final result does not match its labels')
    raw = json.dumps({'primary': result_raw.decode('utf-8'),
                      'labels': labels_raw.decode('utf-8')}, sort_keys=True).encode()
    blob = bucket.blob(object_name)
    try:
        blob.upload_from_string(raw, content_type='application/json', if_generation_match=0)
    except PreconditionFailed:
        if blob.download_as_bytes() != raw:
            raise ValueError('Original final evidence already differs')


def restore_october10_evidence(bucket, result_path, *, object_name='evaluations/private/october10_complete_evidence.json'):
    """Recover a committed result after interruption before its public-safe copy."""
    blob = bucket.blob(object_name)
    if not blob.exists():
        return None
    raw = blob.download_as_bytes()
    if len(raw) > 12 * 1024 * 1024:
        raise ValueError('Final evidence exceeds read bound')
    evidence = json.loads(raw)
    labels_raw = evidence['labels'].encode('utf-8')
    result_raw = evidence['primary'].encode('utf-8')
    if json.loads(result_raw).get('source_labels_sha256') != sha256(labels_raw).hexdigest():
        raise ValueError('Durable final evidence integrity differs')
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_bytes(result_raw)
    labels_path = pipeline.BASE / 'followup_labels_private.json'
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    labels_path.write_bytes(labels_raw)
    return labels_path


def recovery_final_evaluation(bucket):
    """Independent predeclared recovery cohort; never replace older results."""
    from scripts.freeze_callback_prospective import record_digest
    destination=bucket.blob('evaluations/recovery_20261016.json')
    evidence_name='evaluations/private/recovery_20261016_complete_evidence.json'
    result_path=ROOT/'outputs/cp2-v2/prospective_callback_v2/prospective_recovery_evaluation.json'
    labels_path=restore_october10_evidence(bucket,result_path,object_name=evidence_name)
    if labels_path is not None:
        registry=pipeline.read(ROOT/'config/cp2_model_current.json')
        restored=pipeline.read(result_path)
        labels=pipeline.read(labels_path)
        if (restored.get('bundle_sha256')!=registry['bundle_sha256']
                or restored.get('repaired_protocol_sha256')!=registry['recovery_cohort_protocol_sha256']
                or restored.get('cohort_start')!='2026-10-16' or restored.get('cohort_end')!='2026-10-30'
                or labels.get('record_sha256')!=record_digest(labels)):
            raise ValueError('Recovery result protocol or source labels changed')
    if destination.exists():
        if labels_path is None or destination.download_as_bytes()!=result_path.read_bytes():
            raise ValueError('Recovery evaluation differs from durable evidence')
        return {'status':'already_finalized','cohort':'recovery_20261016'}
    if labels_path is None:
        result_path.unlink(missing_ok=True)
        evaluated=journaled_final_evaluation(bucket,recovery=True)
        preserve_october10_evidence(bucket,result_path,evaluated['labels_path'],object_name=evidence_name)
    destination.upload_from_filename(str(result_path),content_type='application/json',if_generation_match=0)
    return {'status':'finalized','cohort':'recovery_20261016'}


def finish_followup_comparison(bucket, labels_path=None):
    """Keep the primary result final while allowing a failed supplement to retry.

    Source-linked labels stay in the same restricted bucket as predictions.
    No collector state or original evaluation is overwritten by this step.
    """
    from scripts import evaluate_cp2_followup_policy as policy
    destination = bucket.blob('evaluations/followup_policy_v1.json')
    if destination.exists():
        return 'already_finalized'
    labels_blob = bucket.blob('evaluations/private/october10_labels.json')
    local_labels = pipeline.BASE / 'followup_labels_private.json'
    if labels_path is not None:
        raw = Path(labels_path).read_bytes()
        if len(raw) > 10 * 1024 * 1024:
            raise ValueError('Supplementary labels exceed storage bound')
        try:
            labels_blob.upload_from_string(raw, content_type='application/json', if_generation_match=0)
        except PreconditionFailed:
            if labels_blob.download_as_bytes() != raw:
                raise ValueError('Durable supplementary labels differ')
    _download(labels_blob, local_labels)
    # A warm instance may retain an output whose durable upload failed.
    policy.RESULT.unlink(missing_ok=True)
    policy.evaluate(local_labels, pipeline.BASE / 'prospective_logs')
    destination.upload_from_filename(str(policy.RESULT), content_type='application/json', if_generation_match=0)
    return 'finalized'


def run_tick(*, full_smoke=False, final_evaluation=False, october5=False, october10=False, recovery=False):
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
    state_hydrated = False
    try:
        hydrate_artifacts(bucket)
        hydrate_state(bucket)
        state_hydrated = True
        if final_evaluation and recovery:
            result=recovery_final_evaluation(bucket)
            persist_state(bucket)
            return result
        if final_evaluation:
            destination = bucket.blob("evaluations/october10_2026.json" if october10 else
                "evaluations/october5_2026.json" if october5 else "evaluations/cloud_2026.json")
            if destination.exists():
                if october10:
                    result_path = ROOT / 'outputs/cp2-v2/prospective_callback_v2/prospective_october10_evaluation.json'
                    labels_path = restore_october10_evidence(bucket, result_path)
                    if labels_path is None:
                        raise ValueError('Original evaluation evidence is unavailable')
                    if destination.download_as_bytes() != result_path.read_bytes():
                        raise ValueError('Original evaluation differs from committed evidence')
                    return {'status': 'already_finalized',
                            'followup_comparison': finish_followup_comparison(bucket, labels_path)}
                return {"status": "already_finalized"}
            result_path = ROOT / "outputs/cp2-v2/prospective_callback_v2" / ("prospective_october10_evaluation.json" if october10 else
                "prospective_october5_evaluation.json" if october5 else "prospective_cloud_evaluation.json")
            if october10:
                labels_path = restore_october10_evidence(bucket, result_path)
                if labels_path is not None:
                    destination.upload_from_filename(str(result_path), content_type='application/json', if_generation_match=0)
                    return {'status': 'finalized_recovered',
                            'followup_comparison': finish_followup_comparison(bucket, labels_path)}
            # Only a durable cloud result is final. A warm instance may retain
            # a local result from a request that failed before its upload.
            result_path.unlink(missing_ok=True)
            evaluated = journaled_final_evaluation(bucket, october10=True) if october10 else (
                journaled_final_evaluation(bucket, october5=True) if october5 else journaled_final_evaluation(bucket))
            if october10:
                preserve_october10_evidence(bucket, result_path, evaluated['labels_path'])
            destination.upload_from_filename(str(result_path), content_type="application/json",
                                             if_generation_match=0)
            result = {"status": "finalized", "cohort_anchors": evaluated["cohort_anchors"],
                      "evaluation_rows": evaluated["evaluation_rows"]}
            if october10:
                result['followup_comparison'] = finish_followup_comparison(bucket, evaluated['labels_path'])
        elif full_smoke:
            state = journaled_pipeline_run(bucket)
            result = {"status": state["status"], "run_id": state["run_id"],
                      "full_pipeline_smoke": True,
                      "prospectively_logged": state["stages"]["prospective"]["receipt"].get("logged_rows", 0)}
            bucket.blob("state/full_smoke.json").upload_from_string(
                json.dumps(result), content_type="application/json")
        else:
            result = tick.poll(run=lambda **kwargs: journaled_pipeline_run(bucket, **kwargs))
        persist_state(bucket)
        if not full_smoke and not final_evaluation and (result.get('status') != 'idle' or result.get('newly_missed_event_windows')):
            raw = json.dumps(result, sort_keys=True).encode()
            digest = sha256(raw).hexdigest()
            bucket.blob(f"ticks/{digest}.json").upload_from_string(raw, content_type='application/json', if_generation_match=0)
        result["bigquery_indexed_predictions"] = mirror_predictions(bucket)
        return result
    except (Exception, SystemExit):
        if state_hydrated:
            persist_state(bucket)
        raise
    finally:
        watchdog.cancel()
        lock.delete(if_generation_match=generation)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path not in {"/tick", "/smoke-full", "/evaluate-cloud", "/evaluate-october5", "/evaluate-october10", "/evaluate-recovery"}:
            self.send_error(404)
            return
        try:
            selection=({'recovery':True} if self.path == '/evaluate-recovery' else
                {'october10':True} if self.path == '/evaluate-october10' else
                {'october5':True} if self.path == '/evaluate-october5' else {})
            result = run_tick(full_smoke=self.path == "/smoke-full",
                              final_evaluation=self.path in {"/evaluate-cloud", "/evaluate-october5", "/evaluate-october10", "/evaluate-recovery"}, **selection)
            status = (409 if result.get("status") == "another_cloud_tick_active" else
                      500 if result.get("status") in {
                          "refresh_failed", "refresh_without_complete_prospective_logging"} else 200)
        except Exception as error:
            # Log only the exception class; source bodies and identifiers stay private.
            result = {"status": "failed", "error_type": type(error).__name__}
            status = 500
        payload = json.dumps(result).encode()
        print(json.dumps({'collector_status': result.get('status'), 'http_status':status,
            **{key:result[key] for key in ('error_type','checked_at_utc','newly_missed_event_windows',
                'acknowledged_event_keys','october10_cohort_missed_eligible_windows',
                'october10_cohort_unresolved_candidate_windows','recovery_cohort_coverage_status',
                'recovery_cohort_missed_eligible_windows','recovery_cohort_unresolved_candidate_windows') if key in result}}, sort_keys=True), flush=True)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    preflight_dependencies()
    HTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
