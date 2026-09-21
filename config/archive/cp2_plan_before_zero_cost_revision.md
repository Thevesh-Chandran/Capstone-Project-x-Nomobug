# Historical CP2 Plan — Superseded 3 September 2026

Decision history only. Do not follow this schedule or its BigQuery/Cloud Run instructions. The active plan is CP2_SEP_NOV_IMPLEMENTATION_PLAN.md at the repository root. The original assumptions of roughly 14 hours/week and billing-enabled cloud services were superseded by the one-hour daily limit and zero-payment requirement.

## Outcome

By 30 November 2026, the repository should contain a reproducible, privacy-aware analytics system that:

1. extracts the approved Google Sheets tabs and six Google Calendars;
2. preserves raw source records with lineage and refresh metadata;
3. cleans and validates the selected business fields;
4. links prospects, sales, payments, warranty claims, refunds, recurring payments, and Calendar events with documented confidence;
5. enriches usable service records with location and historical weather when coverage is sufficient;
6. creates tested Bronze, Silver, Gold, quality, ML, and clustering datasets in BigQuery;
7. trains and evaluates a predictive model and a DBSCAN hotspot analysis without overstating weak evidence;
8. runs through one repeatable Cloud Run Job scheduled by Cloud Scheduler;
9. presents a browser-based management dashboard in hosted Apache Superset through Preset Cloud;
10. exposes data-quality, matching, privacy, model, clustering, cost, and refresh limitations; and
11. includes evaluation evidence, setup instructions, screenshots, and a reliable demonstration path.

## Planning Assumptions

- Schedule: approximately 2 focused hours Monday-Friday, 4 hours Saturday, and Sunday as rest or catch-up.
- Weekly capacity: approximately 14 hours.
- The student implements each step and learns what the code does; guidance supplies small code blocks, commands, explanations, checks, and debugging support.
- Credentials, tokens, refund bank details, unnecessary direct identifiers, raw exports, and notebook outputs remain outside Git. Only approved fields are loaded to the controlled cloud project, and Preset receives read-only access to safe reporting datasets.
- November is primarily for validation, evaluation, documentation, and repair. New features stop on 1 November.
- A daily task is complete only when its acceptance check passes. Unfinished work moves into the next buffer day; it is not hidden or skipped.

## Current Starting Point

Already completed:

- project and Git audit;
- preservation of the CP1 proposal, logbook, and Gantt files;
- read-only Google OAuth setup;
- confirmation of two workbooks, sixteen tabs, and six Nomobug Calendars;
- full local source extraction and initial profiles;
- three beginner-friendly pandas notebooks;
- initial source inventory, source decisions, data dictionary, and 22 quality findings;
- business scope narrowed to the useful operational sources.

Important known issues:

- Prospects `2026` has 32,580 loaded rows and 17,959 exact duplicate rows.
- A repeated phone number can be a genuine new advertisement conversation and must not be removed automatically.
- `B2B FOLLOW UP` contains exact duplicates and requires a clear inspection-booking rule.
- SALES service dates are not maintained; Google Calendar is the operational date authority.
- PAYMENT LINK has no Customer ID, so phone matching needs coverage and confidence reporting.
- WARRANTY CLAIM has no stable claim ID and stores technician history in repeated columns.
- Commercial Clients is derived from SALES and must not be counted again.
- Recurring Payments is derived from SALES and must not become duplicate revenue.
- LTV is unused and excluded.
- Calendar history differs by team, so comparisons require a common time window.

## Final Tool Decision

### Core tools

- Python 3.14 in a project virtual environment.
- pandas for source extraction, profiling, and transformations that are clearer in Python.
- Google BigQuery for Bronze, Silver, Gold, quality, audit, model-output, and clustering datasets.
- dbt Core with `dbt-bigquery` for versioned SQL transformations, documentation, lineage, and data tests.
- Google Cloud Python clients for controlled batch loading and cloud authentication.
- scikit-learn for the required predictive modelling and DBSCAN workstreams.
- pytest plus dbt tests for pipeline, Python, transformation, and relationship checks.
- Open-Meteo for historical rainfall, humidity, and temperature.
- Google Cloud Run Jobs for executing the complete batch pipeline.
- Google Cloud Scheduler for starting the Cloud Run Job on a defined schedule.
- Secret Manager for cloud secrets and Artifact Registry for the pipeline container image.
- Docker Desktop and one project Dockerfile for local reproducibility and Cloud Run packaging; dashboard users do not install Docker.
- Preset Cloud Starter, the hosted Apache Superset service, for the no-code chart builder and browser dashboard. The free plan currently allows one workspace and up to five users.

### Deliberately deferred

- Apache Airflow: Cloud Scheduler and Cloud Run provide sufficient scheduling, execution history, retries, and logs for this batch pipeline without operating Airflow infrastructure.
- Self-hosted Apache Superset: Preset Cloud hosts Superset and removes the need to maintain a public server. A local export/fallback is still documented.
- Supabase: it cannot host the Superset application and would duplicate BigQuery without solving the hosting requirement.
- Power BI, Tableau, Looker Studio, Metabase, and Streamlit: they are not the selected dashboard destination.
- FastAPI: not required for a BI dashboard. Add one read-only endpoint only if the complete dashboard and evaluation are already ahead of schedule.
- Ollama/local AI: optional explanation layer, not part of the core analytical logic.
- Extra predictive models, extensive hyperparameter tuning, and SHAP: optional after the required baseline, selected model, leakage checks, and evaluation pass.
- KDE or additional clustering algorithms: optional after the required DBSCAN implementation and sensitivity analysis pass.

## Required Repository Shape by the End of September

```text
config/                 Safe source maps, aliases, rules, and dictionary
infra/                  Dockerfile and non-secret Google Cloud deployment settings
notebooks/              Learning and investigation notebooks with cleared outputs
scripts/                Small entry points and retained prototypes
dbt/                    dbt project, sources, Silver/Gold models, tests, and documentation
src/nomobug/
  extract/              Google Sheets, Calendar, and weather readers
  load/                 BigQuery loading and idempotency
  transform/            Normalisation and matching logic
  modelling/            Predictive model training, evaluation, and scoring
  clustering/           DBSCAN preparation, testing, and output generation
  quality/              Contracts, flags, and quality summaries
  pipeline/             Ordered pipeline runner and run logging
tests/                  Python unit and integration tests using synthetic data
README.md               Repository landing page only
CP2_START_HERE.md       Technical implementation guide
```

## Definition of Done by Month

### 30 September: ETL foundation complete

- One command performs an end-to-end approved-source refresh.
- BigQuery Bronze, Silver, Gold, quality, and audit objects are created through Python and dbt.
- Re-running the pipeline does not create duplicate facts.
- Pipeline run status and row counts are logged.
- Exact copied rows and legitimate repeat prospect interactions are treated separately.
- Calendar match coverage and confidence are reported.
- Weather enrichment either works with documented coverage or is explicitly excluded with evidence.
- The core automated tests pass.

### 31 October: hosted dashboard and advanced analytics complete

- A Cloud Run Job executes the containerised pipeline and Cloud Scheduler starts a controlled scheduled run.
- Preset Cloud connects through a read-only service account that can access only Gold and approved quality views.
- The required predictive model has a defined target, leakage controls, baseline comparison, test-set metrics, and limitations.
- The required DBSCAN analysis records eligible coverage, parameters, noise, clusters, and sensitivity results.
- Core dashboard pages cover executive KPIs, prospects/sales/payments, services/warranty/refunds, area/weather, DBSCAN hotspots, predictive results, and data quality/refresh.
- Date, area, pest, package, and team filters work where supported.
- Refresh, failure recovery, safe export, and clean deployment are demonstrated.
- Dashboard v1 screenshots are captured.

### 30 November: evaluated submission release complete

- Key figures are reconciled manually against source records.
- Privacy, failure recovery, backup restoration, and refresh tests pass.
- Three to five users complete practical dashboard tasks where availability allows.
- High-impact feedback and critical bugs are addressed.
- The data dictionary, lineage, limitations, architecture, evaluation, report, slides, and demo are ready.
- A release commit/tag and offline demonstration backup exist.

## September 2026: ETL, Storage, Cleaning, Matching, and Tests

| Date | Time | Main task | Required output / acceptance check |
|---|---:|---|---|
| Tue 1 Sep | 2h | Freeze the minimum viable scope. Review source decisions, define the five essential dashboard questions, and separate required work from optional extensions. | Written scope contains no LTV, no duplicate Commercial Clients facts, Calendar as date authority, plus required predictive ML and DBSCAN deliverables. |
| Wed 2 Sep | 2h | Create the Python 3.14 virtual environment and pinned dependency file. Confirm Git ignores `.venv`, secrets, raw data, generated profiles, model artifacts, and notebook outputs. | Fresh environment imports pandas, Google Cloud/Google API clients, dbt-bigquery, scikit-learn, pytest, and requests without errors. |
| Thu 3 Sep | 2h | Create or verify the Google Cloud project, billing safeguards, BigQuery API, dataset location, IAM design, and least-privilege service-account plan. | Project, region, budget alert, APIs, and role matrix are recorded without downloading or committing broad credentials. |
| Fri 4 Sep | 2h | Design BigQuery datasets: `bronze`, `silver`, `gold`, `quality`, `audit`, and `analytics_ml`. Define table naming, partitioning candidates, expiration policy, and safe dashboard access. | Dataset design identifies location, owner, data class, retention, writer, and reader for every layer. |
| Sat 5 Sep | 4h | Build the smallest vertical slice: load the local `2026.csv` snapshot into one BigQuery Bronze table with source name, source row number, extracted time, load ID, and row hash. | BigQuery row count equals the snapshot count and a rerun does not silently multiply rows. |
| Sun 6 Sep | Rest | Rest, back up the local ignored data, and record blockers only. | No new feature work; Monday starts from a clean written status. |
| Mon 7 Sep | 2h | Generalise the BigQuery Bronze loader so it accepts a DataFrame, source object, target table, schema, write mode, and load ID. | One reusable loader handles `2026` and `B2B FOLLOW UP`, with counts and job IDs logged. |
| Tue 8 Sep | 2h | Convert the prospects extraction into a reusable module while retaining a simple notebook demonstration. Add lineage fields before loading. | Live extraction can refresh both selected prospect tabs into Bronze. |
| Wed 9 Sep | 2h | Convert the Session & Payment extraction for SALES, PAYMENTS, PAYMENT LINK, WARRANTY CLAIM, REFUND, Recurring Payments, and Commercial Clients. Exclude LTV. | Approved tabs load; source table row counts are logged. |
| Thu 10 Sep | 2h | Convert Calendar extraction into a reusable paginated module. Preserve event ID, recurring ID, Calendar name, status, timestamps, and source update time. | All six Calendars load and event counts match the controlled snapshot within expected source changes. |
| Fri 11 Sep | 2h | Define BigQuery idempotency: snapshot ID, natural source identifier where available, row hash, loaded timestamp, and atomic staging-to-current behaviour. | Running the same input twice produces the expected current representation plus audit history, not duplicated facts. |
| Sat 12 Sep | 4h | Run and review the complete BigQuery Bronze refresh. Add a source-count reconciliation table in `audit`. | Every approved source has start time, finish time, extracted rows, loaded rows, BigQuery job ID, and status. |
| Sun 13 Sep | Buffer | Catch up only if a Bronze acceptance check failed; otherwise rest. | Bronze milestone is either passed or has one clearly recorded blocker. |
| Mon 14 Sep | 2h | Finalise source contracts and initialise the dbt project with BigQuery sources, environments, tags, naming conventions, and a credential method that stays outside Git. | `dbt debug` and a minimal source test pass; contracts cover every in-scope source and distinguish required, important, and optional fields. |
| Tue 15 Sep | 2h | Build the Prospects `2026` Silver model: whitespace, empty strings, status/category labels, source row ID, phone normalisation, exact-duplicate flag, and repeat-phone flag. | Exact duplicates remain auditable; phone repeats remain valid interactions; no raw row is silently deleted. |
| Wed 16 Sep | 2h | Clean `B2B FOLLOW UP` and define the inspection-booking outcome using Appointment Date, Lead to Appointment, and Status. | Rule produces booked, not booked, and needs-review groups with counts. |
| Thu 17 Sep | 2h | Clean SALES. Rename both invoice columns explicitly, standardise Customer ID, amounts, package, pest, and customer type. Mark all SALES service-date columns non-authoritative. | A Silver sales row represents a sale/agreement and never supplies the operational service date. |
| Fri 18 Sep | 2h | Clean PAYMENTS and PAYMENT LINK. Parse amounts and statuses, keep transaction grain, and prepare phone-only linkage for payment links. | Completed/pending values are profiled; payment transactions are not collapsed into sales rows. |
| Sat 19 Sep | 4h | Clean WARRANTY CLAIM, REFUND, Recurring Payments, and Commercial Clients. Unpivot technician and recurring schedule columns. Exclude refund bank details from Silver. | Warranty technician history is long-form; bank account number is absent from Silver/Gold; derived tabs are not double-counted. |
| Sun 20 Sep | Rest | Rest and create a one-page cleaning-rule summary for personal understanding. | Rules are explainable without reading the code. |
| Mon 21 Sep | 2h | Profile Calendar title/description formats safely and define cautious event categories: inspection, paid/new service, warranty, complimentary, replacement, follow-up, unknown. | Category rules include an `unknown` fallback and no forced attribution. |
| Tue 22 Sep | 2h | Implement Calendar matching pass 1 using Customer ID and normalised phone when present in controlled event text. | Exact-ID and phone match counts are stored separately. |
| Wed 23 Sep | 2h | Implement lower-confidence matching using normalised name plus bounded date context; never use name alone. | Every match stores method, confidence, candidate count, and review reason. |
| Thu 24 Sep | 2h | Produce the match-quality report and manually inspect a safe sample from each match class without committing identifiers. | Coverage, ambiguity, false-match sample findings, and unmatched counts are documented. |
| Fri 25 Sep | 2h | Build core dbt Silver relational models: customer linkage, sales, payment transactions, operational service events, warranty claims, and refunds. | dbt uniqueness, accepted-value, and relationship tests pass or create explicit quality failures. |
| Sat 26 Sep | 4h | Measure address/postcode/area availability and define the location privacy approach. Create a small reviewed area-to-centroid lookup if justified. | A written gate decides whether coordinate-based analysis is supported; full addresses remain outside reporting views. |
| Sun 27 Sep | Buffer | Catch up on matching/location only. If current coordinate coverage is weak, freeze maps as a limitation and use area rankings. | No invented coordinates and no uncontrolled address API uploads. |
| Mon 28 Sep | 2h | Build cached Open-Meteo historical enrichment for matched service date and area centroid. Calculate same-day, previous-day, 3-day, and 7-day rainfall plus temperature/humidity fields. | API responses are cached locally; weather coverage and missing reasons are reported. |
| Tue 29 Sep | 2h | Build the first dbt Gold views: executive daily metrics, prospect funnel, payments, service/warranty/refund outcomes, match quality, source quality, and refresh status. | Each view has a declared grain, documentation, passing tests, and no personal direct identifiers. |
| Wed 30 Sep | 3h | Create `run_pipeline.py`, order extraction, BigQuery loading, dbt Silver/Gold, quality logging, and failures; rerun from an empty controlled dataset and freeze the September release. | One local command completes the initial Bronze-to-Gold path; rerun is safe; pytest, dbt tests, and pipeline run record pass. |

## October 2026: Cloud Deployment, Predictive ML, DBSCAN, and Superset Dashboard

| Date | Time | Main task | Required output / acceptance check |
|---|---:|---|---|
| Thu 1 Oct | 2h | Review the September evidence and learn the cloud deployment chain: Dockerfile, Cloud Build, Artifact Registry, Cloud Run Job, service account, Secret Manager, and Cloud Scheduler. | Can explain where code, image, secrets, execution, logs, warehouse, and dashboard are hosted. |
| Fri 2 Oct | 2h | Create a minimal Dockerfile and `.dockerignore` for `run_pipeline.py`; test the image locally with safe configuration and no credentials baked into layers. | The container runs the controlled pipeline entry point and image inspection reveals no secret or raw data. |
| Sat 3 Oct | 4h | Deploy the first Cloud Run Job from the image, assign the least-privilege pipeline service account, configure Secret Manager references, and execute a manual cloud run. | Cloud Run completes and writes an auditable BigQuery run with no local credential file in the image. |
| Sun 4 Oct | Buffer | Resolve Cloud Run permissions, region, memory, timeout, or container issues only; otherwise rest. | One manual cloud execution is stable before scheduling or dashboard work. |
| Mon 5 Oct | 2h | Create Cloud Scheduler with authenticated invocation and Malaysia-time scheduling; configure retry behaviour and a disabled-by-default safe test schedule. | A scheduled run completes once, records its trigger, and cannot be invoked anonymously. |
| Tue 6 Oct | 2h | Create a dedicated BigQuery read-only service account for Preset with access only to Gold and selected quality views. | The dashboard identity cannot read Bronze, direct identifiers, raw Calendar text, or refund bank information. |
| Wed 7 Oct | 2h | Create the free Preset Cloud Starter workspace, connect BigQuery, add safe datasets, and verify the five-user limit and workspace constraints. | Preset connects successfully and exposes only approved reporting datasets. |
| Thu 8 Oct | 2h | Freeze KPI definitions and denominators before drawing charts. Define interactions, unique phones, B2B inspections, closed sales, completed payments, service events, claims, refunds, matching, and refresh status. | KPI dictionary states grain, filter, numerator, denominator, and caveat. |
| Fri 9 Oct | 2h | Create Executive charts: current totals, monthly trends, top pests/areas, warranty/refund indicators, and last successful refresh. | Each value matches a direct BigQuery check. |
| Sat 10 Oct | 4h | Assemble Executive Dashboard v1 in Preset with native filters, readable labels, and short interpretation notes. | A manager can answer “what is happening?” without viewing raw data. |
| Sun 11 Oct | Rest | Rest and capture a safe screenshot of v1 for progress evidence. | Screenshot contains no direct personal identifiers. |
| Mon 12 Oct | 2h | Finalise the predictive question, target, observation grain, eligible population, prediction time, censoring, and business action. | The model target is measurable from pre-outcome data and has no obvious future-information leakage. |
| Tue 13 Oct | 2h | Build the modelling dataset and time-aware train/validation/test split. Profile class balance, missingness, leakage risks, and sample size. | Every model feature has an availability timestamp and the held-out test set remains untouched. |
| Wed 14 Oct | 2h | Train a simple baseline and the selected interpretable classification model in a reproducible pipeline with preprocessing. | The selected model is compared with the baseline and the run saves parameters, features, split dates, and version. |
| Thu 15 Oct | 2h | Evaluate predictive performance using appropriate test-set metrics, confusion matrix, calibration or threshold analysis, and subgroup/error review. | Results include limitations and do not claim usefulness if performance or coverage is weak. |
| Fri 16 Oct | 2h | Write prediction scores, risk bands, model metrics, feature influence, and run metadata to `analytics_ml`; create safe Gold prediction views. | Every displayed prediction is traceable to a model run and contains no target leakage or direct identifier. |
| Sat 17 Oct | 4h | Build the Predictive Analytics dashboard page in Preset with model performance, risk distribution, segments, feature influence, and clear non-causal wording. | A reviewer can understand what was predicted, when, for whom, how well, and what should not be concluded. |
| Sun 18 Oct | Buffer | Catch up on cloud deployment, Preset, or the predictive workstream only. | Cloud pipeline, executive page, and required predictive experiment pass or have one recorded blocker each. |
| Mon 19 Oct | 2h | Prepare the DBSCAN dataset: eligible event definition, privacy-safe coordinates, common time window, duplicate handling, projection/distance method, and coverage report. | Eligible and excluded counts reconcile; no invented coordinates or uncontrolled address upload occurs. |
| Tue 20 Oct | 2h | Select candidate `eps` and `min_samples` values using domain scale, neighbour-distance evidence, and documented parameter ranges. | Parameter choices are expressed in meaningful distance terms and are reproducible. |
| Wed 21 Oct | 2h | Run DBSCAN across candidate settings; record cluster count, sizes, noise share, stability, area/pest composition, and sensitivity. | The required DBSCAN result distinguishes clusters from noise and does not hide unstable settings. |
| Thu 22 Oct | 2h | Create `analytics_ml.dbscan_points`, cluster summaries, parameter-test results, and privacy-safe Gold hotspot views. | Each cluster output stores model parameters, eligible coverage, run ID, and limitation flags. |
| Fri 23 Oct | 2h | Build Preset heatmap and DBSCAN charts using latitude/longitude, cluster label, noise, pest, warranty/recurrence, weather, and time filters. | Map counts reconcile to eligible records and cluster colours/noise labels remain interpretable. |
| Sat 24 Oct | 4h | Build the remaining Prospects/B2B, Sales/Payments, Service, Warranty/Refund, Area/Weather, Recommendation, and Data Quality pages; integrate shared filters. | Operational dates come only from Calendar, metrics retain correct grains, and every page answers a named decision question. |
| Sun 25 Oct | Rest | Rest and freeze dashboard feature scope. | Only correctness, reliability, privacy, evaluation, and documentation work remain. |
| Mon 26 Oct | 2h | Test Cloud Scheduler retries, Cloud Run timeouts, failed-step logging, last-success preservation, and manual recovery. | One deliberate failure is visible in audit logs and does not replace the last valid Gold dashboard state. |
| Tue 27 Oct | 2h | Create BigQuery export/recovery steps, Preset asset/screenshot backup, model artifact policy, and local `run_pipeline.py` fallback. | A safe backup exists and the core evidence can be demonstrated if Preset or a live API is unavailable. |
| Wed 28 Oct | 2h | Conduct the security/privacy review: IAM, service accounts, Secret Manager, Preset connection, BigQuery views, screenshots, logs, exports, Git index, and cloud regions. | No committed or dashboard-visible phone, email, full address, bank account, OAuth token, private key, or password. |
| Thu 29 Oct | 2h | Test BigQuery query cost and performance, partition/filter behaviour, Preset load time, Cloud Run memory/time, and budget alerts. | Main dashboard performs acceptably and cost controls are evidence-based rather than assumed. |
| Fri 30 Oct | 3h | Perform a clean deployment demonstration: configure safe cloud identities, build/deploy the job, run pipeline, open Preset, and recover from one controlled failure. | Setup/run instructions work from a clean state with offline Gold and screenshot fallbacks. |
| Sat 31 Oct | 4h | Freeze Dashboard v1 and advanced analytics, capture safe evidence, record limitations, and create the October milestone release. | Hosted Superset, scheduled cloud pipeline, predictive model, and DBSCAN meet the October definition of done. |

## November 2026: Validation, Feedback, Documentation, and Submission

| Date | Time | Main task | Required output / acceptance check |
|---|---:|---|---|
| Sun 1 Nov | 1h | Feature freeze. Move every unfinished idea to “future work” unless it blocks a required business question. | No new optional framework, model, dashboard page, or API enters scope. |
| Mon 2 Nov | 2h | Write the final test matrix covering extraction, contracts, loading, cleaning, joins, KPIs, predictive ML, DBSCAN, privacy, refresh, dashboard, cost, backup, and recovery. | Every requirement has a test method, expected result, actual result, and evidence location. |
| Tue 3 Nov | 2h | Run extraction and idempotency tests with synthetic fixtures and one controlled live refresh. | Source count changes are explained; rerun does not multiply facts. |
| Wed 4 Nov | 2h | Run dbt and transformation quality tests: not-null, uniqueness, accepted values, relationship coverage, date validity, amount parsing, source freshness, and documented grains. | Failures become recorded defects or documented source limitations. |
| Thu 5 Nov | 2h | Manually trace a safe sample from source to Bronze, Silver, Gold, and dashboard for each major relationship. | Evidence shows lineage and match method for prospects, sales, payment, Calendar, warranty, and refund paths. |
| Fri 6 Nov | 2h | Recalculate core KPIs manually in pandas/BigQuery and compare with Preset; independently reproduce a small model/cluster sample. | Differences are zero or explained by an explicit filter, grain, eligibility, or model rule. |
| Sat 7 Nov | 4h | Bug-fix sprint 1: repair all critical/high issues found by technical validation and rerun regression tests. | No open critical defect; every high defect has a fix or defensible limitation. |
| Sun 8 Nov | Buffer | Rest or complete only failed validation tasks. | Test matrix status is current. |
| Mon 9 Nov | 2h | Perform the final privacy audit on Google Cloud IAM, BigQuery datasets/views, Preset access, model outputs, notebook outputs, logs, screenshots, exports, Git index, and commit history. | Submission materials and dashboard surfaces contain no unnecessary direct personal or financial identifiers. |
| Tue 10 Nov | 2h | Test controlled failures: missing source column, unavailable Google API, malformed date, duplicate load, unmatched Calendar event, and missing weather response. | Pipeline fails safely or flags the issue, logs it, and preserves the last successful dashboard state. |
| Wed 11 Nov | 2h | Test BigQuery export/recovery, container redeployment, dbt rebuild, model-output restoration policy, and Preset asset/screenshot fallback. | Rebuilt Gold counts and core dashboard evidence match the controlled backup. |
| Thu 12 Nov | 2h | Prepare the usability script and feedback form for 3-5 Nomobug users: area risk, warranty review, refresh recency, and recommendation-evidence tasks. | Tasks, rating questions, consent/privacy wording, and observation sheet are ready. |
| Fri 13 Nov | 2h | Prepare a stable user-test build and short facilitator instructions. Arrange sessions where possible. | Test users receive the same build and task wording. |
| Sat 14 Nov | 4h | Conduct usability round 1 or a supervised pilot if users are unavailable. Record completion, confusion, usefulness, trust, and comments. | Feedback is evidence, not reconstructed from memory. |
| Sun 15 Nov | 1h | Triage feedback into critical, high-value, cosmetic, and future work. | Only changes that improve correctness, clarity, trust, or the assessed tasks enter the final sprint. |
| Mon 16 Nov | 2h | Implement the highest-impact usability changes. | Changed dashboard tasks are retested against the same expected answers. |
| Tue 17 Nov | 2h | Improve labels, colour contrast, filter names, mobile/laptop readability, definitions, caveats, empty states, and help text. | A first-time reviewer can understand metrics and limitations without verbal explanation. |
| Wed 18 Nov | 2h | Conduct user-test round 2 or supervisor review on the revised build. | Major round-1 misunderstandings are resolved or explicitly documented. |
| Thu 19 Nov | 2h | Close evaluation findings and export final tables: test results, match/weather coverage, predictive metrics, DBSCAN sensitivity, quality metrics, cost, and usability summaries. | Evaluation evidence is ready for the report and contains no private identifiers. |
| Fri 20 Nov | 2h | Produce final architecture, ETL-flow, lineage, and dashboard screenshots. | Visuals match the implemented system, not the older proposal architecture. |
| Sat 21 Nov | 4h | Finalise repository setup/run/backup/troubleshooting instructions and code comments. Remove temporary artifacts and clear notebook outputs. | Another person can follow the README and reproduce the safe demo without assistance. |
| Sun 22 Nov | 2h | Finalise data dictionary, source-to-target mapping, KPI definitions, cleaning rules, match-confidence rules, and limitation register. | Documentation agrees with code and dashboard field names. |
| Mon 23 Nov | 2h | Draft the evaluation results and limitations using actual evidence. State exclusions and failed gates honestly. | Every quantitative claim has a source/test result; associations are not written as causes. |
| Tue 24 Nov | 2h | Update final report methodology and implementation sections to describe the implemented stack and deviations from the proposal. | BigQuery, dbt, Cloud Run/Scheduler, predictive ML, DBSCAN, and hosted Superset are described accurately; Airflow and self-hosting are not falsely claimed. |
| Wed 25 Nov | 2h | Complete results, discussion, recommendations, future work, and privacy/ethics sections. | Report answers the objectives and distinguishes delivered work from future work. |
| Thu 26 Nov | 2h | Prepare final presentation slides and a short live-demo route. | Slides show problem, architecture, data quality, pipeline, dashboard, evidence, limitations, and value. |
| Fri 27 Nov | 2h | Rehearse the full demonstration twice: normal path and offline/failed-API path. Time the presentation and prepare likely questions. | Demo fits the available time and does not depend on live Google access alone. |
| Sat 28 Nov | 4h | Bug-fix sprint 2 and release-candidate validation. Only critical correctness, security, setup, or demo issues may be changed. | Full regression suite passes and release checklist is signed off. |
| Sun 29 Nov | Buffer | Rest, back up repository/database/dashboard/report/slides, and verify files open. | At least two recoverable local copies exist; no last-minute feature work. |
| Mon 30 Nov | 3h | Create the final commit/tag and submission package; run the final privacy and reproducibility checks; submit only verified artifacts. | Final release, report, presentation, demo backup, test evidence, and safe repository are complete. |

## Weekly Milestone Gates

Do not progress merely because the calendar changed.

1. **Bronze gate:** approved sources load with lineage, counts, and idempotency.
2. **Silver gate:** each source has a declared grain, cleaning rules, rejected/flagged behaviour, and safe identifiers.
3. **Matching gate:** coverage, confidence, ambiguity, and unmatched records are measurable.
4. **Weather/spatial gate:** location and date coverage are measured; the DBSCAN experiment still runs on the eligible subset, with coverage limits stated rather than hidden.
5. **Predictive gate:** target, eligibility, leakage controls, baseline, held-out evaluation, traceability, and limitations are complete.
6. **DBSCAN gate:** distance method, parameters, eligible population, noise, sensitivity, stability, and privacy are documented.
7. **Gold gate:** metrics have definitions and pass manual reconciliation.
8. **Dashboard gate:** Preset reads only safe Gold/quality views and answers named business questions.
9. **Release gate:** clean deployment, scheduled run, cost controls, backup, recovery, privacy, tests, and demo all pass.

## How Each Guided Work Session Will Operate

For each day, the student can send: `Start 1 September`, `Start today's task`, or the exact task name.

The guided session will then:

1. inspect the current Git status and only the files relevant to that day's task;
2. explain the business reason and the technical concept in plain language;
3. show the intended input, transformation, and output;
4. provide small copyable code blocks or exact platform steps;
5. identify which file each block belongs in and what each important line does;
6. ask the student to run it locally without pasting secrets or customer records;
7. interpret the safe terminal output or error;
8. add or run an acceptance check;
9. explain what was learned and update the next task only after the check passes; and
10. commit or push only when explicitly requested and after reviewing the exact Git scope.

The code will not be dumped as one unexplained final system. Notebook-style DataFrames will be used for learning and investigation. Reusable modules will be introduced gradually when repeated code becomes a maintenance problem.

## Scope-Reduction Rules

If the plan falls behind, remove work in this order:

1. local AI/Ollama;
2. FastAPI;
3. Airflow or any second orchestration platform;
4. extra predictive algorithms, extensive tuning, and SHAP beyond an explainable core result;
5. KDE or extra clustering algorithms beyond DBSCAN;
6. advanced upsell or treatment-difficulty extensions beyond the agreed prediction target;
7. non-essential dashboard pages and decorative visualisations.

Never remove:

- raw-data preservation and lineage;
- data-quality reporting;
- Calendar date authority;
- safe customer/service matching;
- one evaluated predictive modelling workstream;
- one evaluated DBSCAN workstream;
- privacy controls;
- refresh logging;
- manual KPI validation;
- backup/recovery testing; or
- honest limitations.

## Reference Setup Guidance

- [BigQuery documentation](https://cloud.google.com/bigquery/docs)
- [dbt BigQuery setup](https://docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup)
- [Cloud Run Jobs](https://cloud.google.com/run/docs/create-jobs)
- [Cloud Scheduler](https://cloud.google.com/scheduler/docs)
- [Google Secret Manager](https://cloud.google.com/secret-manager/docs)
- [Docker documentation](https://docs.docker.com/)
- [Preset Cloud pricing and Starter limits](https://preset.io/pricing/)
- [Preset BigQuery connection](https://docs.preset.io/docs/big-query-database)
- [Apache Superset documentation](https://superset.apache.org/)
- [scikit-learn model evaluation](https://scikit-learn.org/stable/modules/model_evaluation.html)
- [scikit-learn DBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html)
