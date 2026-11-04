# Reporting refresh repair — 4 November 2026

## Cause

The daily Cloud Scheduler trigger remained enabled at 06:00 Malaysia time. The reporting job stopped at snapshot retention preflight: `payments_` also matched `payments_date_serials_`. The 32 payment snapshots and 32 date sidecars were incorrectly counted as 64 payment snapshots. Exact source-prefix plus 64-character hash matching fixes the count without conflating the two source families or deleting evidence.

The previous candidate also failed programme reconciliation. A reviewed programme appointment formerly expected on 25 October was absent from the historical extraction. The separately extracted future Calendar contains its 13/24 booking on 14 November. The owner-confirmed programme membership is unchanged; this is a scheduled booking, not proof of attendance.

## Retention review

The bounded limit is now 96 exact snapshots per source family. On 4 November, the largest family had 49 snapshots and all Bronze tables together were below 1 GiB logically. This permits daily collection through 30 November plus manual repair runs while keeping a firm review stop. No retained snapshots were deleted.

The reviewed reschedule evidence, source identities and contract links remain in the private release audit. Future reviewed bookings are excluded from historical visit requirements until their scheduled date; a due reviewed visit missing from its source still fails validation.

## Verification

781 Python tests passed locally. The isolated public source review passed 464 tests (3 optional tests skipped), and both browser interaction checks passed. Two full Cloud Run reporting releases passed reconciliation and published current data. The predictor recovery execution succeeded and exported 230 recent-service rows from the latest approved release. The website reads the 4 November snapshot. Its cache checks the private source bundle every five minutes.

Frozen model bundles, prediction receipts, missed windows and final evaluation schedules are unchanged. The return-risk feature export uses a read-only, hash-pinned reference snapshot and compiled feature queries, with no access to prospective prediction ledger objects through its new artifact-prefix permission.


## Operations

The daily job remains scheduled at 06:00 Malaysia time, with one task, no automatic retry and a 20-minute timeout. It uses hash-pinned feature artifacts from a restricted bucket prefix. Recovery can rerun only the operational predictor export with `python -m scripts.publish_return_risk_predictors --published-release --uri <approved-private-runtime-prefix>`; it requires the latest published release to match the current reporting view and preserves its verified extraction timestamps. It does not record prospective predictions.
