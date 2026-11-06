# Nomobug staff website

Current handover: [CP2 final handover](../planning/CP2_FINAL_HANDOVER_20261016.md).

## Live system

https://cp2-portal-964813222593.asia-southeast1.run.app

Google sign-in protects customer records. The hosted website runs in Cloud Run; Docker Desktop and an awake laptop are not required. Do not publish credentials, private snapshots or precise customer locations.

## What belongs here

- **Dashboard:** embedded Looker Studio management reporting.
- **Customers:** private customer search, purchases and verified programme history.
- **Payment follow-up:** Sales-based contract balances and reminder schedules. Elapsed dates do not prove payment, overdue debt or reminder delivery.
- **Area explorer:** district/radius comparisons and the live `/maps` workspace for sales density, Calendar warranty signals, proximity groups and location drill-through.
- **Model & system:** historical evaluation, experimental planning models, data freshness and runtime status.

The map keeps unlocated records in overall totals. Its model layer uses 85 located services from the separate 100-service historical test; neither layer is a new evaluation. Small groups cannot establish reliable area performance. Calendar warranty signals are not proof of biological recurrence or completed treatment.

## Development

`deploy/Dockerfile.web` builds the website (Cloud Build runs it; no local Docker needed). The retired Ollama assistant files are in `archive/retired_ollama/`. `cloudbuild.portal-web.yaml` builds the hosted website and runs a container import smoke check.

Runtime snapshots are private mounted/downloaded data, never image contents. The website runtime identity reads approved snapshots. Every BigQuery refresh query is capped at 100 MiB, and failed refreshes preserve the last good snapshot. Customer endpoints reject mixed releases.

From the project root, run `.venv/Scripts/python.exe -m pytest tests/test_portal.py tests/test_spatial_payload.py -q`. Real-data workflow acceptance uses `python -m scripts.verify_portal_workflows --folder <private-runtime-folder> --output <private-report>`.

## Remaining evidence

The current handover records the deployed revision and dated test results. Broader AI checks measure answer quality and latency; a valid citation is not proof of correctness. The Client M contract needs the owner's confirmation. Future model evaluation remains governed by the predeclared cohort and complete outcomes on 30 November; missing predictions are never backfilled.

Older deployment narratives remain in dated files under `planning/`; they are not current operating instructions. The report and demonstration guides are [here](../planning/CP2_FINAL_REPORT_DRAFT.md) and [here](../planning/CP2_DEMO_GUIDE.md).
