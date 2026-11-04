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
