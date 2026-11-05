"""Read-only historical source-epoch validation and prediction eligibility audit.

No scoring, fitting, label changes, cloud writes, or final outcome evaluation.
Customer-linked differences stay in ignored outputs; stdout contains aggregates.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

try:
    from scripts import benchmark_warranty_models as b
    from scripts import freeze_callback_prospective as p
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    import freeze_callback_prospective as p

PIN = b.ROOT / "config/cp2_historical_callback_validation.json"
MAX_BYTES = 104857600
KEYS = ("population", "sales_record_id", "anchor_date")


def private_output(path):
    path = Path(path).resolve()
    if not path.is_relative_to((b.ROOT / "outputs").resolve()):
        raise ValueError("Private audit output must stay under ignored outputs")
    if path.exists():
        raise ValueError("Audit output already exists; preserve earlier evidence")
    return path


def validate_metadata(table, expected_modified, expected_rows):
    if table.modified.isoformat() != expected_modified or table.num_rows != expected_rows:
        raise ValueError("Historical source epoch changed; do not join old row numbers to new facts")


def historical_sql(pin):
    """Only named, pinned historical tables; current Silver is never referenced."""
    project = pin["project"]
    if not re.fullmatch(r"[a-z][a-z0-9-]+", project):
        raise ValueError("Invalid pinned project")
    for name in ("anchor_table", "fact_table", "calendar_table"):
        if not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", pin[name]):
            raise ValueError("Invalid pinned table")
    a, f, r = (f"`{project}.{pin[name]}`" for name in ("anchor_table", "fact_table", "calendar_table"))
    return f"""WITH linked AS (
 SELECT a.*, f.event_id, f.calendar_name, f.event_category,
        f.event_date_local AS fact_event_date, f.sales_record_id AS fact_sales_record_id,
        f.warranty_claim_candidate AS anchor_is_callback,
        r.event_id AS raw_event_id, r.summary AS raw_summary,
        DATE(SAFE_CAST(r.start_raw AS TIMESTAMP), 'Asia/Kuala_Lumpur') AS raw_date
 FROM {a} a
 LEFT JOIN {f} f ON f.calendar_event_row=a.anchor_event_row
 LEFT JOIN {r} r ON r.calendar_event_row=a.anchor_event_row
  AND r.event_id=f.event_id AND r.calendar_name=f.calendar_name
), outcomes AS (
 SELECT a.anchor_event_row,
        COUNTIF(w.warranty_claim_candidate) AS historical_callback_count
 FROM {a} a LEFT JOIN {f} w
 ON w.sales_record_id=a.sales_record_id
 AND w.event_date_local>a.anchor_date AND w.event_date_local<=a.outcome_end_date
 GROUP BY a.anchor_event_row
)
SELECT COUNT(*) AS anchor_rows,
 COUNTIF(event_id IS NULL OR raw_event_id IS NULL) AS missing_source_identity,
 COUNTIF(fact_event_date IS DISTINCT FROM anchor_date OR raw_date IS DISTINCT FROM anchor_date
   OR fact_sales_record_id IS DISTINCT FROM sales_record_id) AS source_identity_mismatches,
 COUNTIF(event_category IS DISTINCT FROM 'service' OR anchor_is_callback IS DISTINCT FROM FALSE) AS invalid_anchor_categories,
 COUNTIF(outcome_end_date IS DISTINCT FROM DATE_ADD(anchor_date, INTERVAL 30 DAY)
   OR outcome_end_date>observed_through OR observed_through IS NULL) AS invalid_horizons,
 COUNTIF(warranty_claim_count_30d IS DISTINCT FROM historical_callback_count
   OR warranty_signal_within_30d IS DISTINCT FROM (historical_callback_count>0)) AS outcome_mismatches,
 COUNT(*)-COUNT(DISTINCT anchor_event_row) AS duplicate_anchor_rows,
 COUNT(*)-COUNT(DISTINCT TO_JSON_STRING(STRUCT(population,sales_record_id,anchor_date))) AS duplicate_service_keys,
 COUNTIF(REGEXP_CONTAINS(UPPER(COALESCE(raw_summary,'')), r'^\\s*CANCEL(?:L)?ED\\b')) AS postponed_title_anchors_retained_in_historical_rules
FROM linked JOIN outcomes USING(anchor_event_row)"""


def audit_historical(output):
    from google.cloud import bigquery
    output = private_output(output)
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    client = bigquery.Client(project=pin["project"], location=pin["location"])
    try:
        for prefix in ("anchor", "fact"):
            table = client.get_table(f"{pin['project']}.{pin[prefix+'_table']}")
            validate_metadata(table, pin[prefix+"_modified_utc"], pin[prefix+"_rows"])
        query = historical_sql(pin)
        job = client.query(query, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES))
        try:
            rows = list(job.result(timeout=300))
        except Exception:
            job.cancel()
            raise
        # A reporting publication may replace a stable relation while a query
        # runs. Refuse an audit if either historical table changed mid-check.
        for prefix in ("anchor", "fact"):
            table = client.get_table(f"{pin['project']}.{pin[prefix+'_table']}")
            validate_metadata(table, pin[prefix+"_modified_utc"], pin[prefix+"_rows"])
        counts = dict(rows[0])
        failures = {name: value for name, value in counts.items()
                    if name not in ("anchor_rows", "postponed_title_anchors_retained_in_historical_rules") and value}
        if counts["anchor_rows"] != pin["anchor_rows"]:
            failures["anchor_row_count"] = counts["anchor_rows"]
        result = {"status": "fail" if failures else "pass_with_historical_source_limitations",
                  "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                  "pin_sha256": p.digest(PIN), "counts": counts, "failures": failures,
                  "job_id": job.job_id, "bytes_processed": job.total_bytes_processed,
                  "bytes_billed": job.total_bytes_billed, "source_pin": pin,
                  "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
                  "query": query, "model_changed": False,
                  "interpretation": "Cancelled title means the old appointment was postponed; historical limitations are preserved, not a cancelled sale or failed treatment."}
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
        return {key: value for key, value in result.items() if key not in ("query", "source_pin")}
    finally:
        client.close()


def service_key(row):
    values = tuple(str(row.get(name, "")).strip() for name in KEYS)
    if not all(values):
        raise ValueError("Missing service identity in audit input")
    return values[:2] + (values[2][:10],)


def calendar_window_key(event):
    fields = ("calendar_id", "event_id", "start_raw", "end_raw")
    if not all(event.get(field) for field in fields):
        raise ValueError("Complete Calendar event-window identity required")
    return hashlib.sha256("|".join(str(event[field]) for field in fields).encode()).hexdigest()


def bound_window_key(entry, key):
    bindings = entry.get("source_receipt", {}).get("calendar_event_keys_by_prediction_key", {})
    matching = [value for raw_key, value in bindings.items()
                if len(raw_key.split("|")) == 3
                and tuple(raw_key.split("|")[:2] + [raw_key.split("|")[2][:10]]) == key]
    if len(matching) > 1:
        raise ValueError("Ambiguous immutable Calendar window binding")
    return matching[0] if matching else None


def eligibility_drift(entries, candidate_rows, *, bundle_sha256, cohort_start, cohort_end, current_events=None,
                      appointment_reviews=None):
    """Compare immutable receipts with a later extraction; never invent outcomes.

    Candidate rows can be current predictors or mature labels. This is a coverage
    audit only: agreement is not complete-source or outcome-maturity evidence.
    """
    logged = {}
    for entry in entries:
        if entry.get("bundle_sha256") != bundle_sha256:
            raise ValueError("Prediction bundle differs from declared audit bundle")
        if entry.get("record_sha256") != p.record_digest(entry):
            raise ValueError("Immutable prediction receipt changed")
        key = service_key(entry["row"])
        if not cohort_start <= key[2] <= cohort_end:
            continue
        if key in logged:
            raise ValueError("Duplicate prospective service receipts")
        logged[key] = entry
    current = {}
    for row in candidate_rows:
        key = service_key(row)
        if not cohort_start <= key[2] <= cohort_end:
            continue
        if key in current:
            raise ValueError("Duplicate extracted service identity")
        current[key] = row
    events = {}
    windows = {}
    for event in current_events or []:
        identity = (event.get("calendar_id"), event.get("event_id"))
        if not all(identity) or identity in events:
            raise ValueError("Missing or duplicate Calendar event identity")
        events[identity] = event
        window = calendar_window_key(event)
        if window in windows:
            raise ValueError("Duplicate Calendar event-window hash")
        windows[window] = event
    changes = []
    for key in sorted(logged):
        entry = logged[key]
        identity = (entry.get("source_receipt", {}).get("calendar_id"),
                    entry.get("source_receipt", {}).get("event_id"))
        # Existing receipts may carry multiple event identities in calendar_verification.
        row = entry["row"]
        identity = (row.get("calendar_id", identity[0]), row.get("event_id", identity[1]))
        event = events.get(identity) or windows.get(bound_window_key(entry, key))
        reason = "eligibility_or_identity_changed_needs_source_review"
        source_changed = False
        if event:
            try:
                from scripts.calendar_appointment_policy import is_confirmed_placeholder
            except ModuleNotFoundError:
                from calendar_appointment_policy import is_confirmed_placeholder
            title = str(event.get("summary", "")).upper()
            category = str(event.get("event_category", "")).lower()
            if is_confirmed_placeholder(event, appointment_reviews):
                reason = "owner_confirmed_temporary_slot_exact_reviewed_window"
                source_changed = True
            elif category in ("placeholder", "hold", "awaiting_client_date") or re.match(r"^\s*HOLD\b", title):
                reason = "later_marked_hold_placeholder_not_confirmed_service"
                source_changed = True
            elif str(event.get("status", "")).lower() == "cancelled" or re.match(r"^\s*CANCEL(?:L)?ED\b", title):
                reason = "old_appointment_postponed_active_replacement_requires_own_identity"
                source_changed = True
        if key not in current or source_changed:
            kind = "logged_service_missing_from_extraction" if key not in current else "logged_service_source_now_ineligible"
            changes.append({"kind": kind, "service_key": list(key), "reason": reason})
    for key in sorted(set(current) - set(logged)):
        changes.append({"kind": "extracted_service_without_receipt", "service_key": list(key),
                        "reason": "missing_or_late_prediction_cannot_be_backfilled"})
    return {"logged_services": len(logged), "extracted_services": len(current),
            "retained_services": len(set(logged) & set(current)),
            "changed_services": len(changes), "change_counts": dict(Counter(x["kind"] for x in changes)),
            "changes_private": changes, "coverage_keys_agree": not changes,
            "accuracy_claim_ready": False,
            "interpretation": "Key agreement does not prove mature outcomes, timely logging, or complete Calendar coverage; the unchanged final evaluator remains mandatory."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    historical = sub.add_parser("historical")
    historical.add_argument("--output-json", type=Path, required=True)
    drift = sub.add_parser("eligibility-drift")
    drift.add_argument("--prediction-directory", type=Path, required=True)
    drift.add_argument("--candidate-input-json", type=Path, required=True)
    drift.add_argument("--current-calendar-json", type=Path)
    drift.add_argument("--protocol", type=Path, default=b.ROOT/"config/cp2_cloud_cohort.json")
    drift.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "historical":
        result = audit_historical(args.output_json)
    else:
        output = private_output(args.output_json)
        protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
        registry = json.loads((b.ROOT/"config/cp2_model_current.json").read_text(encoding="utf-8"))
        bundle = b.ROOT/registry["bundle_relative_path"]
        manifest, _ = p.load_bundle(bundle)
        p.cohort_contract(bundle, manifest, args.protocol)
        entries = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.prediction_directory.glob("*.json"))]
        rows = b.load_dataset_input(args.candidate_input_json).to_dict("records")
        events = None
        if args.current_calendar_json:
            inventory = json.loads(args.current_calendar_json.read_text(encoding="utf-8"))
            events = inventory.get("records", inventory.get("rows"))
            if not isinstance(events, list): raise ValueError("Calendar snapshot records required")
        result = eligibility_drift(entries, rows, bundle_sha256=protocol["bundle_sha256"],
                                   cohort_start=protocol["cohort_start"], cohort_end=protocol["cohort_end"], current_events=events)
        result.update(checked_at_utc=datetime.now(timezone.utc).isoformat(),
                      candidate_input_sha256=p.digest(args.candidate_input_json), protocol_sha256=p.digest(args.protocol))
        if events is not None:
            try:
                from scripts.calendar_appointment_policy import policy_sha256
            except ModuleNotFoundError:
                from calendar_appointment_policy import policy_sha256
            result["appointment_review_policy_sha256"] = policy_sha256()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle: json.dump(result, handle, indent=2, allow_nan=False)
    print(json.dumps({key: value for key, value in result.items() if key!="changes_private"}, indent=2, allow_nan=False))
    if result.get("status") == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
