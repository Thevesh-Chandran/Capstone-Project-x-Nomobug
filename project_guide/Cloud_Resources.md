# Cloud resources

Project: `profound-keel-500007-s4`. Region: `asia-southeast1`. Inventory checked 25 October 2026. Resource IDs retain their scheduled references; readable purposes are listed below.

## Services

| ID | Purpose |
|---|---|
| `cp2-portal` | Private staff website, tools, workspace records and AI request interface |
| `cp2-ollama` | Private language-model service; not the statistical prediction model |
| `cp2-prospective-collector` | Timely frozen pest-model collection and governed future evaluation endpoints |
| `cp2-info` | Public app information/privacy pages; separate from private customer tools |

## Batch jobs

| ID | Purpose |
|---|---|
| `cp2-reporting-daily` | Extract sources, validate and publish approved warehouse views |
| `cp2-planning-weekly` | Issue/evaluate weekly planning forecasts according to the frozen protocol |

## Scheduler

| ID | Malaysia schedule | Purpose |
|---|---|---|
| `cp2-reporting-daily-trigger` | Daily 06:00 | Reporting refresh |
| `cp2-planning-weekly-trigger` | Sunday 23:50 | Before-Monday planning collection |
| `cp2-prospective-every2m` | Every 2 minutes, 1–30 October | Frozen pest-model prediction windows |
| `cp2-recovery-final-20261130` | 30 November 15:00 | Recovery-cohort evaluation attempt |
| `cp2-prospective-october10-final-20261130` | 30 November 14:00 | Separate earlier cohort evaluation attempt |
| `cp2-prospective-october5-final-20261127` | 27 November 13:00 | Separate earlier cohort evaluation attempt |
| `cp2-prospective-final-20261127` | 27 November 12:00 | Original-cohort evaluation attempt |

All listed triggers were enabled at inspection. Enabled configuration is not proof of a successful run. Earlier incomplete cohorts remain separate and must not claim complete accuracy if their collection guards fail. One-time evaluator guards govern repeated scheduled attempts; calendar cron expressions recur annually unless later disabled. No schedules changed during this file-organisation task.

## Data and configuration

BigQuery: source/cleaning/reporting/research/check layers are in [BigQuery_Catalogue.csv](BigQuery_Catalogue.csv). Exact model pointers and protocols are in `config`, not inferred from cloud service names. Model source is in `scripts`; UI source is in `webapp`.

Container definitions and cloudbuild files remain at the repository root because existing build commands reference them. Credentials remain outside images and handover notebooks. Private workspace progress, reporting snapshots and model receipts are separate stores; see [workspace operations](../planning/CP2_WORKSPACE_PURPOSE.md) and [planning operations](../planning/CP2_PLANNING_FORECAST_OPERATIONS.md).
