# Nomobug Capstone Project

Latest changes: [2 November website and model handover](planning/CP2_PROJECT_HANDOVER_20261102.md). [Remaining verification](planning/CP2_REMAINING_TASKS_20261102.md). The current website source is deployed in revision cp2-portal-00087-cep. The custom dashboard entry is https://cp2-dashboard-thevesh20-3384s-projects.vercel.app/. The separate Vercel Metabase trial has not passed startup.

Business reporting, operational follow-up and experimentally evaluated prediction models using Sales, Calendar, contract reminder and environmental data.

Open [START_HERE.md](START_HERE.md) or [the searchable file guide](FILE_GUIDE.html).

The analysis workflow starts with [00_Project_Overview.ipynb](notebooks/00_Project_Overview.ipynb), then chapters 01–08: sources, cleaning, labels/partitions, predictors, the pest-return model, weekly planning and experiments. Saved executed outputs are included.

Implementation stays in `scripts`, `dbt`, `webapp`, `config` and `infra`. [Project_Structure.md](project_guide/Project_Structure.md) explains their roles. Frozen artifacts retain their dependency paths; the file and warehouse catalogues provide readable names.

The pest-return model is experimental. Weekly planning results are exploratory historical evidence; future evaluation is separate. Model outputs do not establish warranty entitlement, treatment completion, payment or profit.
