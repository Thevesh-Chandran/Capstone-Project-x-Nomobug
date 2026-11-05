# Finish the prospective test by 30 November 2026

Owner-authorized amendment declared 9 October, before the 10 October collection
start. Include eligible services from **10–30 October**. Observe recorded Calendar
callbacks on days 1–30 after each service start date: the last window ends
**29 November**, so complete extraction/evaluation is scheduled for **30 November
at 14:00 Malaysia time**. This is the earliest complete evaluation, subject to
successful collection, source reconciliation and complete outcomes.

Current protocol: `config/cp2_october10_cohort.json`, SHA-256
`1e951e5a112e6c6cd7ef8f3ce3050e5aae151e714c92762cce7b0454396e89a9`.
Prior declaration bytes remain in `protocol_archive/cp2_october10_before_extension.json`
and the existing immutable cloud protocol object. No receipts for this cohort
existed at amendment time. Older protocols, predictions, misses and their
27 November evaluations remain separate and unchanged.

Frozen bundle hash remains
`6ace4314b4a5e170ea1bd6feee40dadbdd14eb3c986db9223d888b3c3ee302e0`.
Weights, thresholds, predictor definitions, target and timing rules are unchanged.
Only this registered precollection amendment can extend the original bundle's
collection dates; legacy evaluation contracts remain restricted to their original
dates. No retrospective scores or guarantees of accuracy are introduced.

The two-minute trigger is restricted to October days 1–30; it does not keep
checking in November. The separate daily reporting refresh remains enabled.
Cloud Scheduler cron expressions recur annually: archive/pause these experiment
entries after the 2026 result review and before next October. No laptop is needed.

Validation: 498 Python tests passed, including last-day collection and rejection
of 31 October anchors. Frozen replay reproduced 5,695 rows with maximum probability
difference 3.61e-16. Cloud deployment and automatic tick evidence is recorded in
`outputs/project_audit/20261009_extension/`.

Live verification completed 9 October: revision `cp2-prospective-collector-00022-pif`
serves 100% of collector traffic. Full source-to-model smoke
`20261009T025046Z_6092f1e3` succeeded. A genuine automatic Scheduler request at
10:54 Malaysia time returned HTTP 200, and its durable tick advanced. Both the
collection and 30 November evaluation schedules are enabled. All 35 prior raw
missed-window timestamps remain unchanged. The superseded 27 November task for
this cohort was replaced; older cohorts' separate tasks remain unchanged.
The temporary smoke-test job and deployment tag were removed.
# Recovery update — 15 October 2026

The original October 10 cohort remains incomplete. A separately declared **16–30 October** recovery cohort uses the same frozen model and existing cloud collection timing. Its one-time evaluation is scheduled for **30 November at 15:00 Malaysia time**, conditional on complete timely predictions and outcomes. See [the protocol and verification record](CP2_COLLECTION_AND_AI_RESOLUTION_20261015.md). Earlier cohort dates and evidence below remain historical; no missed prediction was backfilled.


## After the results: pause the one-time schedules (added 5 November)

Cloud Scheduler repeats these every year. After each has run and its result is saved, pause it so it does not run again in 2027:

```
gcloud scheduler jobs pause cp2-prospective-final-20261127 --location=asia-southeast1
gcloud scheduler jobs pause cp2-prospective-october5-final-20261127 --location=asia-southeast1
gcloud scheduler jobs pause cp2-prospective-october10-final-20261130 --location=asia-southeast1
gcloud scheduler jobs pause cp2-recovery-final-20261130 --location=asia-southeast1
```

`cp2-prospective-every2m` was paused on 5 November (collection ended 30 October). Keep `cp2-reporting-daily-trigger`, `cp2-planning-weekly-trigger` and `cp2-return-risk-monthly-check`: they run the live dashboard and model checks.
