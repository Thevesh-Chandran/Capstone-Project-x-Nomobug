"""One-time supplementary daily-budget comparison after the main future test.

No scoring, fitting, collector mutation or retrospective prediction backfill.
Only immutable source-bound receipts accepted by the original timing contract
are used. The main complete-cohort evaluation must already have succeeded.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.build_cp2_decision_support import HISTORY, KEYS, ROOT, TARGET, counts, select_exact, sha
from scripts import freeze_callback_prospective as frozen

LOCAL = ZoneInfo("Asia/Kuala_Lumpur")
PROTOCOL = ROOT / "config/cp2_followup_policy_v1.json"
BUNDLE = ROOT / "outputs/cp2-v2/prospective_callback_v2"
COLLECTION = ROOT / "config/cp2_october10_cohort.json"
RESULT = BUNDLE / "followup_policy_v1_evaluation.json"
MODEL_SCORE = "challenger_all_history"
RULES = {"review_fraction": .2, "batch": "previous_local_day_all_eligible_services",
         "decision_time": "08:00 Asia/Kuala_Lumpur next day",
         "history_score": HISTORY, "missing_history": "rank_last_report_missing_count",
         "tie_break": "sha256_json_canonical_population_sale_anchor_key",
         "model_score": MODEL_SCORE}


def declare() -> dict:
    now = datetime.now(timezone.utc)
    start = now.astimezone(LOCAL).date() + timedelta(days=1)
    end = pd.Timestamp(json.loads(COLLECTION.read_text())["cohort_end"]).date()
    if start > end:
        raise ValueError("No future collection days remain for declaration")
    protocol = {"version": 1, "declared_at_utc": now.isoformat(), "cohort_start": str(start),
        "cohort_end": str(end), "earliest_evaluation": "2026-11-30", "rules": RULES,
        "collection_sha256": sha(COLLECTION), "bundle_sha256": sha(BUNDLE / "bundle.json"),
        "code_sha256": sha(Path(__file__)),
        "ranking_code_sha256": sha(ROOT / "scripts/build_cp2_decision_support.py"),
        "interpretation": "Predeclared supplementary policy simulation using prospective receipts; no staff actions or savings measured",
        "acceptance": "Original full-cohort evaluation must pass; no missing, late or altered receipts; complete outcomes; one evaluation only"}
    protocol["record_sha256"] = frozen.record_digest(protocol)
    PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
    with PROTOCOL.open("x", encoding="utf-8") as handle:
        json.dump(protocol, handle, indent=2, allow_nan=False)
    return protocol


def check_protocol(protocol: dict, now: datetime) -> None:
    if protocol.get("record_sha256") != frozen.record_digest(protocol) or protocol.get("rules") != RULES:
        raise ValueError("Supplementary protocol changed")
    if (protocol["code_sha256"] != sha(Path(__file__)) or
        protocol["ranking_code_sha256"] != sha(ROOT / "scripts/build_cp2_decision_support.py") or
        protocol["collection_sha256"] != sha(COLLECTION) or
        protocol["bundle_sha256"] != sha(BUNDLE / "bundle.json")):
        raise ValueError("Protocol code, collection or model hash changed")
    declared = datetime.fromisoformat(protocol["declared_at_utc"])
    if pd.Timestamp(protocol["cohort_start"]).date() <= declared.astimezone(LOCAL).date():
        raise ValueError("Supplementary cohort must begin after declaration day")
    if now.astimezone(LOCAL).date() < pd.Timestamp(protocol["earliest_evaluation"]).date():
        raise ValueError("Complete future outcomes have not matured")


def compare_daily(frame: pd.DataFrame) -> list[dict]:
    if frame.empty or frame.duplicated(KEYS).any() or frame[KEYS].isna().any().any():
        raise ValueError("Complete unique service population required")
    if not pd.to_numeric(frame[MODEL_SCORE], errors="raise").between(0, 1).all():
        raise ValueError("Invalid logged probability")
    result = []
    for rule, column in [("Current model", MODEL_SCORE), ("Previous property callbacks", HISTORY)]:
        selected = pd.Series(False, index=frame.index)
        for _, batch in frame.groupby("anchor_date", sort=True):
            selected.loc[batch.index] = select_exact(batch, column)
        result.append({"review_rule": rule, **counts(frame[TARGET], selected),
            "first_service_positive_windows": int((frame[TARGET].astype(bool) & frame.service_number.eq(1)).sum()),
            "first_service_callbacks_found": int((frame[TARGET].astype(bool) & frame.service_number.eq(1) & selected).sum()),
            "history_missing_services": int(frame[HISTORY].isna().sum())})
    expected_found = 0.
    for _, batch in frame.groupby("anchor_date", sort=True):
        expected_found += int(select_exact(batch, MODEL_SCORE).sum()) * float(batch[TARGET].mean())
    result.append({"review_rule": "Random selection (expected)", "services": len(frame),
        "positive_windows": int(frame[TARGET].sum()), "reviews": result[0]["reviews"],
        "callbacks_found": expected_found, "callbacks_missed": int(frame[TARGET].sum())-expected_found,
        "reviews_without_callback": result[0]["reviews"]-expected_found,
        "callback_capture": expected_found/frame[TARGET].sum() if frame[TARGET].sum() else None,
        "review_precision": expected_found/result[0]["reviews"]})
    return result


def evaluate(labels_path: Path, log_dir: Path) -> dict:
    if RESULT.exists():
        raise ValueError("Supplementary evaluation already recorded")
    now = datetime.now(timezone.utc)
    protocol = json.loads(PROTOCOL.read_text())
    check_protocol(protocol, now)
    frozen.configure_contracts(False)
    manifest, _ = frozen.load_bundle(BUNDLE)
    contract = frozen.cohort_contract(BUNDLE, manifest, COLLECTION)
    primary = json.loads(contract["result_path"].read_text())  # No partial-cohort fallback.
    labels = json.loads(labels_path.read_text())
    if (primary.get("bundle_sha256") != protocol["bundle_sha256"] or
        primary.get("repaired_protocol_sha256") != sha(COLLECTION) or
        primary.get("source_labels_sha256") != sha(labels_path) or
        labels.get("record_sha256") != frozen.record_digest(labels) or
        labels.get("cohort_complete") is not True or labels.get("date_authority") != "Calendar"):
        raise ValueError("Main evaluation and complete source-bound outcomes required")
    if pd.Timestamp(labels["calendar_coverage_through"]) < pd.Timestamp(contract["cohort_end"]) + pd.Timedelta(days=30):
        raise ValueError("Incomplete Calendar outcome coverage")
    records = []
    for path in sorted(log_dir.glob("*.json")):
        entry = json.loads(path.read_text())
        receipt = entry.get("source_receipt", {})
        if receipt.get("collection_protocol_sha256") != sha(COLLECTION):
            continue
        if (entry.get("bundle_sha256") != protocol["bundle_sha256"] or
            entry.get("record_sha256") != frozen.record_digest(entry) or
            entry.get("schema_version") != 2 or TARGET in entry["row"] or
            receipt.get("source") != frozen.SOURCE_NAME or
            receipt.get("collection_timing_policy") != contract["collection_protocol"]["timing_policy"]):
            raise ValueError("Altered or incompatible prediction receipt")
        row = entry["row"]
        extracted = frozen.timestamp(receipt["extracted_at_utc"])
        predicted = frozen.timestamp(row["prediction_at"])
        if (not extracted <= frozen.timestamp(row["feature_snapshot_at"]) <= predicted or
            frozen.timestamp(receipt["prediction_generated_at_utc"]) != predicted):
            raise ValueError("Prediction source timing differs")
        one = pd.DataFrame([row])
        one.anchor_date = pd.to_datetime(one.anchor_date)
        frozen.validate_prediction_times(one, manifest, entry["logged_at_utc"],
            collection_protocol=contract["collection_protocol"])
        if one.anchor_date.between(pd.Timestamp(contract["cohort_start"]), pd.Timestamp(contract["cohort_end"])).all():
            records.append(row)
    expected = labels.get("expected_cohort_anchors")
    if type(expected) is not int or len(records) != expected or len(labels["records"]) != expected or primary["rows"] != expected:
        raise ValueError("Missing predictions or incomplete original cohort")
    frame, truth = pd.DataFrame(records), pd.DataFrame(labels["records"])
    if not all(type(x) is bool for x in truth[TARGET]):
        raise ValueError("Unknown outcome is not a negative")
    for f in (frame, truth):
        f["anchor_date"] = pd.to_datetime(f.anchor_date).dt.strftime("%Y-%m-%d")
        f["sales_record_id"] = f.sales_record_id.astype(str)
    frame = frame.merge(truth[KEYS + [TARGET]], on=KEYS, how="outer", validate="one_to_one", indicator=True)
    if not frame._merge.eq("both").all():
        raise ValueError("Eligible services and prediction keys differ")
    selected = frame.loc[frame.anchor_date.between(protocol["cohort_start"], protocol["cohort_end"])].copy()
    result = {"evaluated_at_utc": now.isoformat(), "protocol_sha256": sha(PROTOCOL),
        "primary_result_sha256": sha(contract["result_path"]), "source_labels_sha256": sha(labels_path),
        "cohort_start": protocol["cohort_start"], "cohort_end": protocol["cohort_end"],
        "original_cohort_services": len(frame), "supplementary_services": len(selected),
        "results": compare_daily(selected), "interpretation": protocol["interpretation"],
        "limits": ["No callback prevention, financial benefit or actual staff decisions measured.",
                   "Daily rounding may review more than 20% overall; all rules receive exactly the same daily budget.",
                   "One recorded callback may fall in multiple service windows; first-service results are reported separately."]}
    with RESULT.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["declare", "evaluate"])
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--logs", type=Path)
    args = parser.parse_args()
    if args.action == "declare":
        result = declare()
    else:
        if args.labels is None or args.logs is None:
            parser.error("evaluate requires --labels and --logs")
        result = evaluate(args.labels, args.logs)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
