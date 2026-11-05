# CP2 verification — 17 October 2026

## Verified current operation

At 23:31 Malaysia time, collector revision `cp2-prospective-collector-00017-wgg` had a scheduled tick at 23:30:10, checking 30 Calendar events. The latest full pipeline run completed successfully at 23:01:35. The two-minute Scheduler was enabled. These facts establish recent operation, not complete cohort coverage.

The recovery audit reported zero confirmed eligible missed predictions and **three unresolved candidate windows**. Its status is `requires_source_review`. Older incomplete cohorts and missed windows remain visible. The recovery evaluation Scheduler is enabled for **30 November at 15:00 Malaysia time**; passing complete-population and outcome gates remains necessary. No evaluation was triggered early.

The latest daily reporting execution `cp2-reporting-daily-5sx2t` succeeded, finishing at 12:23 Malaysia time. This verifies execution success; it does not replace the recorded release-level dbt/KPI evidence.

## Website verification

Portal revision `cp2-portal-00041-ln8` is ready. Its restricted runtime snapshots were downloaded without changing publication. Real-snapshot local HTTP acceptance passed for release `cp2r_20261017041003b1d038`, fetched at 17:19 Malaysia time:

- Unauthenticated private API requests are rejected.
- Customer lookup preserves the verified 4+20 programme link and handles no-match results.
- All 39 payment contracts and known paid/balance amounts reconcile to the exact snapshot.
- Date-filtered area sales totals reconcile; increasing radius preserves geographic inclusion (11 sale rows within 5 km and 249 within 20 km at the tested centre).
- Invalid date periods are rejected; planning endpoints suppress individual probability fields.
- Map records reconcile to the release and omit names, contacts and raw individual probabilities from their map payload.

The focused website suite passed 47 tests. The full Python suite then passed **632 tests**, with 19 existing rasterio deprecation warnings. The deployed Models & research page visibly loaded its model cards and reported connected business data and Ollama. Moving to Payment follow-up exposed an expired staff session. The owner was asked to sign in again. **Current authenticated browser checks for customer interactions, payment filters, map interaction and live assistant answers remain pending.** Local API acceptance is not represented as full hosted browser verification.

## Modelling completion

The 40-case outcome audit, larger historical assessment, Calendar-note comparison and source testing are complete and linked from START_HERE.md. No dependable replacement has emerged. The model remains experimental, with a separate governed prospective evaluation still pending.

## Remaining acceptance

1. Resolve the three recovery candidate windows from source evidence; never reinterpret a late prediction as timely.
2. Complete the authenticated live website flow after staff sign-in. Review AI factual correctness and latency using business questions.
3. Dashboard completion remains with the owner.
4. Record current project spending and final release reconciliation near submission; no current spend total was verified in this pass.
5. Finish the final demonstration and prospective outcome evaluation, or explicitly report an incompleteness failure.

Evidence: `outputs/project_audit/20261017_acceptance/`. Customer-linked runtime/state files are private. This pass did not change source records, access permissions, frozen model weights or collection timing.

## Recovery candidate detail

The durable event keys were matched to the archived 16 October Calendar event identities. The three candidates are Client M (duplicate paid-session numbering), Hotel client H (no paid-sale match), and Learning-centre client (duplicate paid-session numbering). Existing owner facts already explain that Client M is a normal second service and Metro was free. Those facts are recorded in CP2_OWNER_REVIEW.md; no repeat owner question is needed. Their integration with the frozen identity/eligibility protocol is still unresolved and must be documented rather than used to fabricate timely predictions. DC3 requires an internal sequence/contract evidence check before any classification decision.
