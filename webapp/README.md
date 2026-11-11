# Nomobug staff website

See [current system and coverage](../planning/CP2_CURRENT_SYSTEM.md).

## Live system

[Open the hosted workspace](https://cp2-portal-fav22krh7q-as.a.run.app/).

Google sign-in protects customer records. The hosted website runs in Cloud Run; Docker Desktop and an awake laptop are not required. Do not publish credentials, private snapshots or precise customer locations.

## What belongs here

- **Dashboard:** [Evidence.dev management reports](../dashboard/README.md) embedded in the workspace.
- **Customers:** private customer search, purchases and verified programme history.
- **Payment follow-up:** Sales-based contract balances and reminder schedules. Elapsed dates do not prove payment, overdue debt or reminder delivery.
- **Area explorer:** district/radius comparisons and the live `/maps` workspace for sales density, Calendar warranty signals, proximity groups and location drill-through.
- **Model & system:** historical evaluation, experimental planning models, data freshness and runtime status.

The map keeps unlocated records in overall totals. Its model layer uses 85 located services from the separate 100-service historical test; neither layer is a new evaluation. Small groups cannot establish reliable area performance. Calendar warranty signals are not proof of biological recurrence or completed treatment.

## Development

`deploy/Dockerfile.web` builds the website (Cloud Build runs it; no local Docker needed). The retired Ollama assistant files are in `archive/retired_ollama/`. `deploy/cloudbuild.portal-web.yaml` builds the hosted website and runs a container import smoke check.

Runtime snapshots are private mounted/downloaded data, never image contents. The website runtime identity reads approved snapshots. Every BigQuery refresh query is capped at 100 MiB, and failed refreshes preserve the last good snapshot. Customer endpoints reject mixed releases.

From the project root, run `.venv/Scripts/python.exe -m pytest tests/test_portal.py tests/test_spatial_payload.py -q`. Real-data workflow acceptance uses `python -m scripts.verify_portal_workflows --folder <private-runtime-folder> --output <private-report>`.

## Evaluation and status

Use the website status page for source freshness and the [current system record](../planning/CP2_CURRENT_SYSTEM.md) for model coverage and evaluation limits. The [demonstration guide](../planning/CP2_DEMO_GUIDE.md) describes the project walkthrough.
