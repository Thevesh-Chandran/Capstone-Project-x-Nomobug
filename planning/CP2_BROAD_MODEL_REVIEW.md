# Broad model improvement review — 1 October 2026

**Decision: retain v5 for the frozen experiment.** Thirty-seven declared model/ensemble contracts were compared. None improved mean development average precision (AP) and callback capture at the same review capacity together. This establishes the result of this bounded search, not that v5 is the best possible model or that its accuracy is dependable.

## What was completed

The [protocol](../config/cp2_broad_challenger_v1.json) and code were committed before the search. The pool contains 33 fitted models and four fixed mixtures: ExtraTrees and RandomForest depth/leaf/weight variants; histogram gradient boosting; logistic regression; six CatBoost variants; a first-service expert; 180-day recency weighting; and feature ablations. All fits use seed 42 and at most two compute threads. No new third-party packages were installed.

Feature contracts compare the existing v5 inputs, twelve new deterministic history/weather variables, the contractual-policy indicator, mapped land-cover fractions, removal of terrain/waterway inputs, and removal of weather/environment inputs. The twelve new variables use area return rates, log history counts, prior-claim recency, rain intensity/share, humidity/soil/temperature changes, and service-gap/first-service interactions. They require no invented inspection records or future weather. Undefined rain denominators and unknown history remain missing. These are candidate features, not additions to the frozen model.

The source audit found **5,695 service windows, 521 positives, no duplicate service keys, valid within-package paid-service counts and exact 30-day windows**. There are **2,096 first services and 44 positive first-service windows** in this full mature input. Forty-four positives are sparse; first-service coverage is still weak. The audit verifies input structure, not every Calendar classification or real treatment completion.

All anchors on or after 15 August 2026 were removed before development feature preparation and splitting. Selection uses the existing purged chronological 2025 Q2/Q3/Q4 folds. Completed-outcome embargo and connected property/package purging remain in force. The selected contracts and timestamp were saved before diagnostic scoring and fresh-source extraction. Threshold and Platt calibration use development out-of-fold predictions only; calibrated development metrics are not independent evidence.

## Development comparison

Review capacity is exactly `ceil(20% of services)` for every contract, with canonical key order breaking ties. The main challenger must preserve mean callback recall while improving AP; the review challenger must preserve AP while improving mean callback recall. If no strict gain qualifies, retain v5.

| Contract | Mean AP | Mean callback recall at 20% review capacity |
|---|---:|---:|
| v5 control | 0.2407 | 51.9% |
| Control + engineered histogram boosting | 0.2531 | 45.1% |
| Control + boosting + CatBoost | 0.2504 | 47.3% |
| Control + engineered RandomForest | 0.2407 | 48.1% |
| First-service expert | 0.2405 | 51.9% |
| ExtraTrees depth 14 / leaf 3 | 0.2403 | 48.3% |
| ExtraTrees plus policy | 0.2392 | 49.7% |
| ExtraTrees with history only | 0.2369 | 52.4% |
| ExtraTrees plus new engineered variables | 0.2358 | 49.4% |
| ExtraTrees with recency weighting | 0.2341 | 48.8% |
| ExtraTrees plus land cover | 0.2236 | 45.2% |

These are means of three fold-level metrics, not pooled percentages or fresh test accuracy. Full aggregate results for all 37 contracts are in [the result record](../config/cp2_broad_challenger_results_v1.json). The first-service expert and all other contracts found zero first-service positives at this global review budget in these folds. Earlier fixed review reservations found some first-service positives at the cost of overall recall; see [the focused comparison](CP2_FIRST_SERVICE_CHALLENGER.md).

The blend with the highest AP loses about 6.8 percentage points of callback recall compared with v5 at the declared review capacity. The history-only variant gains about 0.5 points of recall but loses AP. There is no single winner across these objectives. Neither selection rule accepted a replacement. Do not describe the AP-only improvement as an overall model improvement.

## Reproducibility and repairs

The previously inspected 2026 diagnostic reproduced **103 of 179 positive windows found in 395 reviews**, AUC 0.7872 and AP 0.2319. It still found zero of eleven first-service positives. Serialized predictor-only replay matched within 3.9e-16. No old diagnostic result selected an additional candidate or changed thresholds.

The first attempt stopped when a CatBoost setter sent a null class-weight option to its native parser. The code now leaves the plain-weight option implicit, with a real fit regression test. The failed output directory is retained and has no completed result. The verified run is `outputs/cp2-v2/broad_challenger_v1_verified/`; it did not change the candidate pool in response to scores.

The full Python suite passed **436 tests**; nineteen existing Rasterio deprecation warnings remain. Frozen predictor-only replay passed all 5,695 rows with differences below 3.4e-16. Frozen model parameters, calibrator, threshold, bundle hash, current model registry, reporting views and October cloud protocol were not changed.

## Separate later-period check

The protocol reserves **28–31 August services**, with outcomes complete through **30 September**, for a one-time retrospective check. Historical artifacts were saved before fresh source extraction and train on 5,436 services whose outcomes end before 28 August. This prevents later-known labels from entering fitting for those August services. Returning customers are allowed, as in the existing operational evaluation; this is not a new-customer-only test.

The evaluator rejects changed protocol/code/artifact/source hashes, extraction before selection/artifact freeze, incomplete Calendar coverage, altered 30-day windows, nonmatching service keys and a second evaluation. It uses outcome-free inference and paired connected-component uncertainty with the same exact review budget. It cannot replace the October prospective evaluation or justify post-test model selection.

The live source refresh retrieved 11,606 records from all six approved Calendars and nine approved Sheets tabs, with full Calendar days through 30 September. Sources and customer-level predictions remain private. Regional IFS weather was refreshed for 52 grids across 1–30 August (1,560 complete daily records). The temporary feature derivation processed 70.5 MB across its stages; each query kept the 100 MiB billing guard. It produced 5,709 mature anchors, of which 13 belong to the declared evaluation period.

**The later-period check contains 13 service windows and one positive. The retained v5 contract found zero positives in three reviews, and issued no alerts at its development-frozen 0.19 threshold.** AUC was 0.4167, AP 0.125 and accuracy 92.3%, equal to always predicting no callback. One positive cannot establish a reliable AUC estimate or rank competing models. All three selected roles are the same retained control; zero paired differences are therefore identity, not evidence that distinct challengers are equivalent.

The positive was a second paid service in a 3x package. The fresh-source trace confirms a `4/3` post-package warranty signal exactly 30 days later; it was created before its scheduled visit. The reporting release's candidate facts independently confirm that classification. The first cross-check mistakenly read the older materialized base fact table; current management facts are reached through the published dashboard views and their release dependencies. The source difference was resolved without changing the label. All thirteen evaluated rows had location and complete prior-30-day weather coverage, so missing environmental inputs do not explain this miss.

Full aggregate evidence is in [the one-time later-period result](../config/cp2_broad_challenger_later_period_v1.json). Keep it separate from the original 100-service/five-positive August evaluation: the periods and historical fitting cutoffs differ. Do not combine their scores into a single purported frozen-model test. New weather/source revisions remain retrospective inputs; they are not evidence of online predictions made in August.

## Remaining limits and dashboard use

The old 2025 development folds and 2026 diagnostic were already inspected. This is adaptive exploratory research; more models do not create a new independent test. Historical cancellation/title limitations and incomplete historical source revisions remain documented. The frozen model retains the known nine negative 2024–25 cancellation-title anchors. This search did not silently relabel, delete, or retrain that bundle.

Continue structured inspection/treatment/callback collection using [the implemented evidence path](CP2_CALLBACK_RECORDING_GUIDE.md). Severity needs an agreed rubric; unknown treatment or callback evidence must not be guessed. Real source-backed observations and a declared untouched evaluation are still required before using those new fields.

For the dashboard, use the existing v5 historical evaluation, its denominators and uncertainty, with the live collection status. Put this broad comparison on the methods/limitations page as evidence of model selection effort. Do not display individual experimental scores or describe a 0.253 development AP as achieved future performance. Dashboard construction does not need to wait for further parameter searches.

## Commands

```powershell
.\.venv\Scripts\python.exe -m scripts.compare_broad_callback_challengers --output-dir outputs/cp2-v2/broad_challenger_reproduction
.\.venv\Scripts\python.exe -m scripts.evaluate_broad_callback_challenger --experiment-dir outputs/cp2-v2/broad_challenger_v1_verified --source-run-dir outputs/cp2-v2/broad_challenger_v1_fresh_sources
.\.venv\Scripts\python.exe scripts/cp2_model.py verify
```

The evaluation command is one-time and refuses repetition. Reproducing development with a new output directory is not a new untouched evaluation. Use the checked-in protocol and hashes rather than changing the search after seeing diagnostic or later-period results.
