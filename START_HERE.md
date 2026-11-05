# Nomobug Capstone Project

## Current work: 2 November 2026

- **[Visual model guide](project_guide/models/index.html):** current frozen model, local candidates, probability test, inputs and source-linked experiment results.

- Open [FILE_GUIDE.html](FILE_GUIDE.html) for the searchable source index, notebook links and folder map.
- Website changes: [Project handover](planning/CP2_PROJECT_HANDOVER_20261102.md). The current website source, including the redesigned pages, is included in revision cp2-portal-00087-cep. Research-model limitations remain; this is not promotion to the frozen collector.
- Preview: [updated website on this laptop](http://127.0.0.1:8090/#decisions), while its local server is running. [Hosted website](https://cp2-portal-964813222593.asia-southeast1.run.app/#home) now includes the current source. [Custom dashboard](https://cp2-dashboard-thevesh20-3384s-projects.vercel.app/) uses Vercel assets and protected Cloud Run data.
- Latest research: [2 November model search](planning/CP2_OPERATIONAL_MODEL_SEARCH_20261102.md). It is separate from the original frozen pest-return experiment.
- Outstanding work: [verification and deployment](planning/CP2_REMAINING_TASKS_20261102.md). Owner targets remain unconfirmed. The new forward-test protocol requires timing review; a saved freeze alone does not establish a valid prospective test.
- Storage: [folder sizes](project_guide/Folder_Sizes.csv). Private data, saved model bundles and release evidence retain their original paths.

## Earlier recorded status

Latest main-model review: [28 October findings and repairs](planning/CP2_MAIN_MODEL_REVIEW_20261028.md). Reporting has recovered. The inspected recovery cohort is incomplete (24 missed eligible windows, 13 unresolved candidates); no complete prospective accuracy is claimed. The calibration candidate failed its promotion gate. [Probability calibration notebook](notebooks/08_Probability_Calibration.ipynb).

## Start here

- [Project file guide](FILE_GUIDE.html): chapters, file search and links.
- [Project notebook](notebooks/00_Project_Overview.ipynb): start here, then chapters 01–07.
- [HTML reading copy](notebooks/00_Project_Overview.html): same saved outputs without Jupyter.
- [Supervisor ZIP](outputs/project_notebooks/Nomobug_Project_Notebooks.zip): notebooks and aggregate evidence; no customer rows or credentials.
- [Folder and script guide](project_guide/Project_Structure.md).
- [BigQuery catalogue](project_guide/BigQuery_Catalogue.csv): IDs, readable names and purposes.

## Current system

[Website](https://cp2-portal-964813222593.asia-southeast1.run.app/#home) · [Workspace operations](planning/CP2_WORKSPACE_PURPOSE.md) · [Dashboard definitions](BUSINESS_ANALYTICS.md).

The website connects follow-up reviews, customer history, draft messages, weekly bookings and capacity planning. The management dashboard is a separate reporting surface.

## Models

The frozen pest-return model remains experimental. Its historical 100-service assessment had five positive returns: 94% accuracy, 40% precision and 40% recall, against 95% always-no-return accuracy. The later prospective refit uses 5,695 services; fitting records are not an independent test. Active pointer: `config/cp2_model_current.json`.

The weekly planning candidates predict bookings over two weeks and team-slot appointment hours over one week. Historical errors and baselines are in notebook 06. Live results are collected separately under `config/cp2_planning_v1.json`.

The recovery pest-model cohort ends 30 October; earliest full evaluation is 30 November, conditional on complete collection and outcomes. This guide is not a live collection-health check.

## Files

`notebooks`: review sequence. `scripts`: executable work. `dbt`: SQL. `config`: rules/protocols. `webapp`: application. `infra` and Docker/cloudbuild files: hosting. `outputs`: dated evidence. `planning`: specifications and historical records. `data` and `secrets`: private inputs and credentials.

Older evidence retains its path for traceability. A later filename does not establish a better or active model.
