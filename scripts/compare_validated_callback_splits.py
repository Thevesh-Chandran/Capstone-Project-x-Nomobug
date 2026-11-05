"""Declared, source-checked historical development comparison; never deploys models."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from scripts import benchmark_warranty_models as b
from scripts import compare_callback_candidates_v2 as c
from scripts.refresh_callback_validation import source_delta


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def checked_source(protocol):
    paths = {k: b.ROOT / v["path"] for k, v in protocol["inputs"].items()}
    for name, path in paths.items():
        if digest(path) != protocol["inputs"][name]["sha256"]:
            raise ValueError(f"Changed input: {name}")
    source = b.load_dataset_input(paths["features"])
    old, new = read(paths["old_calendar"]), read(paths["calendar"])
    delta, replaced, _, _ = source_delta(old, new)
    replaced = set(replaced)
    raw = pd.DataFrame([r for r in old["records"]
                        if r["calendar_event_row"] not in replaced] + delta)
    # Row numbers belong only to this reconstructed original epoch. Later
    # snapshots are joined by Calendar/event identity, never their row numbers.
    linked = source.merge(raw[["calendar_event_row", "calendar_id", "event_id", "start_raw"]],
        left_on="anchor_event_row", right_on="calendar_event_row", how="left",
        validate="many_to_one")
    if len(linked) != len(source) or linked.calendar_event_row.isna().any():
        raise ValueError("Incomplete original source identity")
    anchor = pd.to_datetime(linked.anchor_date)
    if not pd.to_datetime(linked.start_raw.str[:10]).eq(anchor).all():
        raise ValueError("Original source anchor dates differ")
    latest = pd.DataFrame(read(paths["status_review_calendar"])["records"])
    linked = linked.merge(latest[["calendar_id", "event_id", "summary", "status", "start_raw"]],
        on=["calendar_id", "event_id"], how="left", validate="many_to_one",
        suffixes=("_original", "_review"))
    reasons = {
        "missing_review_identity": linked.start_raw_review.isna(),
        "changed_review_date": pd.to_datetime(linked.start_raw_review.str[:10],
            errors="coerce").ne(anchor) & linked.start_raw_review.notna(),
        "cancelled_anchor": (linked.summary.fillna("").str.match(
            r"^\s*CANCEL(?:L)?ED\b", case=False)
            | linked.status.fillna("").str.lower().eq("cancelled")),
    }
    excluded = pd.concat(reasons.values(), axis=1).any(axis=1)
    frame = source.loc[~excluded].copy()
    if frame.duplicated(c.KEYS).any() or frame[c.KEYS].isna().any().any():
        raise ValueError("Duplicate or incomplete service keys")
    if not frame[b.TARGET].isin([True, False, 0, 1]).all():
        raise ValueError("Unresolved target")
    dates, ends = pd.to_datetime(frame.anchor_date), pd.to_datetime(frame.outcome_end_date)
    if not (ends - dates).dt.days.eq(30).all():
        raise ValueError("Outcome horizon differs from 30 days")
    if not ends.le(pd.Timestamp(protocol["complete_outcomes_through"])).all():
        raise ValueError("Immature outcomes")
    for col in ["service_number", "package_sessions_recorded"]:
        values = pd.to_numeric(frame[col], errors="raise")
        if values.isna().any() or not (values.ge(1) & values.mod(1).eq(0)).all():
            raise ValueError("Invalid paid-service/package counts")
    if frame.service_number.gt(frame.package_sessions_recorded).any():
        raise ValueError("Overrun service in paid-service population")
    weather = pd.to_datetime(frame.latest_weather_date_used, errors="coerce")
    if not (weather.isna() | weather.lt(dates)).all():
        raise ValueError("Future weather feature")
    audit = {"input_rows": len(source), "original_identity_date_matches": len(linked),
        "excluded_rows": int(excluded.sum()),
        "exclusions_by_reason": {k: int(v.sum()) for k, v in reasons.items()},
        "eligible_rows": len(frame), "positive_rows": int(frame[b.TARGET].sum()),
        "scope": "snapshot identity, dates, maturity, binary target, unique service keys, paid-service counts, prior weather",
        "limits": ["No claim of manual validation of every appointment or biological recurrence.",
            "Historical labels and feature revisions are retained; indirect history contamination is not fully reconstructed.",
            "Previously reported nine cancellation anchors were not reproduced by this stable-identity review; no guessed exclusions."]}
    return c.prepare_input(frame), audit


def review_metrics(y, probability, fraction):
    y = np.asarray(y, dtype=bool)
    count = int(np.ceil(len(y) * fraction))
    # Input frame has canonical key ordering; stable sort deterministically breaks ties.
    chosen = np.argsort(-np.asarray(probability), kind="stable")[:count]
    tp = int(y[chosen].sum())
    return {"reviewed": count, "found": tp, "false_alerts": count - tp,
            "recall": tp / int(y.sum()), "precision": tp / count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    protocol = read(args.protocol)
    if digest(__file__) != protocol["code_sha256"]:
        raise ValueError("Comparison code changed after declaration")
    if args.output_dir.exists():
        raise ValueError("Output directory already exists; preserve previous evidence")
    bundle = b.ROOT / protocol["frozen_bundle_path"]
    before = {p.name: digest(p) for p in bundle.iterdir() if p.is_file()}
    args.output_dir.mkdir(parents=True)
    write(args.output_dir / "protocol.json", protocol)
    frame, audit = checked_source(protocol)
    development = frame[frame.anchor_date.lt(protocol["development_end_exclusive"])].copy()
    write(args.output_dir / "source_audit.json", audit | {
        "development_rows": len(development), "development_positive_rows": int(development[b.TARGET].sum()),
        "reserved_later_rows": len(frame) - len(development)})
    contracts = c.feature_sets()
    numeric = contracts["targeted"]
    features = numeric + list(b.CATEGORICAL)
    if b.TARGET in features:
        raise ValueError("Target leakage")
    metrics = []
    for name, start, end in protocol["folds"]:
        train, valid, split_audit = b.purged_split(development, start, end)
        if train[b.TARGET].nunique() != 2 or valid[b.TARGET].nunique() != 2:
            raise ValueError("Both classes required in every fold")
        for model in protocol["models"]:
            if model == "et10_leaf5":
                pipe = c.make_pipeline(model, numeric)
            else:
                pipe = b.make_model(model, numeric)
            if "n_jobs" in pipe.named_steps["classifier"].get_params():
                pipe.named_steps["classifier"].set_params(n_jobs=2)
            with threadpool_limits(limits=2):
                pipe.fit(train[features], train[b.TARGET])
                scores = pipe.predict_proba(valid[features])[:, 1]
            if not np.isfinite(scores).all():
                raise ValueError("Non-finite predictions")
            result = {"fold": name, "role": "selection" if name in protocol["selection_folds"] else "diagnostic",
                "model": model, "training_rows": len(train),
                "training_positives": int(train[b.TARGET].sum()), **split_audit,
                **b.score(valid[b.TARGET], scores),
                "review": review_metrics(valid[b.TARGET], scores, protocol["review_fraction"])}
            metrics.append(result)
            valid[c.KEYS + [b.TARGET]].assign(probability=scores).to_csv(
                args.output_dir / f"{name}_{model}_predictions_private.csv", index=False)
            print(f"{name} {model}: train={len(train)} validation={len(valid)} positives={int(valid[b.TARGET].sum())} AP={result['average_precision']:.4f} review_recall={result['review']['recall']:.3f}", flush=True)
    summary = []
    for role in ("selection", "diagnostic"):
      for model in protocol["models"]:
        rows = [r for r in metrics if r["model"] == model and r["role"] == role]
        summary.append({"model": model, "role": role, "folds": len(rows),
            "validation_services": sum(r["rows"] for r in rows),
            "positive_service_windows": sum(r["positives"] for r in rows),
            "mean_ap": float(np.mean([r["average_precision"] for r in rows])),
            "mean_auc": float(np.mean([r["roc_auc"] for r in rows])),
            "mean_review_recall": float(np.mean([r["review"]["recall"] for r in rows])),
            "reviewed_services": sum(r["review"]["reviewed"] for r in rows),
            "positive_windows_found": sum(r["review"]["found"] for r in rows)})
    baseline = next(r for r in summary if r["model"] == "et10_leaf5" and r["role"] == "selection")
    qualified = [r for r in summary if r["role"] == "selection" and r["mean_ap"] > baseline["mean_ap"]
                 and r["mean_review_recall"] >= baseline["mean_review_recall"]]
    after = {p.name: digest(p) for p in bundle.iterdir() if p.is_file()}
    if before != after:
        raise ValueError("Frozen bundle changed")
    result = {"status": "historical_development_only_previously_inspected_periods",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(args.protocol), "source_audit": audit,
        "features": features, "metrics": metrics, "summary": summary,
        "qualified_candidates": [r["model"] for r in qualified],
        "decision": "Review candidate on a separately declared future cohort" if qualified else "No replacement qualified in this bounded comparison",
        "frozen_bundle_unchanged": True,
        "limits": protocol["limits"]}
    write(args.output_dir / "results.json", result)
    pd.DataFrame(summary).to_csv(args.output_dir / "comparison.csv", index=False)
    print(json.dumps({"summary": summary, "qualified_candidates": result["qualified_candidates"],
                      "frozen_bundle_unchanged": True}, indent=2), flush=True)


if __name__ == "__main__":
    main()
