# Nomobug Capstone Project

Current system: [protected management workspace](https://cp2-portal-fav22krh7q-as.a.run.app/), with the Evidence dashboard at `/dashboard`. See [current architecture and coverage](planning/CP2_CURRENT_SYSTEM.md). Cloud Run refreshes reporting daily; archived handovers describe earlier deployments.

Business reporting, operational follow-up and experimentally evaluated prediction models using Sales, Calendar, contract reminder and environmental data.

Open [START_HERE.md](START_HERE.md) or [the searchable file guide](FILE_GUIDE.html).

The analysis workflow starts with [00_Project_Overview.ipynb](notebooks/00_Project_Overview.ipynb), then chapters 01–08: sources, cleaning, labels/partitions, predictors, the pest-return model, weekly planning and experiments. Saved executed outputs are included.

Implementation stays in `scripts`, `dbt`, `webapp`, `config` and `infra`. [Project_Structure.md](project_guide/Project_Structure.md) explains their roles. Frozen artifacts retain their dependency paths; the file and warehouse catalogues provide readable names.

The pest-return model is experimental. Weekly planning results are exploratory historical evidence; future evaluation is separate. Model outputs do not establish warranty entitlement, treatment completion, payment or profit.
