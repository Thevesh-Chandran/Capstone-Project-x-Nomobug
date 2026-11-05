# Executable code

The project workflow starts in [notebooks/00_Project_Overview.ipynb](../notebooks/00_Project_Overview.ipynb). The notebooks cover sources, cleaning, labels/partitions, predictors, training configuration, evaluation, planning and experiments. Python and SQL modules remain the implementation used by automation.

## Current entry points

Use [FILE_GUIDE.html](../FILE_GUIDE.html) to search by purpose. `python -m scripts.refresh_project_file_guide` refreshes it without executing notebooks or training models.

| Task | Entry point |
|---|---|
| Reporting refresh and promotion | `cp2_reporting_release.py` |
| Source collection | `load_operational_bronze.py`, `load_calendar_bronze.py` |
| Address matching | `cp2_geocoding.py` |
| Current pest-model status and verification | `cp2_model.py status`, `cp2_model.py verify` |
| Timely pest predictions | `cp2_cloud_collector.py` |
| Weekly forecasting | `cp2_planning_job.py`, `planning_engine.py` |
| KPI reconciliation | `validate_business_kpis.py` |
| Source sign-in renewal | `renew_google_access.py` |
| Project notebook/catalogue build | `python -m scripts.build_project_notebooks` |
| Warehouse display names and catalogue | `python -m scripts.update_warehouse_catalogue` |
| Restore an archived warehouse release | `restore_archived_bigquery_release.py` |

Use `.venv/Scripts/python.exe` from the project root. Check the selected command's help and protocol before running publishing, deployment or one-time evaluation commands.

## Remaining modules

### New research: 2 November

| Purpose | File |
|---|---|
| Operational forecasts | `research_operational_models_20261102.py` |
| Repeat-purchase timing | `research_repeat_survival_20261102.py` |
| Property warranty-risk study | `research_property_warranty_20261102.py` |
| Package the separate risk model | `train_warranty_risk.py` |
| Separate risk-test ledger | `warranty_risk_prospective.py` |

See the [2 November handover](../planning/CP2_PROJECT_HANDOVER_20261102.md). These are separate from the original frozen pest-return experiment. Research output is not automatically deployment approval or a validated future result.

Other modules are shared dependencies, tested model research, source rules or support utilities. Many files are retained because the live collector imports feature preparation, preprocessing and evaluation helpers; deleting every older-named module would break that chain. The [file catalogue](../FILE_GUIDE.html) identifies their role and purpose.

## Retired code

67 standalone old reports, prototypes, one-off repairs and comparisons were moved to [archive/retired_scripts](../archive/retired_scripts/README.md). They are outside the working scripts folder and container build context. The manifest preserves original paths and hashes. No byte-identical duplicate scripts were found.

Do not run all scripts as a batch. Historical code is not a second active workflow. Original source-profiling notebooks are under `notebooks/source_profiles`.
