# CP2 October submission record

**Target submission: 31 October 2026.** The 30-day prospective outcome test is separate. Services in the predeclared 28 September–27 October cohort can have callbacks through 26 November, so the earliest complete-source evaluation is 27 November. The October submission must report collection coverage and the frozen historical result; it must not present a future accuracy estimate that has not been measured.

## Question, method and result

The selected v5 ExtraTrees model estimates the probability of a **recorded corrective Calendar callback in days 1–30 after a matched paid service**. The target is binary. A callback is an operational record, not proof of biological pest recurrence, completed treatment, or warranty entitlement. Residential and commercial services can both have callback labels even though commercial clients have no contractual warranty.

Development selection used purged walk-forward 2025 folds. The selected depth-10 ExtraTrees contract was frozen before evaluation on 100 services dated 15–27 August 2026. Five service windows had a recorded callback. At a fixed 20-service review capacity, the selected model found four of five versus three of five for the corrected reference. ROC AUC was 0.8905 versus 0.8126; average precision was 0.3051 versus 0.2723. A no-callback-only prediction would have scored 95% raw accuracy on this imbalanced set while finding zero callbacks, so raw accuracy is not the decision metric. The paired intervals include no improvement, and the positive sample is too small to establish a dependable gain. Previously inspected 2026 data show a first-service blind spot. The frozen future refit uses 5,695 mature anchors, including 2,075 from 2026; its training scores are not evaluation evidence. See [the full model report](CP2_CORRECTED_MODEL_CANDIDATES_V5.md).

## Data and architecture

The reporting path reads approved Sheets and six Calendars with read-only OAuth, saves immutable Bronze snapshots, builds candidate Silver/Gold datasets with dbt, independently reconciles source rows and monthly business KPIs, and promotes stable reporting views only after validation. An audit table records runs and their last successful release; failures retain the previous published view definitions. Gold views supply the restricted management dashboard. A separate local two-minute collector logs predictions within five minutes of a scheduled Calendar service end, using the frozen bundle; the daily reporting batch does not replace that timing-sensitive experiment. [Reporting runbook](../infra/README.md) and [prospective operations](CP2_LIVE_PIPELINE_OPERATIONS.md).

The 28 September fresh release `20260928081442aba7ea` is published. All 180 dbt nodes passed, the independent KPI check returned `pass_with_business_caveats`, and 41 stable view pointers were promoted. The first cloud execution then failed on a scoped BigQuery `quality` write permission, leaving those Gold pointers intact. After a dataset-level grant, manual Cloud Run execution `cp2-reporting-daily-7jfzx` completed successfully in 8m17s and published release `20260928134056afeb07`. Its audit row is `PUBLISHED` and the checked Gold dashboard view points to the new candidate dataset. The published release is source-backed, but a Calendar entry remains a scheduled/recorded visit, SALES value remains package face value, PAYMENTS remain sheet entries, formal claims remain separate from callback signals, and source dates or amounts can be missing or inferred. The reviewed 1x plus Upsell 2x episode and `4/3` warranty examples are covered by the business checks; neither a Calendar title nor a package flag alone decides contractual entitlement.

The dashboard is a management artifact, not a customer risk list. It should show denominators, freshness, weather/location coverage, DBSCAN radius sensitivity, and aggregate held-out model evidence. Weather, waterways, land cover and flood context were evaluated as observational predictors; geographic clustering and rainfall associations are not causal effects. Individual experimental probabilities must not be shared in the report.

## Acceptance ledger

| Check | Evidence / current state |
|---|---|
| Fresh source → candidate build → independent reconciliation → publish | Passed on 28 September; release ID above |
| Python/dbt CI and container smoke | GitHub CI passed for the deploy revision; local full Python suite passed 376 tests; Linux image build and CLI smoke passed |
| Frozen model replay | Passed again on 29 September for all 5,695 current-bundle scores; maximum probability difference below 3.9e-16 |
| Manual cloud job | Passed: execution `cp2-reporting-daily-7jfzx` completed; audit release `20260928134056afeb07` is `PUBLISHED` |
| 06:00 MYT scheduled cloud job | Passed: Scheduler-triggered execution `cp2-reporting-daily-wkh6q` started at 06:00 MYT on 29 September and published audit release `202609282200221fcb3a` |
| Deliberate cloud failure and recovery | Passed: execution-only invalid token path caused `cp2-reporting-daily-wrwbl` to fail; Gold stayed on release `202609282200221fcb3a`, and the persistent job configuration retained the correct token path. Normal retry `cp2-reporting-daily-8bkhh` completed and published audit release `20260929013202b88add`; the checked Gold view points to it. The earlier real IAM failure also preserved prior Gold and recovered. |
| Dashboard totals, filters, privacy, viewer access and narrow-screen rendering | Owner is finishing the dashboard; pending final checks |
| Prospective collection | Local collector installed; report logged predictions and missed windows from its immutable operational records at submission |
| Project cost below RM 30/month operator ceiling | Billing Reports showed MYR0.00 posted September cost through 28 September when checked on 29 September; the report showed RM0.11 Cloud Run usage offset by savings. Posting can lag, so this is not a cap or a current-day total. Recheck before each deployment and while the schedule runs. |

As of the 29 September 01:22 UTC collector tick, **zero prospective predictions** were committed and **eight service windows** were marked missed; no new misses occurred in that tick. The PC was not recording ticks overnight, consistent with the local signed-in/awake dependency. This is incomplete collection evidence, not a future accuracy result. The missed windows cannot be backfilled as prospective scores. Reassess collection at submission and, if full-cohort coverage is impossible, state that the 27 November full-cohort test is blocked and predeclare a new cohort rather than relabel a retrospective test as prospective.

## Remaining before 31 October

1. Recheck current source-to-Gold reconciliation and owner examples after the final release. Confirm dashboard totals, filters, privacy, viewer permissions, and narrow-screen use with the owner.
2. Run the final Python/dbt suites, frozen replay and container smoke against the submission revision. Record the actual prospective log and missed-window counts, latest cost observation, and any unresolved blockers.
3. Deploy the source-exit audit fix from the reviewed revision, verify its image/configuration, and recheck current spending. Keep monitoring daily runs through October.

The 29 September local verification initially rejected byte hashes after Git converted frozen Python and SQL sources to Windows CRLF. The byte-identical LF contents replayed the unchanged model. Repository line-ending attributes now preserve LF for the exact hashed files. A separate post-freeze production anchor-macro optimization has an explicit current-source hash in the live feature pin; the frozen compiled SQL pin remains exact. The live feature guard still rejects arbitrary macro or compiled-SQL changes. The model bundle and its 30-day target were not changed.

The deliberate missing-token execution exposed an audit edge case: a Google source reader exits with `SystemExit`, which the release runner did not previously classify as a failed run. The failed Cloud Run execution and unchanged Gold pointer were verified, then its stranded `STARTED` audit record was reconciled to `FAILED` from that execution evidence. The runner now audits source `SystemExit` failures directly; a regression test covers this path. No source data or model artifact was changed by the fault injection.
