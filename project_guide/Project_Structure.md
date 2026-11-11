# Nomobug project structure

## Project workflow

Start with [00 Project Overview](../notebooks/00_Project_Overview.ipynb). Chapters 01–07 cover sources, cleaning, labels and partitions, predictors, the pest-return model, weekly planning and experiments. Each notebook has saved executed outputs and an HTML copy. The full dictionary and individual input-removal results are in chapter 04.

The notebooks replay pinned evidence. They do not claim new training, fresh source validation or completed future evaluation. Full processing implementations stay in their script/SQL modules. Chapter 05 includes the actual model-construction, fitting and feature-preparation functions.

## Folders

| Folder | Contents | When to open it |
|---|---|---|
| `notebooks` | Eleven chapters and portable aggregate evidence | Project analysis and model explanation |
| `notebooks/source_profiles` | Original Sheets and Calendar profiling notebooks | Original live-source exploration; credentials required |
| `scripts` | Extraction, processing, models, experiments and operations | Reproduce a specific workflow |
| `dbt/models` | Typing, Calendar classification, links and Silver transformations | Data cleaning |
| `dbt/models/gold` | Reporting definitions | Business measures |
| `dbt/models/analytics_ml` | Model datasets and historical research SQL | Label and feature lineage |
| `dbt/tests`, `tests` | SQL and Python checks | Validate a change |
| `config` | Dictionaries, confirmed mappings, protocols and model pointers | Exact rules and active artifacts |
| `dashboard` | Evidence.dev report pages, queries and refresh job | Reporting development |
| `webapp` | Website, customer tools, planner and decision pages | Application development |
| `infra`, `.github`, `deploy` | Cloud configuration and containers | Deployment and schedules |
| `planning` | Policies, specifications and dated records | Context and operations |
| `outputs/model_validation` | Dated model studies | Chapter 07 evidence |
| `outputs/cp2-v2` | Frozen bundles, training evidence and prediction receipts | Audit/reproduction; preserve hashes and paths |
| `outputs/reporting_release` | Immutable release records | Warehouse lineage |
| `outputs/project_audit` | Verification and metadata backups | Audit and recovery |
| `outputs/project_notebooks` | Supervisor ZIP | Share the notebook series |
| `data` | Private source and derived data | Local reproduction |
| `secrets`, `.env` | Credentials | Private; never share |
| `.venv` | Python environment | Runtime |
| `docs` | Original documents and CP2 report copies | Report writing |
| `tmp`, `.codex-tmp` | Working artifacts | Not a reading entry point |

## Main executable files

| File | Role |
|---|---|
| `scripts/cp2_reporting_release.py` | Scheduled source refresh, dbt, reconciliation and reporting promotion |
| `scripts/load_operational_bronze.py` | Sheets extraction into immutable snapshots |
| `scripts/load_calendar_bronze.py` | Calendar extraction |
| `scripts/cp2_geocoding.py` | Address lookup and precision |
| `scripts/service_programme_policy.py` | Confirmed linked-programme rules |
| `scripts/calendar_appointment_policy.py` | Cancelled/rescheduled and temporary appointment rules |
| `scripts/sales_payment_rules.py` | Recorded amount and reminder interpretation |
| `scripts/benchmark_warranty_models.py` | Input preparation, time/group splits, metrics and training utilities |
| `scripts/compare_callback_candidates_v2.py` | Corrected candidate fitting and selection |
| `scripts/cp2_model.py` | Frozen pest-model status, verification and governed prediction/evaluation commands |
| `scripts/cp2_cloud_collector.py` | Timely cloud predictions |
| `scripts/research_management_forecasts_20261021_v2.py` | Historical weekly comparisons |
| `scripts/planning_engine.py` | Weekly forecast calculations |
| `scripts/cp2_planning_job.py` | Planning collection and outcomes |
| `scripts/build_project_notebooks.py` | Rebuild the project notebook workflow and catalogue |
| `scripts/update_warehouse_catalogue.py` | Back up and update BigQuery metadata and catalogue |
| `webapp/server.py` | Authenticated website/API |
| `webapp/workspace.py`, `webapp/action_log.py` | Operational decisions and durable internal progress |

Do not run the whole scripts folder. Some commands publish, request sign-in, deploy or evaluate once. Read the selected command's help and protocol first.

## Names and compatibility

The refreshed [file guide](../FILE_GUIDE.html) groups the current source files by project area and links all eleven notebook chapters. [Folder_Sizes.csv](Folder_Sizes.csv) records storage usage. Rebuild navigation without retraining or notebook execution using `python -m scripts.refresh_project_file_guide`; add `--clean-caches` to remove only regenerable Python/test caches outside protected evidence folders.

The hosted workspace uses the [Evidence dashboard](../dashboard/README.md). See [current system and coverage](../planning/CP2_CURRENT_SYSTEM.md) for deployment and reporting details.

Python modules, dbt models, bundles, snapshots and cloud resource IDs retain their dependency paths. Their readable names and purposes are in [File_Catalogue.csv](File_Catalogue.csv) and [the searchable guide](../FILE_GUIDE.html).

BigQuery has numbered dataset display names and object descriptions; SQL IDs still work. `gold.READ_ME` explains reporting sources; `analytics_ml.READ_ME` explains historical model objects. [BigQuery_Catalogue.csv](BigQuery_Catalogue.csv) lists stable-layer objects. Versioned releases support evidence/rollback. No table was deleted merely because its date looked old.

## Sharing

The project notebook ZIP contains notebooks, HTML copies, aggregate evidence and selected SQL/code excerpts. It excludes source customer rows, addresses, identifiers, credentials, full private inputs and model binaries. It contains business research results: share with approved project reviewers, not a public repository.

## Retired code

67 unreferenced standalone historical scripts were moved out of `scripts` to `archive/retired_scripts`. The archive manifest records original paths and byte hashes; archived files are not part of container builds. No exact duplicate scripts were found. Remaining scripts include dependencies used by the live system and tests, not just user-facing commands. See `scripts/README.md` for the current entry points.
