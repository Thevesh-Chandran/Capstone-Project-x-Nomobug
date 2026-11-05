> Current dates amended before collection: **10–30 October**, final evaluation **30 November at 14:00 MYT**. See [finish record](CP2_NOVEMBER30_FINISH.md). The original repair/deployment evidence below remains historical.

# Collection repair declared 9 October 2026

The cloud was running, but the 5 October test had five unacknowledged Calendar
candidate windows. Fresh frozen-feature extraction confirms two overnight
appointments are model anchors; the three daytime appointments are absent from
the eligible frozen predictor population. That fresh check cannot reconstruct
the exact earlier source state. Preserve all five raw windows and timestamps;
do not present the raw candidate count as five confirmed eligible services.

## New test: 10â€“27 October

The immutable protocol is `config/cp2_october10_cohort.json`, hash
`7224062bf8a41110769aa4d2b6d951aec4ccb562d00d6a5631301c4a3684a4d3`.
The model bundle remains
`6ace4314b4a5e170ea1bd6feee40dadbdd14eb3c986db9223d888b3c3ee302e0`.
The outcome remains recorded Calendar callbacks on days 1â€“30 after the scheduled
service **start date**. Neither training, thresholds nor the label clock changes.

Daytime predictions must be committed within five minutes after scheduled end.
Overnight predictions must be committed between 23:45 and 23:50 Malaysia time on
their scheduled start date, before the first outcome day. These use the service
details known then and can precede a service scheduled to start after 23:45.
They predict a planned service, not verified treatment completion. The two-minute
trigger starts preparation shortly before the capture time and checks Calendar
again before writing a source-bound immutable receipt. Future-created source rows
and outcome columns remain unavailable to the predictor query.

New receipts bind the protocol hash and timing policy. The separate one-time
endpoint is `/evaluate-october10`, result `evaluations/october10_2026.json`.
Evaluation on 27 November must reject incomplete prediction/outcome coverage,
changed source eligibility, altered receipts/model/protocol, and repeated results.
Do not pool this evaluation with the original, repaired, 1 October or 5 October
tests. Their protocols and raw audit history remain unchanged and visible.

## Diagnostics and limits

The collector distinguishes eligible anchors from unmatched or ambiguous sales,
package mismatches, duplicate sessions, missing sale dates and exclusions.
Durable watch state preserves decisions and raw missed candidates. Stage journals
include bounded aggregate collection counts and reasons. Non-idle ticks have
immutable audit objects; logs contain only status, counts and exception classes.
Neither source exclusions nor a successful pipeline run count as saved predictions.
Unknown or potentially repairable matching cases require source review.

External outages, late Calendar edits, newly added historical appointments, or
long refreshes can still cause gaps. No software repair guarantees complete
collection. A saved overnight prediction followed by a cancellation, changed slot
or matching revision must pass the existing source eligibility-drift check before
any performance claim. No late prediction can repair an earlier missed window.

## Verification record

Python suite: 496 tests passed. Frozen replay: 5,695 rows reproduced within
3.33e-16 maximum probability difference. See
`outputs/project_audit/20261009/` for real source diagnosis and deployment checks.
Live deployment verified: revision `cp2-prospective-collector-00019-xus` serves
100% of traffic. Image hash:
`aee4554cd53dfe6592c07a03db499cdaf9f1b8e3b57bea2469c85b45f0777ef9`.
Cloud full smoke `20261009T021136Z_78ebdeb7` succeeded with durable terminal stage
journals. Genuine automatic Scheduler ticks succeeded at 10:16 and 10:18 MYT on
9 October, and durable state reports the new cohort as `not_started` with zero
eligible misses. All five earlier candidate timestamps remain preserved; there
are 63 durable older prediction receipts. No future accuracy result exists yet.
The temporary verification job and revision tag were removed after verification.

Fresh source reasons for the three daytime candidates: an unmatched/ambiguous
sale, package/session mismatch, and duplicate paid session. These are source-review
cases; their raw history is retained and no owner fact or link is invented.
The aggregate deployment record is
`outputs/project_audit/20261009/collector_repair_verification.json`.
