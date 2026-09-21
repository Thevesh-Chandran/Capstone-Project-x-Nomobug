"""Build and test the bounded analytics-ML experiment datasets."""

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
    with bigquery.Client(project=PROJECT, location=LOCATION) as client:
        prospects_view = client.get_table(f"{PROJECT}.silver.prospects_2026")
        ids = set(re.findall(
            r"prospects_2026_([0-9a-f]{64})", prospects_view.view_query or ""))
        if len(ids) != 1:
            raise SystemExit("Cannot resolve pinned Prospects snapshot")
        digest = ids.pop()
        metadata = json.loads(client.get_table(
            f"{PROJECT}.bronze.prospects_2026_{digest}").description)
    variables = json.dumps({
        "prospects_snapshot_id": digest,
        "prospects_snapshot_extracted_at": metadata["extracted_at"],
    })
    dbt = Path(sys.executable).with_name(
        "dbt.exe" if sys.platform == "win32" else "dbt")
    test_only = "--invariants-only" in sys.argv
    contract_only = "--contract-tests" in sys.argv
    release_only = "--release-models" in sys.argv
    models_only = "--models-only" in sys.argv
    spatial_only = "--spatial" in sys.argv
    selection = ("dashboard_ml_evaluation dashboard_spatial_cluster_summary"
                 if release_only else
                 ("looker_release_invariants dashboard_spatial_cluster_summary dashboard_ml_evaluation"
                 if contract_only else ("+tag:spatial+" if spatial_only else
                 ("warranty_risk_3session_invariants" if test_only else "+tag:analytics_ml"))
                 ))
    command = [
        str(dbt), "test" if (test_only or contract_only) else
        ("run" if (models_only or release_only) else "build"),
        "--project-dir", str(ROOT / "dbt"),
        "--profiles-dir", str(ROOT / "dbt"), "--vars", variables,
        "--select", selection,
        "--no-send-anonymous-usage-stats",
    ]
    if subprocess.run(command, cwd=ROOT).returncode:
        raise SystemExit("ANALYTICS ML DATASET BUILD FAILED")
    print("RELEASE MODELS REFRESH PASS" if release_only else
          ("RELEASE CONTRACT TESTS PASS" if contract_only else
          ("SPATIAL MODEL REFRESH PASS" if spatial_only else
          ("ANALYTICS ML INVARIANTS PASS" if test_only else
          ("ANALYTICS ML MODEL REFRESH PASS" if models_only
           else "ANALYTICS ML DATASET BUILD PASS")))))


if __name__ == "__main__":
    main()
