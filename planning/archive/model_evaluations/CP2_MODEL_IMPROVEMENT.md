> Historical v4 evidence, superseded by [the corrected v5 model](../../CP2_CORRECTED_MODEL_CANDIDATES_V5.md). Retained for reproduction; its recommendation, counts and source-refresh blocker are historical.

# CP2 model improvement — 27 September 2026

The reviewed labels, prediction timing and evaluation were repaired before
model comparison. These are retrospective experiments, not operational
recurrence forecasts. The already-inspected 2026 period is diagnostic.

## Recommendation

Use recorded corrective-callback planning as the strongest experimental
CP2 prediction goal. It has a larger sample and useful ranking evidence.
Warranty entitlement remains a policy calculation; the warranty-only
prediction models are too weak or uncertain for operational decisions.
Freeze the development-selected model and evaluate future mature records
before adopting its probabilities or alert threshold.

The [subsequent blind-spot experiment](CP2_BLIND_SPOT_EVALUATION.md) produces
a focused RandomForest challenger: 108/179 callbacks versus 100 at the same
395-review capacity, including 10/20 mixed-pest positives versus zero. First-service
capture remains zero, overall AP is slightly lower, and overall uncertainty
includes no gain. Retain v4 as the reference and freeze this challenger for
prospective evaluation; no operational contract has been replaced.

The subsequent [claim-date and description-feature experiment](CP2_CALLBACK_EVIDENCE_RECONCILIATION.md)
reconciles all 5,598 targets, isolates seven date conflicts and tests ten recovered
Problem-field variables. It establishes no useful gain at equal review capacity
(94 callbacks for a refitted baseline versus 91 with descriptions at 374 reviews).
The [recording guide](../../CP2_CALLBACK_RECORDING_GUIDE.md) and blank template define
the structured request, visit, treatment and availability evidence needed next.

## Target and variable meaning

Each row is a recorded paid base service. Prediction occurs immediately
after that service; the target is categorical/binary: 1 if a recorded
corrective claim visit follows within 30 days, otherwise 0. Models output
a numerical probability from 0 to 1. Ordinary scheduled visits are not
positive outcomes. Callback planning includes discretionary commercial
returns, without granting commercial warranty entitlement.

The 30-day prediction horizon does not shorten 4x/6x/12x entitlement
through the active service period and 30 days after the final service.
A claim later than 30 days after an anchor can be policy-valid while
remaining outside this particular prediction target.

Numerical predictors include package/session counts, prior service and
claim history, price, service gaps, season, rainfall, humidity, temperature,
soil moisture, elevation, waterway distances and land-cover proportions.
Categorical predictors describe the recorded pest, package and treatment
method; the callback experiment also includes residential/commercial type.
Outcome counts, future appointments and post-anchor weather are excluded.

## What was implemented

- Applied all 80 user decisions with event-level provenance. Two unresolved
  records remain unknown; their matched packages are excluded from training.
- Fixed negated warranty wording and sequence-only consultation classification.
- Preserved reviewed upsell, included bonus, completion and discretionary-claim
  exceptions. Commercial contractual eligibility was not expanded.
- Fixed the prior-seven-day workload join and bounded service history at the anchor.
- Compared fixed 30-day targets: residential 3x after service three, and
  residential 4x/6x/12x after each recorded base service. The latter windows
  can overlap; validation and bootstrapping preserve property dependence.
- Also tested operational corrective-callback planning for matched packages
  across residential/commercial clients. It predicts recorded extra work,
  independently of contractual entitlement, and uses explicit premise context.
- Added antecedent 1–30 day rainfall, wet/heavy-rain counts, rain recency,
  temperature, humidity, soil moisture and rainfall-trend variables.
- Added ESA WorldCover 2021 built-up, tree, grass, crop, water and wetland
  fractions within 250 m and 1 km. The historical map predates the examples.
- Refreshed elevation/place/waterway context for newly eligible anchors.
- Tested deterministic Malay/English pest aliases and multi-pest indicators
  while retaining raw labels and unknown terms. The normalised challenger
  won callback development selection by only 0.0027 AP, with mixed fold gains.
- Compared logistic regression, random forests, extra trees, histogram
  gradient boosting, CatBoost and a prevalence baseline with six feature sets.
- Embargoed outcomes not known before each fold and kept connected packages
  and properties together. Assertions check both identifiers separately.
  All imputers and categorical transforms fit training only.
- Added positive-slope calibration from pre-2026 predictions, top-20% review
  metrics, component-bootstrap intervals, saved models and replayable inputs.

## Selected models and diagnostic results

| Population | Model / feature set | Rows / claims | AUC | AP / prevalence | Accuracy at development threshold | No-claim accuracy | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| residential_3x_final_30d | extra_trees_depth6 / compact_history | 434 / 112 | 0.541 | 0.283 / 0.258 | 70.0% | 74.2% | 11.6% |
| residential_4x_6x_12x_after_service_30d | catboost_depth3_plain / base_weather_environment | 171 / 9 | 0.631 | 0.079 / 0.053 | 73.1% | 94.7% | 33.3% |
| matched_packages_recorded_callback_30d | extra_trees_depth6 / base_weather_environment | 1975 / 179 | 0.774 | 0.248 / 0.091 | 67.9% | 90.9% | 72.6% |

AP (average precision) evaluates ranking of rare claims; its no-signal
baseline is claim prevalence. AUC = 0.5 is chance discrimination. High raw
accuracy alone can reward never identifying a claim.

Evaluated 271 candidate/feature combinations,
including development-only challengers. Duplicate target experiments are
selected by pre-2026 development AP, never by their 2026 scores.

## Development evidence and uncertainty

### residential_3x_final_30d

Selected from 85 candidates using 3 pre-2026 folds. Mean development AP 0.2883, fold SD 0.1430; AUC 0.5695.

Package/property-component bootstrap AUC interval: 0.486–0.600. AP interval: 0.235–0.348.

Reviewing the highest-scored 20.0% of rows captures 20.5% of claims, with 26.4% precision (1.02× the population claim rate).

Development comparison on the same cohort:

| Feature set | Pest context | Best model | Mean AP | Fold SD |
| --- | --- | --- | ---: | ---: |
| compact_history | raw | extra_trees_depth6 | 0.2883 | 0.1430 |
| base_weather | raw | extra_trees_depth6 | 0.2857 | 0.1521 |
| base_weather_environment_landcover | raw | rf_depth6 | 0.2845 | 0.0827 |
| base_weather_environment | raw | extra_trees_depth6 | 0.2840 | 0.1457 |
| base | raw | extra_trees_depth6 | 0.2797 | 0.1631 |
| compact_history_landcover | raw | hist_depth2 | 0.2659 | 0.1336 |

Calibration and review workload:

```json
{
  "calibration": {
    "method": "platt_on_pre2026_purged_walk_forward_oof",
    "fitted_rows": 677,
    "slope": 2.1823415427256543,
    "intercept": -1.2878639192874857,
    "development_calibrated_brier_is_in_sample_for_calibration": true,
    "ranking_invariant": true,
    "applied": true
  },
  "diagnostic_2026_raw": {
    "rows": 434,
    "positives": 112,
    "prevalence": 0.25806451612903225,
    "roc_auc": 0.5407885980479148,
    "average_precision": 0.2829364926378531,
    "brier_score": 0.23688618430150873,
    "accuracy": 0.6013824884792627,
    "balanced_accuracy": 0.5217391304347826,
    "precision": 0.28368794326241137,
    "recall": 0.35714285714285715,
    "f1": 0.31620553359683795,
    "alert_rows": 141,
    "threshold": 0.5,
    "majority_class_accuracy": 0.7419354838709677,
    "ap_lift_over_prevalence": 1.0963789089716807
  },
  "diagnostic_prevalence_baseline": {
    "rows": 434,
    "positives": 112,
    "prevalence": 0.25806451612903225,
    "roc_auc": 0.5,
    "average_precision": 0.25806451612903225,
    "brier_score": 0.19304765439524924,
    "accuracy": 0.7419354838709677,
    "balanced_accuracy": 0.5,
    "precision": 0.0,
    "recall": 0.0,
    "f1": 0.0,
    "alert_rows": 0,
    "threshold": 0.5,
    "majority_class_accuracy": 0.7419354838709677,
    "ap_lift_over_prevalence": 1.0
  },
  "diagnostic_priority_top20pct": {
    "target_fraction": 0.2,
    "target_rows": 87,
    "selected_rows_including_ties": 87,
    "realized_fraction": 0.20046082949308755,
    "score_cutoff": 0.23015462669150868,
    "cutoff_tied_rows": 3,
    "precision": 0.26436781609195403,
    "recall": 0.20535714285714285,
    "precision_lift_over_prevalence": 1.024425287356322,
    "selection": "within_batch_top_fraction_including_cutoff_ties"
  }
}
```

### residential_4x_6x_12x_after_service_30d

Selected from 85 candidates using 2 pre-2026 folds. Mean development AP 0.3296, fold SD 0.2664; AUC 0.6384.

Package/property-component bootstrap AUC interval: 0.477–0.790. AP interval: 0.037–0.265.

Reviewing the highest-scored 20.5% of rows captures 33.3% of claims, with 8.6% precision (1.63× the population claim rate).

Development comparison on the same cohort:

| Feature set | Pest context | Best model | Mean AP | Fold SD |
| --- | --- | --- | ---: | ---: |
| base_weather_environment | raw | catboost_depth3_plain | 0.3296 | 0.2664 |
| base_weather | raw | catboost_depth3_plain | 0.3033 | 0.2512 |
| base_weather_environment_landcover | raw | rf_depth3 | 0.2814 | 0.0079 |
| compact_history | raw | lr_c10.0_balanced | 0.2616 | 0.2372 |
| base | raw | lr_c10.0_balanced | 0.2403 | 0.1882 |
| compact_history_landcover | raw | rf_depth3 | 0.2371 | 0.1593 |

Calibration and review workload:

```json
{
  "calibration": {
    "method": "platt_on_pre2026_purged_walk_forward_oof",
    "fitted_rows": 113,
    "slope": 0.7956370804576912,
    "intercept": 1.4117752097914125,
    "development_calibrated_brier_is_in_sample_for_calibration": true,
    "ranking_invariant": true,
    "applied": true
  },
  "diagnostic_2026_raw": {
    "rows": 171,
    "positives": 9,
    "prevalence": 0.05263157894736842,
    "roc_auc": 0.6310013717421125,
    "average_precision": 0.07931162897038169,
    "brier_score": 0.05339420696963692,
    "accuracy": 0.9473684210526315,
    "balanced_accuracy": 0.5,
    "precision": 0.0,
    "recall": 0.0,
    "f1": 0.0,
    "alert_rows": 0,
    "threshold": 0.5,
    "majority_class_accuracy": 0.9473684210526316,
    "ap_lift_over_prevalence": 1.506920950437252
  },
  "diagnostic_prevalence_baseline": {
    "rows": 171,
    "positives": 9,
    "prevalence": 0.05263157894736842,
    "roc_auc": 0.5,
    "average_precision": 0.05263157894736842,
    "brier_score": 0.049886621315192746,
    "accuracy": 0.9473684210526315,
    "balanced_accuracy": 0.5,
    "precision": 0.0,
    "recall": 0.0,
    "f1": 0.0,
    "alert_rows": 0,
    "threshold": 0.5,
    "majority_class_accuracy": 0.9473684210526316,
    "ap_lift_over_prevalence": 1.0
  },
  "diagnostic_priority_top20pct": {
    "target_fraction": 0.2,
    "target_rows": 35,
    "selected_rows_including_ties": 35,
    "realized_fraction": 0.2046783625730994,
    "score_cutoff": 0.18941581364512475,
    "cutoff_tied_rows": 1,
    "precision": 0.08571428571428572,
    "recall": 0.3333333333333333,
    "precision_lift_over_prevalence": 1.6285714285714288,
    "selection": "within_batch_top_fraction_including_cutoff_ties"
  }
}
```

### matched_packages_recorded_callback_30d

Selected from 101 candidates using 3 pre-2026 folds. Mean development AP 0.2380, fold SD 0.1194; AUC 0.7515.

Package/property-component bootstrap AUC interval: 0.740–0.807. AP interval: 0.197–0.310.

Reviewing the highest-scored 20.0% of rows captures 55.9% of claims, with 25.3% precision (2.79× the population claim rate).

Development comparison on the same cohort:

| Feature set | Pest context | Best model | Mean AP | Fold SD |
| --- | --- | --- | ---: | ---: |
| base | raw | extra_trees_depth6 | 0.2353 | 0.1268 |
| base_weather_environment | raw | extra_trees_depth6 | 0.2227 | 0.1107 |
| base_weather | raw | extra_trees_depth6 | 0.2226 | 0.1130 |
| base_weather_environment_landcover | raw | rf_depth6 | 0.2170 | 0.1103 |
| compact_history | raw | extra_trees_depth6 | 0.2153 | 0.1163 |
| compact_history_landcover | raw | hist_depth2 | 0.2003 | 0.1083 |
| base_weather_environment | normalised + raw | extra_trees_depth6 | 0.2380 | 0.1194 |
| base | normalised + raw | extra_trees_depth6 | 0.2283 | 0.1242 |
| compact_history | normalised + raw | extra_trees_depth6 | 0.2200 | 0.1155 |

Calibration and review workload:

```json
{
  "calibration": {
    "method": "platt_on_pre2026_purged_walk_forward_oof",
    "fitted_rows": 2481,
    "slope": 1.4784577935752956,
    "intercept": -2.0428006178369875,
    "development_calibrated_brier_is_in_sample_for_calibration": true,
    "ranking_invariant": true,
    "applied": true
  },
  "diagnostic_2026_raw": {
    "rows": 1975,
    "positives": 179,
    "prevalence": 0.09063291139240506,
    "roc_auc": 0.7743340259546354,
    "average_precision": 0.2483446911950121,
    "brier_score": 0.16095957342531383,
    "accuracy": 0.6678481012658228,
    "balanced_accuracy": 0.7067163529133642,
    "precision": 0.18072289156626506,
    "recall": 0.7541899441340782,
    "f1": 0.2915766738660907,
    "alert_rows": 747,
    "threshold": 0.5,
    "majority_class_accuracy": 0.909367088607595,
    "ap_lift_over_prevalence": 2.740116006201949
  },
  "diagnostic_prevalence_baseline": {
    "rows": 1975,
    "positives": 179,
    "prevalence": 0.09063291139240506,
    "roc_auc": 0.5,
    "average_precision": 0.09063291139240506,
    "brier_score": 0.08243810453133409,
    "accuracy": 0.909367088607595,
    "balanced_accuracy": 0.5,
    "precision": 0.0,
    "recall": 0.0,
    "f1": 0.0,
    "alert_rows": 0,
    "threshold": 0.5,
    "majority_class_accuracy": 0.909367088607595,
    "ap_lift_over_prevalence": 1.0
  },
  "diagnostic_priority_top20pct": {
    "target_fraction": 0.2,
    "target_rows": 395,
    "selected_rows_including_ties": 395,
    "realized_fraction": 0.2,
    "score_cutoff": 0.16273147928869156,
    "cutoff_tied_rows": 1,
    "precision": 0.25316455696202533,
    "recall": 0.5586592178770949,
    "precision_lift_over_prevalence": 2.7932960893854752,
    "selection": "within_batch_top_fraction_including_cutoff_ties"
  }
}
```

## Limits and next evidence

- Environmental features were evaluated, not assumed beneficial. See the
  development comparisons above. Small AP differences relative to fold
  variability do not establish environmental benefit or causation.
- In the contractual cohorts, WorldCover coverage is about 53% for 3x anchors and 99% for multi-service
  anchors, balanced across development/diagnostic periods. Missing data
  remains missing, with training-fold imputation indicators.
- Weather is coarse IFS reanalysis; it does not resolve house-level rain
  or flooding. OSM waterways are mapped proximity, not flood occurrence.
- Reanalysis can be revised and is not a frozen as-available weather feed.
  The September 2026 OSM snapshot is retrospective for 2025 anchors.
  Compact/history and weather-only candidates provide no-OSM sensitivity.
- Spatial buffers can be smaller than geocoding uncertainty; approximate
  locations cannot establish exact house-level water or land-cover exposure.
  See [environmental source notes](../../CP2_ENVIRONMENTAL_FEATURE_NOTES.md).
- Maximum seven-day temperature means the maximum cached daily mean,
  not the maximum instantaneous temperature.
- Labels describe recorded Calendar claim visits, not verified biological
  recurrence or completed treatments. Calendar snapshots may contain
  retrospective edits; full historical record versions are unavailable.
- Address hashes can miss alternate spellings of the same property.
- The small multi-service positive count and broad model search make model
  selection uncertain. Development calibration metrics fit the calibrator
  and must not be presented as independent calibration validation.
- A higher-score 60/90-day 3x outcome would exceed the confirmed policy.
  Ordinary repeat appointments would also mix scheduled work with claims.
- Link original and upsell SALES allowances using verified package identity.
  Do not sum all purchases for a customer or infer warranty from stale notes.
- Promised bonus sessions must remain distinct from contractual tier and
  claim-triggered service. Ambiguous allowances remain outside this cohort.
- The most valuable prospective inputs are pre-service infestation severity,
  observed pest evidence/count, property/treatment context, and a documented
  claim reason/date. These were not fabricated as retrospective features.
- Freeze the selected models and use newly arriving, fully mature records
  for the next independent evaluation; do not tune against these 2026 scores.

## Verification and replay

The subsequent [2026 training-period comparison](CP2_2026_TRAINING_EVALUATION.md)
tests earlier-2026-only and updated all-history fits on identical later services.
Neither establishes a gain over the frozen callback recommendation. Its subset
metrics should not be mixed with the original full-2026 metrics below.

The subsequent flood-data experiment is documented separately in
[CP2_FLOOD_MODEL_EVALUATION.md](CP2_FLOOD_MODEL_EVALUATION.md). It preserves this
target and cohort, compares observed nearby flooding with an observation-only
control, and tests reported regional floods in a separate locked comparison.
The metrics below are the completed pre-flood evaluation receipt.

Live bounded dataset build: 53/53 passed. Local suite: 181 passed.
Saved selected model artifacts also reload and predict in a fresh Python process.
Composite input fingerprint: `e8ddefc5ba728366fa74bebc3ffcad576ad1d26fd8237fd766e2d7d17aa62163`.
Each model contract records its own exact input fingerprint and source.

```powershell
.\.venv\Scripts\python.exe scripts\build_warranty_experiment.py
.\.venv\Scripts\python.exe scripts\benchmark_warranty_models.py --input-json outputs\cp2-v2\model_benchmark_components\dataset_input.json --output-dir outputs\cp2-v2\model_benchmark_replay
.\.venv\Scripts\python.exe scripts\benchmark_warranty_models.py --source profound-keel-500007-s4.analytics_ml.warranty_callback_fixed_horizon_dataset --input-json outputs\cp2-v2\model_callback_components\dataset_input.json --premise-context --output-dir outputs\cp2-v2\model_callback_replay
.\.venv\Scripts\python.exe scripts\benchmark_warranty_models.py --source profound-keel-500007-s4.analytics_ml.warranty_callback_fixed_horizon_dataset --input-json outputs\cp2-v2\model_callback_normalized_pest\dataset_input.json --premise-context --normalize-pest-context --feature-set compact_history --feature-set base --feature-set base_weather_environment --model extra_trees_depth6 --model rf_depth3 --model rf_depth6 --model catboost_depth4_plain --model lr_c1.0_plain --output-dir outputs\cp2-v2\model_callback_normalized_replay
```

Sources: [ESA WorldCover data access](https://esa-worldcover.org/en/data-access),
[Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api),
[HOTOSM Malaysia waterways](https://data.humdata.org/dataset/hotosm_mys_waterways).


## 27 September: all-mature-data prospective setup

Both frozen experimental models now use all 5,598 mature services (1,975 from 2026). Predictor-only scoring preserves pending outcomes. All 269 tests pass; no prospective accuracy is available and the live feature feed is not connected. The 28 September–27 October cohort cannot be finally evaluated before 27 November. A read-only Calendar refresh failed because Google sign-in expired or was revoked; newer source availability remains unknown. See [the protocol](CP2_PROSPECTIVE_MODEL_TEST.md). Governing v4 remains unchanged.


## Current checkpoint: corrected v5

Use [the corrected v5 report](../../CP2_CORRECTED_MODEL_CANDIDATES_V5.md) and `config/cp2_model_current.json`. The earlier reference recommendation and frozen v1 setup above are historical. The renewed read-only Calendar refresh succeeded; history availability, complete-day maturity and paired score alignment are repaired. Fourteen fixed candidates were tested. The development-selected primary ET10 caught4/5 positive service windows at20reviews on100newer services (reference3/5); onlyfive positives prevent a reliable-win claim. The final future refit trains5695mature services/2075from2026. Live extraction remains unconnected; no future accuracy is measured.
