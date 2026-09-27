> Historical v4 evidence, superseded by [the corrected v5 model](../../CP2_CORRECTED_MODEL_CANDIDATES_V5.md). Retained for reproduction; its recommendation, counts and source-refresh blocker are historical.

# CP2 frozen prospective comparison

Frozen on 27 September 2026. This setup is ready for controlled scoring, but is not connected to a live feature feed or scheduled to run. No prospective predictions or final outcomes have been collected.

## Models and data

Both experimental models were refitted on all 5,598 mature paid-service anchors, including 1,975 from 2026. There are 517 recorded 30-day callbacks. The latest training service is 14 August 2026 and its outcome window ends 13 September.

The reference is ExtraTrees depth 6 using the existing weather/environment features. The challenger is Random Forest depth 6 with the previously selected service-stage, pest and history interactions, and double training weight for positive first-service or mixed-pest cases. Model choices, calibrators and thresholds were fixed before this all-history refit. The reference threshold is 0.17 and the challenger threshold is 0.13. These experimental refits do not replace governing v4 or its threshold.

Earlier exploratory results were 108 versus 100 callbacks captured at the same 395-review budget. Those results belong to the earlier models trained without 2026, not these refits. The overall improvement interval included zero, and neither selected model captured first-service callbacks at that budget. The previously inspected 2026 set cannot establish a new independent accuracy claim.

The target remains a recorded corrective Calendar callback within 30 days of a paid service. It is binary; the model emits a numerical risk score. It is not proof of biological recurrence, completed treatment or contractual warranty entitlement. Calendar remains the service-date authority, including the seven owner-resolved cases.

## Fixed test protocol

- Service cohort: 28 September–27 October 2026, Malaysia time.
- Latest inclusive 30-day outcome date: 26 November. Earliest final evaluation: 27 November, with complete Calendar coverage.
- Compare both models on the identical cohort at a global top-20% review budget, plus AUC, average precision, threshold metrics and first-service/mixed-pest segments.
- Keep complete predictor snapshots and both scores before knowing outcomes. Scoring requires timezone-bearing service start/end, prediction and feature-snapshot timestamps. Logs must be written within five minutes of prediction and five minutes after service end; historical backfill is rejected.
- Missing outcomes remain pending. Final evaluation requires explicit Calendar labels, declared complete cohort coverage, matching prediction coverage and mature outcomes. Unknown labels cannot become negatives.
- Do not tune features, weights or thresholds using this cohort. Final results cannot be overwritten through the evaluator.

## Implementation and validation

`scripts/freeze_callback_prospective.py` provides `freeze`, `verify`, `score` and `evaluate`. The private bundle is under ignored `outputs/cp2-v2/prospective_callback_v1/`; future logs are under ignored `outputs/cp2-v2/prospective_callback_logs/`. Its manifest records input, model, replay and feature-code hashes. Keep private artifacts locally; the public config contains aggregate metadata only.

Fresh-process verification reproduced both models' 5,598 training scores to within 3.4e-16 without outcome labels. This verifies reproducibility, not predictive performance. The full suite passed 269 tests, with 19 existing Rasterio warnings. Tests cover missing outcomes, time gates, tampering, immutable logs, complete Calendar labels and final evaluation timing.

The scoring interface still needs a live predictor extractor. Timestamp declarations and hashes detect accidental changes but do not independently prove upstream availability or complete source capture. Previously seen customers may appear in the prospective cohort; it measures future operational services rather than unseen-customer generalization.

## Current source-refresh blocker

A read-only Calendar check for 15 August–27 September failed on 27 September with Google's `invalid_grant` (saved token expired or revoked). No source rows were downloaded and no warehouse or Calendar changes were made. Newer mature records may exist; their absence has not been established.

To restore access, run `.venv\Scripts\python.exe scripts/renew_google_access.py` from the project and complete Google sign-in. Then repeat the read-only Calendar check. Preserve frozen inputs and stable event-ID review mappings before deriving a refreshed candidate dataset. New historical data can support a separately identified retrospective holdout; it must not be backfilled as prospective predictions.
