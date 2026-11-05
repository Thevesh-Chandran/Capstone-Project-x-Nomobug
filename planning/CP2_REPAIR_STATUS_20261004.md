# CP2 repair status — 4 October 2026

This is the current checkpoint; the original project review records the earlier
audit and its findings. The owner is building the dashboard.

| Area | Current evidence |
|---|---|
| Source formulas | 18,594 original formula repairs verified. The inspected 39 service-date helper errors are also resolved using uniquely matched Calendar evidence. |
| Source fact resolution | Owner excluded CUST527 and confirmed CUST1982 fully paid RM520 through Atome. Live SALES now marks the first cancelled and records the second payment once with RM0 remaining. Two remaining exceptions are the original enquiry phone and the refund-needed receipt's sale linkage; neither was invented. |
| Upgraded package | The reviewed 1x plus Upsell 2x programme has two sales, three paid visits and RM640 recorded value. The cloud candidate's programme invariants return zero failures. |
| Reporting release | Latest hosted execution `cp2-reporting-daily-98l6c` published owner-confirmed source release `20261004125916e732f9` in 8m40s after the guarded warehouse build, KPI reconciliation and privacy checks. An independent post-publication query verified CUST527 is excluded, CUST1982 records RM520 once with RM0 remaining, the sales pointer is current and all 47 published view definitions pass the privacy gate. Prior release `202610041128244d18aa` passed all 201 warehouse build/test steps and 16 KPI checks, followed by an independent 16-check rerun in 22 bounded queries (10,967,620 bytes processed). Failed candidates preserve approved views. |
| Cloud collector | Revision `cp2-prospective-collector-00010-gtf` serves 100% of traffic. Three observed Scheduler requests returned HTTP 200. Full source-to-model smoke `20261004T110931Z_29cc2e1f` succeeded with a durable terminal journal. Both old laptop tasks, collection and final evaluation, are disabled; the local installer rejects reinstallation or repair of this retired schedule. The laptop does not need to stay awake for cloud collection. |
| Failure and recovery | Isolated cloud run `20261004T073058Z_875b6450` retained its failed weather-stage journal and prior success pointer, then succeeded on resume. Production state/predictions were not modified by this fixture. Temporary verification jobs were removed. |
| Evaluation safeguards | Final evaluation audits source eligibility and immutable receipt hashes before labels/results. Regression checks reject missing or late predictions, changed refresh artifacts and repeat evaluation. Full audit details stay in restricted storage. |
| Historical model evidence | Research labels reconciled against their own source epoch. Frozen replay reproduces all 5,695 scores, with maximum differences below 3.4e-16. This is integrity evidence, not new accuracy. |
| Python checks | 480 passed for the deployed diagnostics repair; the subsequent local readiness-summary checks brought the complete suite to 486 passed (19 warnings). Frozen bundle hash verification also passed. |
| Billing | CP2 was the only billed project in the inspected report. Reported 1–3 October usage: RM5.99; savings: RM5.99; net: RM0.00. Newer usage is subject to reporting delay. The owner removed the operator spending ceiling. |
| October source capacity | The largest inspected Bronze snapshot family has 15 snapshots against the 64-family limit. Twenty-seven additional daily snapshots would remain within that bound; additional retries still need monitoring. |
| Report access | Existing report is Restricted, with the owner as its only listed user. Intended management viewers still need to be added by the owner. No permissions or report content were changed. |

The original and repaired prospective cohorts remain incomplete. The October
cloud cohort has one preserved missed overnight service window; raw historical
misses remain 30. Waiting until November cannot recover an unlogged prediction.
The evaluator must reject a full-cohort accuracy claim when coverage is incomplete.
October submission can use the historical evaluation plus honest collection evidence.

The frozen model remains experimental: 94% threshold accuracy versus a 95%
always-no-callback baseline on 100 services with only five positives. Its
highest-risk twenty services contained four positives, but this small sample
does not establish reliable operational performance. The programme reporting
repair does not retroactively alter the frozen model's inputs or weights.

Remaining source facts are listed in [CP2_UNRESOLVED_SOURCE_FACTS.md](CP2_UNRESOLVED_SOURCE_FACTS.md).
Programme interpretation is documented in [CP2_SERVICE_PROGRAMME_REPAIR.md](CP2_SERVICE_PROGRAMME_REPAIR.md).
The additional source recheck and explicit model-readiness decision are documented
in [CP2_REMAINING_RESOLUTION_20261004.md](CP2_REMAINING_RESOLUTION_20261004.md).
The dashboard should use the stable approved aggregate sources in
[CP2_DASHBOARD_HANDOFF.md](CP2_DASHBOARD_HANDOFF.md).


## Latest collector checkpoint — 4 October, 22:06 MYT

Google read-only sign-in was renewed and restricted Secret Manager version 2 installed. Candidate cloud verification succeeded; collector revision `00011-4fg` serves 100% of traffic and a genuine two-minute Scheduler tick returned HTTP 200. New cohort: not started, zero misses; older cloud cohort: one miss; raw audit: 30 misses unchanged. Protocol committed and stored immutably before 5 October. See [the separate protocol and dates](CP2_OCTOBER5_TEST.md). All 487 Python checks pass. Model reliability remains experimental; working collection does not establish accuracy. Laptop operation is unnecessary.
