# Main model review — 28 October 2026

## Current findings

The main model remains the frozen 93-input Extra Trees model predicting a recorded pest-related return within 30 days of a paid service. No weights, thresholds, target, frozen protocol or prediction timestamps were changed in this review.

The final Python suite passed 682 tests, including calibration and deadline checks. The 20 existing rasterio deprecation warnings remain.

## Reporting repair

The 27 and 28 October daily reporting jobs failed their candidate validation; the previous approved Gold views remained published. The durable audit identified two failures in `service_programme_upgrade_invariants`.

The same confirmed Calendar event for CONTRACT_0002 stage 13/24 moved from 18 to 25 October. Event identity, session numbering, sale match and non-warranty classification were unchanged. The reporting seed's expected date was updated to the current Calendar date. This describes a recorded appointment, not proof of completed treatment. Original failed-run evidence remains in the audit.

Reporting image `release:9f0ce32d-836c-4616-a15d-5d6e84681349` built successfully and passed its container smoke check; the daily Cloud Run job was updated to it. The source-pinned candidate passed all 222 dbt build/test steps and all 16 independent KPI reconciliations, then published 53 views and its website export. The recovered release is `cp2r_20261027220023217d5b`, sourced from the 28 October morning extraction. The next natural scheduled run of the updated image has not yet been observed. Recovery receipts are under `outputs/project_audit/20261028_main_model` and the corresponding reporting-release folder.

## Collection completeness

At the inspected tick, `2026-10-28T15:34:12Z` (23:34 Malaysia time), the recovery cohort reported 24 missed eligible windows and 13 unresolved candidate windows. These are the collector's original classifications, not newly owner-adjudicated source facts. The cohort is incomplete. The full-cohort evaluator must refuse a complete prospective accuracy claim unless its declared completeness gates genuinely pass; later scoring cannot repair late or missing predictions.

The recent 26–28 October journal sample contains 36 successful pipeline runs and one abandoned/incomplete journal. Successful runs do not prove that every service was captured on time. The inspected last successful refresh finished 28 October at 18:46 Malaysia time, with one newly logged prediction. No missed windows or classifications were deleted or backfilled. More forensic/source review is required to attribute every gap; this review does not claim to have eliminated all future misses.

The abandoned run stopped in feature derivation. Timely runs now reserve 45 seconds of the existing five-minute gate for scoring/commitment, cap each feature-query wait at 60 seconds or the remaining budget, cancel stalled queries and bound cleanup calls. Expired work raises a recorded timeout rather than extending the protocol. Non-collection replay retains its original timeout. This changes execution control, not feature formulas, fitted weights, labels or valid prediction timing. Revision `cp2-prospective-collector-00017-wgg` serves 100% traffic. An authenticated post-deployment tick at `2026-10-28T15:56:34Z` returned HTTP 200/idle, zero newly missed windows and the unchanged incomplete-cohort counters. A future due-window stall/recovery on this revision has not yet been observed; an idle check is not proof that no future misses can occur.

## Probability calibration experiment

Five declared methods used existing out-of-fold main-model scores. Calibration training used 500 earlier matured service windows, with property groups excluded from Q3 validation. Q3 contained 772 windows. Calibration was refitted on 1,334 earlier matured windows, excluding Q4 property groups; Q4 contained 410 windows and 81 positive returns.

The method and threshold were selected on Q3 before computing Q4 metrics. These periods have been examined in prior studies; this is a historical diagnostic, not a new independent final test.

| Q4 metric | Raw-score reference, validation-selected threshold | Logit calibration, validation-selected threshold |
|---|---:|---:|
| Accuracy | 67.1% | 49.8% |
| Precision | 31.5% | 26.6% |
| Recall | 56.8% | 87.7% |
| Brier probability error, lower is better | 0.1959 | 0.1623 |
| False alerts | 100 | 196 |

Calibration reduced probability error but worsened precision and accuracy at the chosen threshold. It failed the declared exploratory promotion gate and was not deployed. These metrics use different records from the original 100-service result and must not replace or be mixed with that result.

Original historical reference remains 94% accuracy, 40% precision and 40% recall on 100 services with five positive returns, against 95% always-no-return accuracy. The new study does not demonstrate a better operational replacement.

## Current work priorities

1. Verify successful reporting recovery and the next scheduled run.
2. Preserve and explain collection gaps; investigate current unmatched/changed service facts without rewriting historical predictions.
3. Retain the frozen reference and report uncertainty. Do not repeatedly choose thresholds from the same assessment period and present the result as independent accuracy.
4. Treat verified labels and as-of source availability as the remaining modelling priority. More downloaded inputs alone are not evidence of improvement.

Study code: `scripts/test_return_probability_calibration.py`. Notebook: `notebooks/08_Probability_Calibration.ipynb`. Full protocol and results: `outputs/model_validation/20261028_probability_calibration`.
