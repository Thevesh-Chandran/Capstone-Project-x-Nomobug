# CP2 cloud resource map and cleanup record

Project: `profound-keel-500007-s4`. Region: `asia-southeast1`.

| Resource | Purpose | Keep rule |
|---|---|---|
| Cloud Run service `cp2-prospective-collector` | Checks new Calendar services every two minutes and logs timely frozen-model predictions | Keep active revision and experiment evidence |
| Cloud Run job `cp2-reporting-daily` | Refreshes immutable Bronze snapshots and publishes checked reporting views | Keep current image and rollback evidence |
| Cloud Scheduler jobs `cp2-prospective-every2m`, `cp2-reporting-daily-trigger`, `cp2-prospective-final-20261127` | Two-minute collection, daily reporting, one-time future evaluation | Keep through their planned runs |
| BigQuery `bronze`, `quality`, `silver`, `gold`, `audit`, `analytics_ml` | Source snapshots, environmental features, published views, release history and model data | Keep; published `silver`/`gold` views are the dashboard and collector interface |
| BigQuery `cp2r_<run>_silver` and `cp2r_<run>_gold` | Candidate views/tables for a reporting release | Keep every published run while rollback/audit can reference it; remove failed candidates only after checking status and all view/backup references |
| Cloud Storage `gs://profound-keel-500007-s4-cp2-prospective` | Private prediction receipts and collector state | Keep through evaluation and audit retention |
| Artifact Registry `cp2-reporting` | Collector and reporting job images | Keep current images and images needed for rollback/replay; review older tags before deleting |

On 30 September 2026, four failed releases were confirmed as `FAILED` by their latest `audit.release_runs` event. Their eight candidate datasets had no references in any current stable Silver/Gold view or `audit.release_backups` definition. The failed run records and immutable Bronze source snapshots were retained. These derived candidates were then deleted:

| Failed run ID | Candidate datasets removed |
|---|---|
| `20260930101441c9fedd` | Silver (16 views), Gold (31 objects) |
| `20260930094714bf40a6` | Silver (16 views), Gold (31 objects) |
| `20260928080718472688` | Silver (13 views), Gold (16 objects) |
| `20260928075706feaf1f` | Silver (8 views), Gold (14 objects) |

The published candidate datasets, including a run that initially failed and was subsequently published, were preserved. Old Cloud Run revisions and Artifact Registry images were preserved because they are rollback/replay material, not proven duplicate live resources. This cleanup was housekeeping after checking published pointers; never delete candidates as a way to recover from a failed release. See [the reporting runbook](README.md) for failure recovery.
