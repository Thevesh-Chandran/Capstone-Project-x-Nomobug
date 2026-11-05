"""Summarize real observed usability responses; blank tasks remain untested."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
from statistics import median

TASKS = {"reminders", "balances", "bookings", "model_tradeoff", "weather_evidence", "freshness"}


def summarize(rows):
    completed = []
    seen = set()
    for row in rows:
        if row["task_id"] not in TASKS:
            raise ValueError("Unknown task")
        if not any(row.get(k, "").strip() for k in ("participant_code", "started_at", "finished_at", "answer", "correct")):
            continue
        key = (row["participant_code"], row["task_id"])
        if not key[0] or key in seen or not row.get("answer", "").strip():
            raise ValueError("Participant, unique attempt and actual answer required")
        seen.add(key)
        if row["correct"].lower() not in ("yes", "no") or row["help_needed"].lower() not in ("yes", "no"):
            raise ValueError("Observed correct/help_needed must be yes or no")
        start, end = (datetime.fromisoformat(row[k]) for k in ("started_at", "finished_at"))
        if start.tzinfo is None or end.tzinfo is None or end < start:
            raise ValueError("Ordered timezone-aware observation times required")
        completed.append({"task_id": row["task_id"], "seconds": (end-start).total_seconds(),
                          "correct": row["correct"].lower() == "yes", "help": row["help_needed"].lower() == "yes"})
    return {"status": "measured" if completed else "not_tested",
        "completed_attempts": len(completed), "tasks_tested": sorted({r["task_id"] for r in completed}),
        "tasks_not_tested": sorted(TASKS - {r["task_id"] for r in completed}),
        "correct_answers": sum(r["correct"] for r in completed),
        "success_share": sum(r["correct"] for r in completed)/len(completed) if completed else None,
        "median_seconds": median(r["seconds"] for r in completed) if completed else None,
        "attempts_needing_help": sum(r["help"] for r in completed),
        "interpretation": "Observed tasks only; no baseline time saving or financial benefit inferred."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("responses", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.responses.open(newline="", encoding="utf-8") as handle:
        result = summarize(list(csv.DictReader(handle)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result))
