"""Build conservative Gold facts, monthly summaries and quality checks."""

import json
import re
import subprocess
import sys
from pathlib import Path

from google.cloud import bigquery


ROOT = Path(__file__).resolve().parents[1]
PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"


def main() -> None:
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        for dataset in ("silver", "gold"):
            if client.get_dataset(f"{PROJECT}.{dataset}").location.lower() != LOCATION:
                raise SystemExit(f"{dataset} dataset region mismatch")
        for view in ("sales", "payments", "refund", "warranty_claim",
                     "calendar_events", "calendar_event_matches"):
            if client.get_table(f"{PROJECT}.silver.{view}").table_type != "VIEW":
                raise SystemExit(f"Expected Silver view missing: {view}")
        prospects_view = client.get_table(f"{PROJECT}.silver.prospects_2026")
        ids = set(re.findall(r"prospects_2026_([0-9a-f]{64})", prospects_view.view_query or ""))
        if len(ids) != 1:
            raise SystemExit("Cannot resolve Prospects snapshot for dbt parsing")
        digest = ids.pop()
        metadata = json.loads(
            client.get_table(f"{PROJECT}.bronze.prospects_2026_{digest}").description
        )
        variables = json.dumps({
            "prospects_snapshot_id": digest,
            "prospects_snapshot_extracted_at": metadata["extracted_at"],
        })
    finally:
        client.close()

    dbt = Path(sys.executable).with_name("dbt.exe" if sys.platform == "win32" else "dbt")
    looker_only = "--looker-only" in sys.argv
    command = [
        str(dbt), "build", "--project-dir", str(ROOT / "dbt"),
        "--profiles-dir", str(ROOT / "dbt"), "--vars", variables,
        "--select", "tag:looker" if looker_only else "tag:gold",
        "--no-send-anonymous-usage-stats",
    ]
    if subprocess.run(command, cwd=ROOT).returncode:
        raise SystemExit("GOLD BUILD FAILED; do not publish reporting metrics")
    if looker_only:
        print("LOOKER RELEASE VIEW BUILD PASS")
    else:
        print("GOLD BUILD PASS: facts, recorded monthly activity and quality checks reconciled")


if __name__ == "__main__":
    main()
