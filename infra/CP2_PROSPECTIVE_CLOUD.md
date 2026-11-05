> Current dates amended before collection: **10–30 October**, final evaluation **30 November at 14:00 MYT**. See [finish record](../planning/CP2_NOVEMBER30_FINISH.md). The original repair/deployment evidence below remains historical.

# CP2 prospective cloud collector

## 9 October collection repair

The separately declared `config/cp2_october10_cohort.json` changes overnight
collection to 23:45â€“23:50 MYT before the existing outcome window starts. It keeps
daytime post-end timing, frozen weights and the start-date-based 30-day target.
New receipts bind this protocol; the old cohorts cannot silently reuse them.
The separate `/evaluate-october10` task is now scheduled for 30 November at 14:00 MYT,
with zero retries and result `evaluations/october10_2026.json`. Pause that annual
entry after its 2026 result is reviewed. See [the repair record](../planning/CP2_OCTOBER10_COLLECTION_REPAIR.md).

Raw Calendar candidate misses and their original timestamps remain visible.
`event_decisions` in durable watch state records current frozen-population reasons.
`october10_cohort_missed_eligible_windows` and
`october10_cohort_unresolved_candidate_windows` distinguish failed eligible
predictions from unresolved source matching. Do not infer complete coverage from
HTTP 200, pipeline success or the eligible-miss count alone: source review and the
final full-population reconciliation are still required. Non-idle tick audits live
under `ticks/`; stage journals now include aggregate collection summaries.

## Latest verified repair â€” 4 October

Revision `cp2-prospective-collector-00010-gtf` serves 100% of traffic. Scheduler
requests returned HTTP 200 and full smoke `20261004T110931Z_29cc2e1f` succeeded.
Stage and terminal run journals are durable in the restricted bucket. Final
evaluation now verifies immutable refresh receipts and audits eligibility drift
before creating labels/results; full customer-linked differences remain private.
The isolated failure/recovery fixture preserved its failed journal and prior
success pointer, then completed on resume. Both temporary verification jobs were
removed. The collector runs independently of the owner's laptop.

Reporting failures now retain bounded dbt check diagnostics in the existing
private BigQuery audit manifest; compiled SQL and raw source rows are excluded.
See [the current repair status](../planning/CP2_REPAIR_STATUS_20261004.md) for
publication status, exact remaining source facts and model limitations. One
October overnight miss remains preserved; these operational repairs do not make
the declared future cohort complete.

The daily `cp2-reporting-daily` job and the time-sensitive model experiment are separate. The private Cloud Run service `cp2-prospective-collector` is called by `cp2-prospective-every2m` in `asia-southeast1`. The local Windows collector remains disabled. The service uses the same frozen v5 bundle and five-minute post-service logging rule. It never backfills a prediction. Its source Google OAuth secret has only read-only Calendar and Sheets scopes. Cloud collection does not require the owner's laptop to stay on.

The collector checks Calendar on each tick. When a paid service is near its scheduled end, it reads fresh Sheets/Calendar data, obtains prior weather, derives predictors in bounded temporary BigQuery queries, rechecks the Calendar event, and writes an immutable private receipt before acknowledging the score. The `audit.prospective_predictions` table is a restricted index of receipt hashes and risk probabilities; the full source-linked receipt is in `gs://profound-keel-500007-s4-cp2-prospective/prospective_logs/`. Neither is a dashboard source. The bucket also holds the exact private model and reference snapshot, checked against `config/cp2_cloud_artifacts.json` and the frozen model registry. The container contains code and public configuration only.

## Verify and recover

**4 October appointment correction:** Sunday is not a placeholder rule. The shared
`calendar_appointment_overrides.csv` review binds only the owner-confirmed temporary
slot to its exact Calendar identity and start/end. Moving it expires the exception.
The collector trigger and temporary live feature input use the same registry; the
feature receipt records its SHA-256. Reporting retains the source event as a
placeholder and excludes it from workload. Existing prediction logs, missed windows
and frozen weights are preserved. See [appointment policy](../planning/CP2_CALENDAR_APPOINTMENT_POLICY.md).

**Prepared local repair, 4 October:** The collector now records bounded, private stage journals under `runs/<run_id>/journal/<sha256>.json`. Each journal contains stage statuses/times, receipt hashes and the original local manifest hash, never raw receipts, customer values, source bodies, credentials or error messages. Writes require a new object generation and use transfer checksums; an existing identical checkpoint is accepted only after a generation-pinned hash check. Each storage request has a ten-second limit and no automatic application retry. A checkpoint is saved before each full-pipeline stage and after terminal success or failure. Failure paths also preserve hydrated collector state before releasing the lease. These changes do not modify frozen predictions, cohort eligibility or missed-window history. They are not live until a new collector image is deployed and its private journal objects are verified.

The journals are recovery evidence, not complete resumable source snapshots. Source rows, weather inputs and predictor files remain private instance-local inputs; immutable prediction receipts retain their existing source linkage. A hard process kill may leave the last `running` checkpoint rather than a terminal failure record. Check Cloud Run logs and the expired lease to distinguish that case. Existing runtime bucket object permissions cover this prefix; no additional IAM role, public access or customer-data publication is required.

**4 October cloud audit:** The two-minute collector was healthy at 11:30 MYT, but its preserved October missed-window count was one. A matched paid appointment starting 2 October at 23:30 MYT ended after midnight at 00:30 on 3 October. Its source/model refresh reached logging at 00:32, but the frozen calendar-day outcome protocol forbids a prediction after the anchor day. Preserve this unscoreable overnight window; it cannot be fixed with a late receipt. The 1â€“27 October protocol remains unchanged, and full prospective accuracy must not be claimed without complete eligible-service evidence.

Check Scheduler state, Cloud Run request status, and `state/last_tick.json` in the private bucket. A healthy idle tick has HTTP 200 and an advancing `checked_at_utc`. `missed_event_windows` is the preserved raw cumulative audit; it must never decrease because a late score was fabricated. `cloud_cohort_missed_event_windows` counts only misses dated 1â€“27 October, so the older incomplete cohorts do not permanently mark the new cohort incomplete. The separate `state/full_smoke.json` confirms a full source-to-model cloud run. A successful idle tick alone does not prove that a real service-end score can meet the five-minute gate.

If refresh or source access fails, pause `cp2-prospective-every2m`, inspect only error types and private run evidence, correct the fault, and manually verify a cloud tick before resuming. The Cloud Storage generation precondition prevents a second receipt for the same anchor. A cross-run lease prevents overlap; a worker terminates itself before 18 minutes, and another worker can recover a lease older than 22 minutes. BigQuery indexing reconciles from durable receipts after a partial failure. A service whose five-minute window expires remains a missed window.

Do not describe a declared cohort as complete until every eligible service has one timely receipt. The original 28 September cohort and the 30 September repaired cohort are incomplete. The overnight test pause left 24 raw missed title windows, including three dated 30 September. The source-to-Gold audit found six of the 24 were `4/3` or `5/3` extra warranty visits; the other 18 were matched within-package services. The raw missed entries and original timestamps remain unchanged. The trigger now excludes future over-package visits. The full source-to-model cloud smoke run `20260929T150804Z_41f31575` succeeded; a scheduled idle tick advanced `state/last_tick.json` at 11:56 MYT on 30 September. The immutable [cloud cohort protocol](../config/cp2_cloud_cohort.json) was declared at 11:55 MYT on 30 September for 1â€“27 October. Preserve both older protocols and their incomplete results. The cloud cohort still depends on every eligible service receiving one timely durable receipt; deployment and an idle tick alone do not prove future coverage. Complete 30-day outcomes and one-time evaluation are available no earlier than 27 November. The October submission uses the historical held-out test and the cloud collection audit, without claiming future accuracy.

At 12:01:33 MYT on 30 September, the collector stored its first real prediction receipt 1.56 minutes after the scheduled service end. Its frozen bundle hash matched, its Calendar event was acknowledged, and the restricted BigQuery index contained the matching row. A second real receipt was indexed at 12:31:43 MYT. Both belong to the already incomplete 30 September cohort, not the 1 October cloud cohort.

At 13:30 MYT, the collector saw two third-service Calendar events. It committed one receipt at 13:31:22, but the other sale also had a confirmed-status `3/3` entry on 14 September. The frozen anchor contract requires one unique event per sale and service number, so it produced no predictor row for the 30 September event. The tick returned HTTP 500 for incomplete logging, and the unlogged event became the **25th raw missed window** at 13:36. The owner confirmed that the 14 September event was cancelled and rescheduled to 30 September; its title begins `CANCELLED` although its Calendar status remains confirmed. The classifier now treats a leading `CANCELLED` or `CANCELED` as cancellation, and the two-minute trigger ignores it. Preserve the missed 30 September window; no late score may be backfilled. The 1â€“27 October cloud-cohort missed count remained zero because this incident preceded its start.

A second 30 September appointment at 16:30 MYT also missed under the old classifier: the same commercial sale had a confirmed-status `CANCELLED GPC 2/12` title on 17 September. This became raw missed window **26**. The corrected classifier covers both cases. The correction is shipped through a new, pin-hash-versioned private artifact prefix, preserving the previous artifact set for rollback; the frozen model bundle is unchanged. Revision `cp2-prospective-collector-00007-jxj` handled scheduled HTTP 200 ticks after deployment. In the frozen 5,695-row training input, nine older anchors have confirmed-status titles beginning `CANCELLED` (all nine negative, dated 2024â€“25); they are a documented source-quality limitation and are not silently removed from the frozen experiment.

Do not promote a collector revision whose compiled Calendar query needs a Gold field before the reporting release publishes that field. Revision `00007` was initially routed before `gold.calendar_warranty_review_overrides` exposed `event_identity_hash`; its 18:00 MYT feature refreshes failed. Three further September windows became raw misses (29 total by 18:12). Traffic was restored to working revision `00006` at 18:07, and Gold remained on its prior approved release. New collector revisions now check the published Gold schema during startup, before serving requests, so an incompatible revision cannot take traffic. After the reporting release publishes, switch to the corrected revision and verify a scheduled tick plus a real service-end receipt.

Recovery completed at 18:56 MYT: reporting release `202609301038259b6f46` published after all 14 KPI reconciliation checks passed. Its candidate review seed had 80 event hashes, while the older stable Gold review table had only five columns. The old table was backed up to `audit.calendar_warranty_review_overrides_backup_20260930`, then its hash column was populated from the approved candidate after verifying all 80 review IDs and labels matched. All 80 hashes now match. Collector revision `cp2-prospective-collector-00008-9xl` is serving 100% of traffic; scheduled ticks and full source-to-model smoke `20260930T105414Z_570a1af5` returned HTTP 200. A real post-repair service was logged at 19:31 MYT, 1.40 minutes after its scheduled end. The guarded reporting release `2026093011124282606c` then published and independently passed all 14 KPI checks. Future reporting releases stop before promotion if the stable review table differs from their candidate seed; reconcile a review change deliberately rather than letting the collector silently use different decisions.

The private `POST /evaluate-cloud` endpoint is reserved for the one-time cloud-cohort evaluation no earlier than 27 November. Scheduler job `cp2-prospective-final-20261127` invokes it at **12:00 MYT on 27 November 2026** with zero retries. It checks full Calendar outcome coverage and prediction receipts before storing a final result at `evaluations/cloud_2026.json`. Inspect its status and the private result; a failed or incomplete evaluation must not be reported as model performance. The Scheduler cron repeats yearly, so pause or delete that job after the 2026 outcome is reviewed.

Cloud Run is private and only the dedicated scheduler identity has `run.invoker`. The collector runtime identity has BigQuery job creation, dataset-level `READER` access on the approved Bronze/Silver/Gold/quality/analytics datasets and every current reporting candidate Silver/Gold dataset, audit dataset write access, bucket object access, and access to the three approved Google source secrets. Its project-wide BigQuery `dataViewer` role was removed on 30 September after the reporting release began granting access to each new candidate **before** view promotion. Full cloud smoke `20260930T044845Z_3d487f25` then succeeded on the newly published views using only dataset-level access; a healthy scheduled tick followed. If future candidate grants fail, the release must stop before promotion. Review [Cloud Run scheduling](https://docs.cloud.google.com/run/docs/triggering/using-scheduler), [request timeout behavior](https://docs.cloud.google.com/run/docs/configuring/request-timeout), and [private bucket access](https://docs.cloud.google.com/storage/docs/public-access-prevention) when changing this deployment.


## Separate 5 October test â€” activated 4 October 2026

Revision `cp2-prospective-collector-00011-4fg` serves all traffic following successful cloud verification and a genuine Scheduler HTTP 200 tick at 22:06 MYT. Approved Google read-only access was renewed using restricted secret version 2. The temporary verification job and revision tag were removed after verification.

`config/cp2_october5_cohort.json` is committed and its exact hash is stored immutably under restricted bucket `protocols/cp2_october5_2026/`. New endpoint `/evaluate-october5` has separate Scheduler job `cp2-prospective-october5-final-20261127`, 27 November 13:00 MYT, zero retries, and separate result `evaluations/october5_2026.json`. The original noon evaluation stays separate. Pause both annual Scheduler entries after their 2026 result is reviewed. See `planning/CP2_OCTOBER5_TEST.md` for dates and unchanged overnight-service timing limitation.
