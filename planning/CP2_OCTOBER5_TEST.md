# Separate 5 October prospective test

**9 October update:** This protocol remains unchanged and its incomplete raw
collection history is retained. A separately declared timing repair begins on
10 October; see [the new protocol and repair](CP2_OCTOBER10_COLLECTION_REPAIR.md).

Declared and committed on 4 October 2026 at 21:39:20 Malaysia time, before
collection begins. Commit: `ab2accc`. Protocol:
`config/cp2_october5_cohort.json`; SHA256:
`5c7d90df93b048454caf806cf58fad126b023126ce498a2abdb387d512c65034`.

| Date | Work |
|---|---|
| 4 October | Declare protocol, verify access and collector before collection begins |
| 5–27 October | Log timely predictions for every eligible matched paid service |
| Through 26 November | Extract every service's complete 30-day Calendar outcome window |
| 27 November, 13:00 MYT | Separate cloud evaluation task; reject incomplete or altered evidence |
| 28–30 November | Results and write-up if the evaluator succeeds |

Frozen bundle hash remains
`6ace4314b4a5e170ea1bd6feee40dadbdd14eb3c986db9223d888b3c3ee302e0`.
Weights, thresholds, model target and original protocols are unchanged. Separate
result paths are `prospective_october5_evaluation.json` locally and
`evaluations/october5_2026.json` in restricted cloud storage. Original results and
misses remain visible. No historical predictions are backfilled.

The 30-day target starts with the first complete local day after the service's
start date. The existing scorer requires logging within five minutes after
scheduled end and before that next day begins. Overnight services can therefore
fail this unchanged contract. They remain eligible misses; this protocol does
not silently exclude them or guarantee complete coverage/high accuracy.

The new endpoint is `/evaluate-october5`. The separate Scheduler task is
`cp2-prospective-october5-final-20261127`, 13:00 Malaysia time, zero retries,
the existing approved scheduler identity and private service audience. The older
12:00 task remains separate. The evaluation gate rejects early outcomes, missing
or late predictions, changed protocol/model/source hashes and repeat evaluation.

487 Python tests passed, including a new distinct-result/hash-tampering regression.
Image build `81ca4439-3982-446c-a285-041e0543c80d` succeeded. Verification initially
exposed expired Google consent. The owner completed renewal of the same read-only
access; the existing restricted secret now has version 2. Verification execution
`cp2-october5-verification-20261004-fkzsh` succeeded. Revision
`cp2-prospective-collector-00011-4fg` now serves all traffic. A genuine Scheduler
tick returned HTTP 200 at 22:06:04 MYT on 4 October. The durable audit shows
the new cohort not started, zero new-cohort misses, one older cloud-cohort miss,
and 30 raw historical missed windows. Those old misses remain unchanged.

The exact declared protocol was also stored immutably in the restricted collector
bucket at 22:04:54 MYT, with a matching SHA256. Collection runs in the cloud;
the owner's laptop need not remain awake. This verifies operation before the
cohort, not future coverage or model accuracy.
