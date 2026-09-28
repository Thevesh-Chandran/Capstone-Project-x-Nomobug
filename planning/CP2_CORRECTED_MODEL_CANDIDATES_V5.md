# Corrected callback model comparison v5

The refreshed source corrects future-created, backdated records entering regional history. This experiment then compares 14 fixed model contracts using only purged 2025 development folds. The primary candidate is `et10_leaf5`; the predeclared review-capacity candidate is `policy_et6`. Their selections were saved before diagnostic scoring and before the new late-August holdout was accessed.

This is a model of a **recorded corrective Calendar callback within 30 days of a paid service**, a binary target with probability output. It does not establish biological pest recurrence, service completion, or contractual entitlement. Raw accuracy is misleading because 90.9% of the old 2026 diagnostic anchors are negative.

## Source and separation

The corrected, sanitized input contains 5,595 anchors and 516 recorded callbacks. Its SHA-256 is `6a8aff583eb7a067473198bbe07b56b38b2dceb8751a074f0e16f5e64ac6ab22`. Calendar is the service-date authority. No label edit was made by this experiment.

All old 2026 connected package/property components are removed before development selection, calibration and diagnostic fitting. The resulting pre-2026 training pool has 3,048 anchors and 289 callbacks. The three walk-forward validation periods are 2025 Q2, Q3 and Q4, with a completed-outcome embargo and further component purging at each split. Calibration and alert thresholds use only the resulting pre-2026 out-of-fold predictions. Calibrated development Brier scores would be in-sample for calibration and are not presented as independent results.

The primary selection maximizes mean development average precision (AP), with mean review recall and AUC as tie breaks. The secondary selection maximizes mean recall in a global top-20% review budget, subject to mean AP at least the reference. All cutoff ties stay in the review batch and their count is reported.

## Fixed model and feature ablations

The bounded pool includes the retained ExtraTrees control, weighted RandomForest control, deeper regularized forests, HistGradientBoosting, four CatBoost contracts, two fixed equal-weight ensembles, and two matched policy-feature ExtraTrees contracts. Candidate parameters are fixed in source; no new holdout result tunes them. Thread counts are bounded using existing dependencies.

`policy_et6` adds one deterministic predictor to the same numeric/categorical inputs as `targeted_et6`: recognized contractual eligibility at the paid anchor. It is one for residential 3x after the third paid service and residential 4x/6x/12x during paid services. It is zero for commercial and 1x. Pest type never enters this rule. Counts outside the named policy are not recognized eligible by this indicator; it is not an entitlement decision. Commercial corrective callbacks remain valid target outcomes and their probabilities are not forced to zero. No future scheduled last-service date is used.

| Candidate | Mean 2025 AP | Mean global20 recall |
|---|---:|---:|
| et10_leaf5 | 0.2407 | 51.9% |
| policy_et6 | 0.2378 | 54.4% |
| hist3_balanced | 0.2341 | 42.4% |
| blend_et_cat | 0.2313 | 41.2% |
| targeted_et6 | 0.2297 | 51.7% |
| rf6_leaf20 | 0.2297 | 43.1% |
| blend_et_rf | 0.2277 | 45.0% |
| reference_et6 | 0.2246 | 44.1% |
| rf10_leaf5 | 0.2229 | 39.8% |
| focus_rf6 | 0.2228 | 43.7% |
| cat4_balanced | 0.2223 | 39.2% |
| cat4_plain | 0.2193 | 41.1% |
| cat6_plain | 0.2179 | 41.6% |
| cat6_balanced | 0.2147 | 38.1% |

The policy flag improves mean development AP from 0.2297 to 0.2378 and mean review recall from 51.7% to 54.4% against its matched targeted ExtraTrees control. The stronger ExtraTrees candidate reaches AP 0.2407, against 0.2246 for the corrected reference.

## Previously inspected 2026 diagnostic

All three frozen diagnostic models score the same 1,975 anchors and 179 callbacks. The review batch is 395 anchors for each model.

| Model role | ROC AUC | AP | Callbacks found at 395 reviews | Review precision | Mixed-pest found | First-service found |
|---|---:|---:|---:|---:|---:|---:|
| reference (reference_et6) | 0.7742 | 0.2474 | 97 / 179 | 24.6% | 0 / 20 | 0 / 11 |
| selected_ap (et10_leaf5) | 0.7872 | 0.2319 | 103 / 179 | 26.1% | 1 / 20 | 0 / 11 |
| selected_priority (policy_et6) | 0.7906 | 0.2479 | 105 / 179 | 26.6% | 6 / 20 | 0 / 11 |

The secondary policy candidate finds eight more callbacks than the corrected reference at the same review count, and captures six mixed-pest callbacks. It still misses every first-service callback. The primary candidate improves review capture but has lower diagnostic AP than the reference. Therefore the experiment does not establish a universally better model.

Paired connected-component resampling uses 763 components and 300 repeats, with explicit key alignment. For the secondary policy candidate minus reference, the 95% interval for AP is approximately [-0.0316, 0.0254], and the review-recall interval is [0.0000, 0.0960]. For the primary candidate, the AP interval is [-0.0489, 0.0134] and review-recall interval [-0.0113, 0.0692]. These intervals do not establish a reliable general AP gain. This 2026 cohort was previously inspected and some feature ideas were motivated by its errors; these results are exploratory.

## Scoring artifacts

Each role has three separate artifacts under `outputs/cp2-v2/model_corrected_v5/<role>/`:

- `diagnostic_model.joblib`: purged pre-2026 fitting for the old diagnostic.
- `historical_model.joblib`: fitting on 5,333 anchors and 492 callbacks whose outcomes end before 15 August 2026. Its latest anchor is 15 July and latest outcome end is 14 August. This is the artifact for the separately held late-August operational evaluation, where returning customers are allowed.
- `all_mature_model.joblib`: fitting on all 5,595 completed anchors, including 2026, for future services after this refit. It must not be described as a prediction made on historical August anchors whose later training outcomes were not yet available.

All-history fitting keeps the selected model contract, calibrator and threshold fixed. Its training predictions are not treated as accuracy evidence. The three roles are `reference`, `selected_ap` and `selected_priority`.

Use `predict_artifact(artifact, raw_predictor_frame)` from `scripts/compare_callback_candidates_v2.py`, or the `--score-model`, `--score-json` and `--score-output` CLI arguments. Scoring requires predictor columns and identifiers, drops any supplied target, and returns key-aligned probabilities. Unknown future outcomes are not manufactured as negatives. Customer-level inputs, models and predictions remain ignored private outputs.

The new late-August holdout is evaluated separately by the root workflow. This experiment never reads those holdout outcomes and makes no fresh-accuracy claim from them.

## Verification

Twelve focused tests pass: model probability mixtures, feature-contract enforcement, outcome-free inference, component reservation, maturity cutoffs, selection guards and the owner-policy matrix. All three serialized diagnostic artifacts replay 1,975 predictions in fresh processes, with maximum probability differences below 3.1e-16. Aggregate evidence and artifact hashes are recorded in `config/warranty_model_experiment_v5.json`.


## New later-date evaluation

The model choices above were frozen before accessing the newer outcomes. All three historical artifacts used 5,333 training services with outcomes complete by 14 August. The same new 100 services from 15–27 August have five callback-positive service windows; their outcomes were fully covered through 26 September. This is a retrospective evaluation of later operational services, including returning customers. It is not a replay of predictions actually logged in August.

| Model | AUC | AP | Positive windows found at 20 reviews | Review precision |
|---|---:|---:|---:|---:|
| Corrected reference ET6 | 0.8126 | 0.2723 | 3 / 5 | 15% |
| Primary ET10 | 0.8905 | 0.3051 | 4 / 5 | 20% |
| Secondary policy ET6 | 0.8863 | 0.3948 | 3 / 5 | 15% |

Primary selection remains ET10, chosen from development AP before this test. The policy model's higher new-test AP does not cause a post-test switch. At the frozen 0.19 threshold ET10 predicts five alerts, finds two positives, and has 94% accuracy. Always predicting no callback scores 95% accuracy but finds none; raw accuracy alone is an unsuitable success criterion. The global review budget instead captures four positive service windows in twenty reviews. These are service windows, not necessarily distinct clients or biological recurrences.

Only five positives and 94 connected components are available. Paired component bootstrap (300 requested, 299 valid repeats) gives primary-minus-reference AUC interval [-0.0084, 0.2306], AP [-0.1868, 0.2379], and budget recall [0.0, 0.91]. The intervals are wide and include no improvement; a reliable win is not established. No first-service positives occur in this new test, so it cannot resolve the earlier first-service failure. The larger earlier 2026 diagnostic still misses all eleven first-service positives. Aggregate final evidence is in `config/warranty_new_holdout_v5.json`; the evaluator refuses to overwrite this final result.

## Correctness repairs and source refresh

The read-only refresh retrieved 11,486 rows across the six approved Calendars. Against the old 11,214-row snapshot it found 476 new IDs, 204 absent IDs, and ten changes to substantive service fields (89 entries changed when creation/update metadata is also counted). Absence is not treated as proof of a deleted service. Stable old IDs retain reviewed-label links. Seven changed description/location entries lose inherited geocodes. No Calendar or Sheets edits or production source-pin changes were made.

The shared history feature macro now rejects entries created after the anchor service end. Audit found impossible availability in 389 pre-2026 and 109 old-2026 anchors, mostly regional history. Candidate feature reconstruction changes 239 area-claim and 266 area-service counts; these overlapping counts also reflect the refreshed source. The common historical labels remain unchanged; three old anchors drop out under refreshed eligibility and source evidence. The old snapshot's ten August-14 negative anchors had outcome windows ending on its partial extraction day; the fresh read confirms their labels. Production maturity now comes from source metadata and stops on the last fully covered day, rather than using future scheduled appointments as evidence of follow-up coverage.

Paired evaluation explicitly aligns scores, outcomes and components by service key. A reproduced row-order bug could otherwise reverse uncertainty estimates for shuffled prediction logs. Equality-based package/property/area joins plus deduplication replace a slow OR join while preserving counts; executable equivalence tests cover both targets. Regional histories still use a fixed geohash-area proxy, not a claim that changing dashboard radius improves accuracy.

The private corrected input was derived with temporary BigQuery session tables. Every statement kept the 100 MiB guard; the successful eight-stage derivation processed about 50.6 MB in total (billing minima are larger). Failed schema/billing attempts and a timed-out OR join were not labeled passes; the slow query was cancelled and its session ended. Exact SQL, parameters/source snapshots and executed job IDs remain in ignored `outputs/cp2-v2/source_refresh_20260927/`. The session mechanism follows [Google's BigQuery documentation](https://docs.cloud.google.com/bigquery/docs/sessions).

Creation timestamps prove when entries existed, but older edited classifications, sales fields and location text cannot all be reconstructed without historical revisions. Corrected retrospective results therefore remain distinct from future predictions logged when a service actually ends.

## One current model entry point

`config/cp2_model_current.json` points to the primary corrected v5 candidate. Run:

```powershell
.\.venv\Scripts\python.exe scripts\cp2_model.py status
.\.venv\Scripts\python.exe scripts\cp2_model.py verify
```

`predict --input-json <private predictors> --output-csv outputs/<private scores>.csv` generates risk scores and explicitly drops supplied outcome labels. It does not measure accuracy or register prospective evidence. `log-prospective` retains the strict timing gates; `evaluate-prospective` waits for complete Calendar labels. All customer-level inputs and outputs stay private.

The separate corrected v2 future bundle now trains on all **5,695 mature services, including 2,075 from 2026**, with 521 positive windows. It refits the fixed models after the later-date evaluation; no hyperparameters, weights, calibrators or thresholds change in response to that result. Its latest training service is 27 August and outcome end 26 September. Model files are under `outputs/cp2-v2/prospective_callback_v2/`; the primary file is `challenger_all_history.joblib`. Three fresh-process predictor-only replays match all 5,695 scores within 3.4e-16, and the public config records artifact hashes. Training replay is reproducibility evidence, not accuracy.

The next prospective service cohort remains 28 September–27 October, with final evaluation no earlier than 27 November and complete coverage required. A local read-only Sheets/Calendar-to-temporary-BigQuery feature feed and two-minute prospective collector are now connected; its first checked run produced 205 private recent-service scores but no qualifying just-ended service to log. The collector depends on the signed-in computer remaining awake and connected. These operational scores do not add future accuracy evidence. Earlier v4 and v1 artifacts remain historical evidence rather than the current model recommendation.

## File cleanup

Twenty-two historical documents and the old start guide are archived under `planning/archive/`. Dashboard work is under `planning/deferred/`. The current model guide, configuration map and command index now lead to this report and one model entry point. No byte-identical documentation/configuration duplicates were found. Unique evidence, original source data, credentials and governed model contracts remain available for reproduction. Four old synthetic test-cache directories were left intact because automatic approval review blocked deletion; an empty old archive directory also remained after Windows denied removal.


Final verification: the optimized production macros compile, and a fresh source replay matches all 5,695 keys, labels and history counts. One rain-trend float varies by 8.9e-16 under distributed aggregation; the verifier permits only float noise up to 1e-12 and still rejects changed labels, counts or material predictors. Three serialized current models replay all 5,695 predictor-only scores. The full test suite passed 312 tests with 19 existing Rasterio warnings. Final Markdown verification found no broken local links.
