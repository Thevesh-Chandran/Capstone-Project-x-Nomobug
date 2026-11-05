# Remaining issues: resolution and evidence limits

4 October 2026. Dashboard construction and viewer setup are outside this repair.

The deployed source/reporting/collector repairs are verified in
[the repair record](CP2_REPAIR_STATUS_20261004.md). The further source search
initially did not establish the two missing financial amounts, the original enquiry
phone, or a sale link for the refund-needed receipt. The owner subsequently resolved
the financial cases: exclude CUST527 and record CUST1982 fully paid RM520 through
Atome, once. Live source readback confirmed both corrections and RM0 remaining
for CUST1982. Only the phone and refund-needed receipt linkage remain explicit
quality exceptions. Their absence does not produce invented money.
See [the source evidence disposition](CP2_UNRESOLVED_SOURCE_FACTS.md).

## Model decision

Retain the frozen v5 experiment. The prior declared comparison tested 37 model
and feature contracts; no replacement met its selection rules. Repeating a search
against already inspected tests cannot establish a new independent improvement.
The existing 100-service test has only five positives and 94% threshold accuracy,
below its 95% always-no-callback baseline. Its useful-looking ranking result,
four positives among twenty reviews, remains a small-sample result. The separate
13-service later test missed its one positive at the declared review budget.

A new read-only readiness command verifies the existing bundle hash and reports
these limitations explicitly:

```powershell
.\.venv\Scripts\python.exe scripts/cp2_model.py readiness
```

The report is an evidence summary, not a new approval mechanism. It never grants
operational approval from accuracy alone or from a successful collector run.
Invalid/missing accuracy values stay unknown. It does not change the frozen
weights, threshold, protocols, prediction receipts or cloud scoring behavior.

## Missed future prediction

The October overnight miss remains in the declared cohort. The evaluator rejects
missing/late predictions; it must not present a full-cohort performance result.
Neither a later extraction nor a backdated score can recover that observation.
The cloud continues collecting valid future receipts without needing the laptop.
No replacement cohort, selective removal, backfill or new training was created.
The November date allows outcomes to mature; it does not fix incomplete coverage.

## What would supply genuinely new evidence

The two financial cases are resolved. Staff can restore the actual enquiry
phone from its original enquiry, and determine whether the refund-needed receipt
has a sale reference. The implemented structured service/callback templates can
collect actual inspection and treatment evidence for future model development.
They are not connected to frozen-model training and unknown observations remain
unknown. A future model needs a declared evaluation on fresh independent evidence;
the current model cannot be labelled reliable solely to close a project checklist.
