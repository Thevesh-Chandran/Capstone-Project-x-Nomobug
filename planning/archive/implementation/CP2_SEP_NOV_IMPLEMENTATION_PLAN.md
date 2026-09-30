> Archived evidence or implementation history. Its dated status and model choices are not current instructions. Start with [the current model guide](../../CP2_START_HERE.md).

# Nomobug CP2: Active Implementation Plan

Paths and commands are relative to the repository root.

Reconciled 3 September 2026. This is a historical schedule; `planning/CP2_SCOPE_AND_DELIVERABLES.md` defines business scope and `planning/CP2_OCTOBER_SUBMISSION.md` tracks the current deadline. The previous plan is preserved at `planning/archive/implementation/cp2_plan_before_zero_cost_revision.md`. CP1 documents and the proposal are unchanged.

Current implementation evidence is in `planning/CP2_OCTOBER_SUBMISSION.md`; earlier checkpoints are in `planning/CP2_PROJECT_HISTORY.md`. The dates below are historical planning targets, including older Neon/Preset/GitHub-scheduled platform references. The selected stack is BigQuery, dbt, Cloud Run Jobs + Scheduler, Looker Studio, GitHub Actions CI, and Neon as manual fallback.

## Working agreement and capacity

### BigQuery migration amendment — 3 September 2026

This amendment supersedes Neon-only and no-card assumptions below, including provider references in daily tasks. BigQuery with `dbt-bigquery` is the primary target; Neon scripts and the verified 32,580-row snapshot stay intact as manual fallback. Billing linkage is acceptable to the user, but the target bill remains $0. No automatic provider switch, paid upgrade or dual-write. Daily business deliverables and deadlines remain unchanged; validate BigQuery authentication, region and cost controls before cloud loading. See `planning/archive/implementation/bigquery_migration.md`. Cloud migration is pending, not complete. The state table below predates the successful Neon load and rerun; current evidence is one verified snapshot, 18.82 MiB database size, and read-only Silver profiling implemented.

- Target $0 usage; no automatic upgrades or trial-dependent deployment. User accepts billing linkage for BigQuery, with residual charge risk explicitly disclosed. Verify actual cost controls before deploying.
- At most 60 minutes of student time daily, including learning and debugging. No hidden four-hour weekends. Dates are latest-finish targets, not instructions to wait: use spare time for the next dependency-ready task.
- Aim for 5 minutes reviewing evidence, 35 implementing, 15 testing/explaining and 5 recording progress. Stop at a safe checkpoint.
- Provide short copyable code with exact paths and plain-language explanations. Prefer linear pandas scripts/cells; introduce reusable functions gradually.
- Every task advances the actual system. Connection checks and synthetic regression tests are validation, not separate practice projects.
- No unrequested commit, push, deletion, account upgrade, live-source edit or customer-data transfer.

The old plan allowed about 14 hours/week; the current maximum is 7. There are at most 89 one-hour sessions from 3 September to 30 November inclusive, and part of today's session is already used. This is a constrained target plan, NOT proof that the original workload fits half the time.

Reuse extraction prototypes, one common loader, dbt views, one predictive model plus a baseline, one DBSCAN experiment and shared dashboard templates. Cover every required business area without assuming ten separately designed pages. Collect report notes and evidence throughout implementation.

Review progress weekly. If measured effort exceeds capacity, name the failed acceptance check immediately, use an earlier finish or named buffer, and seek a scope decision before a deadline is missed. Do not silently move deadlines or remove ML, DBSCAN, privacy or correctness. Poor labels/location coverage, OAuth renewal, free-tier limits and external user availability remain schedule risks.

## Evidence-backed state on 3 September

| Component | Status |
|---|---|
| CP1 | Preserved locally under ignored `docs/`; unchanged by this revision. |
| Google sources | Read-only OAuth/inventory prototypes and historical profiles exist for two workbooks and six calendars. Current access and live structures require rechecking. |
| Python | Student verified Python 3.14.4, pandas 3.0.5, scikit-learn 1.9.0 and database-library imports. |
| dbt | Core 1.12.3 and BigQuery adapter 1.12.0 were verified. PostgreSQL adapter compatibility, installation and `dbt debug` remain pending. |
| Neon | Student created Free project and six schemas; Python returned all six. Region, capacity settings, runtime roles and backup policy still need verification. |
| Extraction | Student renewed Google consent via port 8081 and verified the live `2026` extraction at 2026-09-03 14:41 UTC: 32,580 API/DataFrame rows, 24 source columns, Sheet rows 2–32581, 0 entirely blank rows, 16,847 exact repeats beyond first retained. This is extraction evidence, not proof of customer uniqueness or full data quality. Column completeness output has now been added; student review pending. Eight extractor plus three renewal synthetic tests pass. |
| Pipeline | Live API-to-Neon load, rerun safety and audit logging NOT implemented/tested. |
| Deployment/analytics | GitHub Actions, Preset connection/dashboard, predictive ML and DBSCAN remain planned. |

Historical CSV row counts are not current live counts. An installed package, existing credential or created schema does not prove a working pipeline.

## Active architecture and cost gates

Google Sheets + six Google Calendars + Open-Meteo APIs -> Python/pandas -> Neon PostgreSQL (`bronze`, `silver`, `gold`, `quality`, `audit`, `analytics_ml`) -> Preset Starter.

dbt Core with `dbt-postgres` transforms/tests SQL. scikit-learn produces prediction and clustering outputs. GitHub Actions runs short manual/scheduled batch jobs. Docker packages reproducible local execution; users access the dashboard in a browser.

- Neon Free: published allowance checked 3 September is 0.5 GB/project storage, 100 CU-hours/project/month and 5 GB public transfer. No card needed. Measure table/index/history size; CSV bytes are not a database-size guarantee. Keep one current Bronze representation, bounded logs and protected local backups rather than full daily cloud copies.
- Preset Starter: one workspace and up to five users; verify Starter enrollment rather than a paid trial. Free access controls are limited. Its database login must read approved reporting views only; do not assume free embedding or per-user role separation. User testing can be sequential/supervised within seat limits.
- GitHub Actions: GitHub Free includes 2,000 monthly private-repository minutes. Verify existing billing settings and block paid usage before scheduling. Use standard Linux runners, bounded runtime, no sensitive logs/artifacts and a private execution repository. Public code does not authorize public customer data.
- Scheduled workflows are best-effort, not real-time. Show last successful refresh, support manual/local runs and measure duration before assuming the allowance is sufficient.
- The existing Google project remains for Sheets/Calendar APIs only. BigQuery, Cloud Run, Cloud Scheduler, Secret Manager and Artifact Registry are not active dependencies.
- Free limits may stop service; never upgrade automatically. Keep local backup/restore and offline demonstration paths. Free offerings can change.
- Confirm approved fields, destination/region and access before company-data transfer to Neon/Preset/Actions. Sheets access alone does not settle third-party data-sharing permission.

References: [Neon pricing](https://neon.com/pricing), [Preset pricing](https://preset.io/pricing/), [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

## Source and analytics contracts

- Live APIs are the primary input, not Excel or exported CSV. Local snapshots remain optional ignored debugging/backup artifacts.
- Prospects: `2026` and `B2B FOLLOW UP` only. Repeated phone numbers may be legitimate new enquiries. Exact repeats and template rows need separate flags, not silent deletion.
- SALES supplies commercial details, NOT authoritative service dates. PAYMENTS remains transaction-grain; PAYMENT LINK remains a distinct funnel stage with cautious phone linkage.
- Calendar supplies operational dates; an event alone does not prove service completion. Preserve cancellations, recurrence IDs and timezones; define completed-service eligibility explicitly.
- Warranty/refund operational dates require Calendar matching. Exclude refund bank details from cloud analytics. Commercial Clients/Recurring Payments are derived and must not duplicate SALES revenue.
- Preserve original values, header mapping and Sheet row positions BEFORE filtering. A Sheet row number identifies a row within an extraction, not a permanent customer ID.
- Read every returned row in the approved API range, not every allocated empty grid row. Count internal blanks/templates explicitly; no silent removal from the raw layer.
- Stage/validate before transactional publication; failed extraction must not erase the previous valid state. Record run ID, UTC extraction time, tab, row counts and hashes.
- Predictive work requires target, prediction time, eligibility, leakage-safe split, baseline and held-out evaluation. Poor labels require an explicit feasibility decision, not invented performance or silent removal.
- DBSCAN requires credible coordinates, distance units, coverage and sensitivity evidence. Area-centroid duplication can create artificial clusters. Report this; absent eligible data requires a scope decision, not silent substitution.

## Milestone acceptance gates

| Deadline | Required evidence |
|---|---|
| 6 Sep | Live `2026` -> DataFrame -> approved Bronze slice; counts reconcile, rerun does not multiply rows, failure preserves last success. |
| 13 Sep | All approved Sheets/Calendar sources reach Bronze with mapping, lineage, counts and safe logging. |
| 20 Sep | Core dictionary/Silver contracts, cleaning flags and first exact matching tested. |
| 27 Sep | Matching quality, usable location/weather features and initial Gold views verified. |
| 30 Sep | One command runs API-to-Gold locally with tests, rerun safety, audit logs and limitations. |
| 11 Oct | Manual/scheduled hosted execution, read-only Preset connection and core operational dashboard verified. |
| 18 Oct | Predictive baseline/model, held-out evaluation and traceable outputs complete. |
| 25 Oct | DBSCAN sensitivity, heatmap/map and remaining dashboard areas complete. |
| 31 Oct | Deployment, dashboard, ML, DBSCAN, privacy/recovery evidence; feature freeze. |
| 30 Nov | Evaluated, repaired, documented submission with reproducible/offline demo. |

## Daily target sequence

Every row is at most one hour of student time, not guaranteed completion. Work may start early or span sessions; gates determine progress. Buffers address failed checks, not optional features.

### September — real API pipeline

| Date | Target output/check |
|---|---|
| 1 Sep | Scope and five business questions agreed (historical checkpoint). |
| 2 Sep | Python environment/initial dependencies verified (completed earlier). |
| 3 Sep | Neon connection verified; reconcile plan and inspect existing API code. |
| 4 Sep | Live `2026` DataFrame, Sheet row positions/header map, safe counts and source contract. |
| 5 Sep | Approve cloud fields/access; create Bronze table, transactional first load and run metadata; reconcile counts. |
| 6 Sep | First-slice rerun/failure checks; buffer for repairs. |
| 7 Sep | Reuse extraction/loader for `B2B FOLLOW UP`; distinguish bookings/enquiries. |
| 8 Sep | SALES/PAYMENTS extraction and load with separate grains/counts. |
| 9 Sep | PAYMENT LINK/WARRANTY CLAIM extraction and load; preserve ambiguity. |
| 10 Sep | REFUND load excluding bank fields; derived recurring/commercial tabs kept separate. |
| 11 Sep | Adapt Calendar pagination; six calendars, recurrence/cancellation fields. |
| 12 Sep | Calendar load and finite history/window reconciliation; source mapping. |
| 13 Sep | Bronze gate: counts, failure recovery, capacity and buffer. |
| 14 Sep | Verify/install/pin `dbt-postgres`; private credentials and `dbt debug`. |
| 15 Sep | Shared Silver normalization plus `2026`/B2B flags and tests. |
| 16 Sep | SALES/PAYMENTS/PAYMENT LINK Silver; amounts/customer-key checks. |
| 17 Sep | Warranty/refund/derived-tab Silver; date authority/non-double-counting tests. |
| 18 Sep | Calendar Silver and explicit event categories with unknown fallback. |
| 19 Sep | Exact-ID/phone linkage, candidate counts/ambiguity flags; never name-only matching. |
| 20 Sep | Silver/dictionary gate and buffer; required fields have meaning/grain/authority. |
| 21 Sep | Safe unmatched/ambiguous review; bounded secondary matching only if justified. |
| 22 Sep | Matching coverage/false-match evidence and defensible rule freeze. |
| 23 Sep | Location availability and approved coordinate/privacy approach; spatial feasibility gate. |
| 24 Sep | Cached Open-Meteo enrichment on eligible dates/locations; coverage counts. |
| 25 Sep | Define outcome windows/prediction eligibility; flag weak labels before October. |
| 26 Sep | Gold funnel/finance/service views and manually checked totals. |
| 27 Sep | Gold quality/refresh/weather views; matching/weather gate and buffer. |
| 28 Sep | One pipeline entry point, ordered steps, failures and last-success protection. |
| 29 Sep | Integrated tests and bounded storage/retention; acceptance repairs only. |
| 30 Sep | Live API-to-Gold demonstration/rerun; September evidence and risk review. |

### October — deployment, dashboard and required analytics

| Date | Target output/check |
|---|---|
| 1 Oct | Verify Actions free/billing settings, private execution and unattended Google auth. |
| 2 Oct | Dockerfile/.dockerignore and local run without embedded secrets/data. |
| 3 Oct | Manual Actions run with restricted secrets; counts/logs verified. |
| 4 Oct | Hosted-run buffer; timeouts/concurrency/retry boundaries and fallback. |
| 5 Oct | Scheduled workflow, UTC/Malaysia timing and delayed-run caveat verified. |
| 6 Oct | PostgreSQL reporting role cannot read raw/customer-identifying data. |
| 7 Oct | Preset Starter limits/enrollment and TLS connection to approved Gold views. |
| 8 Oct | KPI denominators, executive charts and last-success indicator reconciled. |
| 9 Oct | Prospects/B2B and finance dashboard sections from shared templates. |
| 10 Oct | Service/warranty/refund and quality sections; filters/totals checked. |
| 11 Oct | Hosted/core-dashboard gate and buffer. |
| 12 Oct | Freeze predictive target, prediction time, cohort and label availability. |
| 13 Oct | Leakage-safe grouped/time-aware split; preprocessing trained on training data only. |
| 14 Oct | Baseline plus one interpretable model; seed/features/run recorded. |
| 15 Oct | Validation threshold/error analysis; no repeated tuning on held-out test data. |
| 16 Oct | Held-out evaluation, class balance and limitations; no forced usefulness claim. |
| 17 Oct | Persist safe prediction/metric outputs and predictive dashboard section. |
| 18 Oct | Predictive gate and buffer; explain target/baseline/results/limitations. |
| 19 Oct | DBSCAN eligible points, window, distance units and privacy. |
| 20 Oct | Parameter rationale from domain scale/neighbour distances. |
| 21 Oct | Bounded sensitivity runs; clusters/noise/coverage recorded. |
| 22 Oct | Stability and centroid/duplicate effects; traceable clustering outputs. |
| 23 Oct | Heatmap/cluster charts; count/geographic-meaning checks. |
| 24 Oct | Weather/recurrence and rule-based recommendations; non-causal wording. |
| 25 Oct | DBSCAN/dashboard gate and buffer; required areas covered. |
| 26 Oct | Controlled pipeline failure and last-success/manual recovery. |
| 27 Oct | Database/model/dashboard backup and restore demonstration. |
| 28 Oct | Privacy review: Actions logs, notebook outputs, credentials/reporting role. |
| 29 Oct | Measure storage/compute/workflow minutes/dashboard speed; no keep-alive polling. |
| 30 Oct | Clean setup/run demonstration; acceptance repairs only. |
| 31 Oct | October gate, evidence capture and feature freeze. |

### November — evaluate, repair and submit

| Date | Target output/check |
|---|---|
| 1 Nov | Freeze features/rank defects; no additional frameworks. |
| 2 Nov | Consolidate test matrix from accumulated evidence. |
| 3 Nov | Extraction/count/rerun regressions. |
| 4 Nov | dbt type/null/relationship/business-rule tests. |
| 5 Nov | Privately trace source-to-dashboard sample; safe findings only. |
| 6 Nov | Independently reconcile KPI/model/clustering results. |
| 7 Nov | Highest-severity correctness repairs/regressions. |
| 8 Nov | Failed-check buffer; otherwise rest. |
| 9 Nov | Full repository/identity/data/log/export privacy review. |
| 10 Nov | Missing column/API failure/invalid-value scenarios preserve last success. |
| 11 Nov | Restore and local fallback rehearsal. |
| 12 Nov | User-test tasks/consent/appointments arranged. |
| 13 Nov | Safe pilot build and expected answers frozen. |
| 14 Nov | First short user-test session; observed feedback recorded. |
| 15 Nov | Additional session or triage; respect Preset account limit. |
| 16 Nov | Highest-value usability repairs. |
| 17 Nov | Labels/filters/definitions/empty states/readability. |
| 18 Nov | Follow-up user/supervisor check; report actual participation. |
| 19 Nov | Consolidate technical/usability evidence. |
| 20 Nov | Architecture/lineage diagrams and safe screenshots. |
| 21 Nov | Reproducibility instructions/comments; README stays a repository overview. |
| 22 Nov | Dictionary/source mapping/limitations finalized. |
| 23 Nov | Evaluation narrative finalized from notes gathered throughout implementation. |
| 24 Nov | Methodology and zero-cost infrastructure deviation; original proposal preserved. |
| 25 Nov | Discussion/recommendations/future work/citation consistency. |
| 26 Nov | Slides and concise demo route. |
| 27 Nov | Timed live/offline rehearsal. |
| 28 Nov | Critical fixes only; final regressions. |
| 29 Nov | Buffer/backups/submission-file checks. |
| 30 Nov | Final submission checklist; commit/tag/push only on explicit request. |

## Immediate next implementation

Run `python scripts/extract_prospects_2026.py` to review the newly added column mapping/completeness summary. Basic live extraction passed; column meanings and required-field decisions remain to be reviewed. The script reuses approved private source IDs, preserves displayed values/original Sheet row positions/header mappings and handles ragged rows/duplicate headers. It prints column labels and aggregate counts, not customer values. No new Google project, CSV dependency or customer-data upload is required during this check.

After inspecting the current API response, agree Bronze fields/privacy, implement transactional loading and pass first-slice count/rerun/failure checks before expanding sources.
