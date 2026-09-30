# CP2 model explained — 1 October 2026

The model estimates the chance of a **recorded corrective Calendar callback during days 1–30 after a matched paid service**. Its intended use is to investigate whether management could prioritise follow-up reviews. The current evidence is promising but too limited to establish dependable operational performance.

The [current model registry](../config/cp2_model_current.json) identifies the frozen v5 model. The [held-out evaluation record](../config/warranty_new_holdout_v5.json) supplies the historical results, and the [cloud collector runbook](../infra/CP2_PROSPECTIVE_CLOUD.md) supplies the current operating arrangements. This guide contains aggregate information only.

## 1. The question, target and prediction

The question is: **“Immediately after this paid service ends, how likely is a corrective callback to be recorded in Calendar within the following 30 days?”**

| Term | Meaning in CP2 |
|---|---|
| One model observation | One eligible matched paid service, called a service anchor |
| Target variable | Whether at least one qualifying corrective Calendar event is recorded against the linked sales package in days 1–30 after the anchor |
| Target type | Binary: 1/true for a recorded callback; 0/false for none recorded in a fully observed window |
| Technical target column | `warranty_signal_within_30d`; this is a historical column name. The current business target is recorded corrective callback, rather than formal warranty entitlement. |
| Prediction/output | A numerical probability between 0 and 1 |
| Prediction time | Immediately after the scheduled end of the matched paid service; a prospective receipt must be stored within five minutes |
| Current main model | ExtraTrees with 300 trees, maximum depth 10 and at least five observations per leaf |
| Frozen alert threshold | 0.19; a score at or above 0.19 becomes an alert under the threshold rule |
| Alternative review rule used in evaluation | Review the highest-risk 20% of services, including any ties at the cutoff |

**Synthetic example:** a probability of 0.12 means the model estimates a 12% chance of a recorded callback in that service window. It is not a statement that the customer has a 12% infestation, that treatment is 88% effective, or that a callback will definitely happen. A probability of 0.25 crosses the frozen 0.19 alert threshold. Under a top-20% review rule, selection instead depends on how that score ranks within the batch. These examples are invented and are not customer scores.

ExtraTrees combines the decisions of many trees. The probability is calibrated using development data so that it is closer to an interpretable risk estimate. Calibration does not guarantee accuracy for future customers; that needs independent outcome evidence.

The eligible callback population includes matched residential and commercial packages. A commercial corrective return can be a valid recorded outcome even though commercial customers have no contractual warranty. Warranty policy is a separate business rule: residential 1x is ineligible; residential 3x has a 30-day claim period after its third paid service; residential 4x, 6x and 12x cover the service period plus 30 days after the final paid service, regardless of pest. Calendar records alone do not prove actual completion, biological recurrence, treatment failure or final entitlement.

A positive **service window** is not necessarily a distinct customer or a distinct callback event. One callback can fall inside the 30-day windows of more than one earlier paid service. A negative means no qualifying callback was recorded in the covered window; it does not prove the premises had no pests.

## 2. What information the current model uses

The frozen main model has **93 raw predictor fields: 87 numerical/binary fields and six categorical fields**. Numerical fields include money, days, counts, distances, fractions and derived combinations. Binary fields are yes/no flags represented as 0 or 1. Categorical fields are labels such as premise type or pest category.

Missing numerical values are handled by imputation and missingness indicators. Categorical values are encoded for the model. Customer names, contact details, raw addresses, raw Calendar descriptions and direct latitude/longitude are not predictor fields. Private linkage identifiers are used to match records and validate predictions; they are not inputs the model learns from.

### Service, package, past history and location reliability — 16 fields

| Exact fields | Type/unit | Meaning |
|---|---|---|
| `service_number`, `package_sessions_recorded` | Numerical counts | Position of the paid service and the recorded number of package sessions |
| `sale_total_rm` | Numerical, RM | Recorded package sales value; this is not settled cash or profit |
| `days_since_previous_service`, `days_sale_to_anchor` | Numerical, days | Gap since the earlier package service and gap from the sale date to this service |
| `prior_package_warranty_claims`, `prior_package_service_events` | Numerical counts | Earlier Calendar return signals and other service entries linked to the package |
| `prior_property_warranty_claims`, `prior_property_service_events` | Numerical counts | Earlier Calendar return signals and other service entries linked to the property |
| `days_since_prior_property_claim` | Numerical, days | Time since the most recent earlier recorded property return signal |
| `prior_property_claims_90d` | Numerical count | Earlier property return signals in the previous 90 days |
| `prior_area_claims_90d`, `prior_area_services_90d` | Numerical counts | Recorded signals and other service entries in the fixed geohash-4 area during the previous 90 days |
| `anchor_month_sin`, `anchor_month_cos` | Numerical transformations | Seasonal month position; sine/cosine represent December and January as adjacent months |
| `location_uncertainty_radius_m` | Numerical, metres | Stated uncertainty of the assigned service location |

The feature names containing `warranty_claims` refer to recorded Calendar signals in this model history. They are not counts of rows in the separate formal claims sheet. Historical entries must precede the anchor and pass the source-creation availability check.

### Weather before the service — 19 fields

| Exact fields | Type/unit | Meaning |
|---|---|---|
| `prior_1d_precipitation_mm`, `prior_3d_precipitation_mm`, `prior_7d_precipitation_mm`, `prior_14d_precipitation_mm`, `prior_30d_precipitation_mm` | Numerical, millimetres | Rain totals in the stated prior periods |
| `prior_7d_wet_days_1mm`, `prior_14d_wet_days_1mm`, `prior_30d_wet_days_1mm` | Numerical counts | Days with at least 1 mm rain |
| `prior_14d_heavy_rain_days_10mm` | Numerical count | Days with at least 10 mm rain in the previous 14 days |
| `prior_14d_max_daily_precipitation_mm` | Numerical, millimetres | Largest daily rain total in the previous 14 days |
| `days_since_last_rain_1mm_capped_30d` | Numerical, days | Recency of a day with at least 1 mm rain, capped at 30 days |
| `prior_7d_temperature_mean_c`, `prior_30d_temperature_mean_c` | Numerical, °C | Average temperature over the stated prior period |
| `prior_7d_temperature_max_c` | Numerical, °C | Highest cached daily **mean** temperature in the previous seven days; it is not the highest observed temperature |
| `prior_7d_relative_humidity_mean_pct`, `prior_30d_relative_humidity_mean_pct` | Numerical, percent | Average relative humidity |
| `prior_7d_soil_moisture_0_to_7cm_mean`, `prior_30d_soil_moisture_0_to_7cm_mean` | Numerical, source soil-moisture measure | Average shallow soil moisture |
| `prior_3d_vs_previous_11d_daily_rain_trend_mm` | Numerical, millimetres per day | Difference between average daily rain in the latest three days and the preceding eleven days |

Weather comes from the Open-Meteo ECMWF IFS historical source. Dates are strictly before the anchor. Exposure is broad, approximately 9–11 km, rather than rainfall measured at the customer's building. An incomplete required window stays unknown rather than becoming zero rain. Historical reanalysis is not a preserved copy of exactly what was available to staff on the historical service day.

### Mapped environmental context — 11 fields

| Exact fields | Type/unit | Meaning |
|---|---|---|
| `elevation_m` | Numerical, metres | Ground elevation |
| `local_relief_500m_m` | Numerical, metres | Variation in elevation around the location within the 500 m context |
| `nearest_mapped_water_m`, `nearest_mapped_forest_m` | Numerical, metres | Distance to nearby mapped water and forest context |
| `hotosm_nearest_waterway_m` | Numerical, metres | Distance to the nearest mapped waterway |
| `hotosm_water_features_500m`, `hotosm_water_features_1km`, `hotosm_water_features_2km` | Numerical counts | Mapped water features in each buffer |
| `hotosm_nearest_drainage_m`, `hotosm_nearest_flowing_water_m`, `hotosm_nearest_standing_water_m` | Numerical, metres | Distance to each mapped water-feature category |

These describe mapped surroundings. They do not measure drain quality, water volume or whether a property flooded. The 2026 HOTOSM/OSM snapshot is applied retrospectively to older services, so its historical availability is a limitation. Coarse service geocodes can make a small buffer or nearest-feature distance appear more precise than the input location supports.

### Environmental combinations — four fields

| Exact field | Formula/meaning |
|---|---|
| `log1p_waterway_distance` | Natural logarithm of `1 + nearest waterway distance`; reduces the scale of large distances |
| `water_rain_interaction` | Prior 14-day rain ÷ `(1 + nearest waterway distance in metres / 1000)` |
| `drainage_rain_interaction` | Prior 14-day rain ÷ `(1 + nearest drainage distance in metres / 1000)` |
| `rain_soil_interaction` | Prior 14-day rain × prior seven-day mean shallow soil moisture |

These are numerical combinations that let the model compare contextual patterns. They are not causal effects of rain or drainage.

### Pest text indicators — ten fields

Nine binary fields identify recognized text: `pest_has_ant`, `pest_has_cockroach`, `pest_has_rodent`, `pest_has_bed_bug`, `pest_has_termite`, `pest_has_mosquito`, `pest_has_fly`, `pest_has_general_control` and `pest_has_other_terms`. The numerical count `pest_distinct_known_types` records the number of recognized pest categories. A mixed-pest record can have several flags set to 1.

### Service-stage and context combinations — 27 fields

| Exact fields | Type/formula | Meaning |
|---|---|---|
| `anchor_is_first`, `anchor_is_final`, `anchor_is_single_service`, `anchor_is_mixed_pest` | Binary | First service, final paid service, 1x package and at least two recognized pest types |
| `anchor_service_progress` | Numerical fraction | Service number ÷ recorded package sessions |
| `anchor_remaining_services` | Numerical count | Recorded package sessions − service number |
| `prior_property_return_rate_smoothed`, `prior_package_return_rate_smoothed` | Numerical ratios | `(earlier recorded return signals + 1) / (earlier other service entries + 10)` at property/package level |
| `first_service_prior_property_return_rate`, `mixed_pest_prior_property_return_rate` | Numerical combinations | Smoothed property ratio multiplied by the first-service/mixed-pest flag |
| `first_service_no_property_history` | Binary | First package service and no recorded earlier property service history |
| `mixed_pest_rain_14d`, `first_service_rain_14d` | Numerical combinations | Prior 14-day rain multiplied by the mixed-pest/first-service flag |
| `first_pest_ant`, `first_pest_cockroach`, `first_pest_rodent`, `first_pest_bed_bug`, `first_pest_termite`, `first_pest_mosquito`, `first_pest_fly` | Seven binary combinations | First-service flag multiplied by the corresponding recognized pest flag |
| `final_pest_ant`, `final_pest_cockroach`, `final_pest_rodent`, `final_pest_bed_bug`, `final_pest_termite`, `final_pest_mosquito`, `final_pest_fly` | Seven binary combinations | Final-service flag multiplied by the corresponding recognized pest flag |

The smoothed ratios are deliberately transformed model inputs, with fixed smoothing constants. They are not the management dashboard's customer return-rate or warranty-claim-rate formulas.

### Categorical labels — six fields

1. `pest_category`: recorded sales pest text/category.
2. `package_category`: recorded sales package text/category.
3. `calendar_pest_text_category`: classified Calendar pest text.
4. `calendar_service_method_category`: classified Calendar service method.
5. `normalized_pest_category`: normalized recognized pest grouping.
6. `premise_type`: residential/commercial context.

### Flooding, land cover and dashboard radius

Satellite flood observations, regional flood reports and land-cover fractions were evaluated in separate bounded comparisons. **They are excluded from the frozen main v5 predictor list.** The existence of these datasets does not mean the current model uses them. Flood observations had limited reliable exposure coverage, and the flood additions did not improve the declared development selection criterion. Missing or unobserved flooding cannot be treated as proof of dry conditions. See [environmental source and timing notes](CP2_ENVIRONMENTAL_FEATURE_NOTES.md) for the source limitations.

The secondary policy candidate includes the separate predictor `contract_eligible_at_paid_anchor`; the selected main ExtraTrees depth-10 model does not include it. Choosing that secondary model after seeing a better holdout metric would amount to selecting on the test result, so the main selection stays fixed.

The model's prior-area history uses a fixed geohash-4 proxy. The dashboard's 1/2/5 km DBSCAN settings are alternative spatial summaries. Changing that dashboard radius does not retrain the model, change weather resolution or establish improved model accuracy.

## 3. Training, historical testing and the future experiment

Training lets the model learn from earlier observations. A held-out test measures its predictions on observations reserved from the relevant fit and model selection. A future test is stronger operational evidence when predictions were logged before outcomes happened.

| Population | Purpose | Services / callback-positive windows |
|---|---|---:|
| Purged pre-2026 development pool | Model selection through 2025 forward validation folds; completed-outcome embargo and package/property separation | 3,048 / 289 |
| Previously inspected 2026 diagnostic | Exploratory check of model weaknesses; it is not a new untouched final test | 1,975 / 179 |
| Historical model fit for the later holdout | Training outcomes completed before 15 August 2026 | 5,333 / 492 |
| Later historical holdout | Services on 15–27 August 2026, with outcomes covered through 26 September | 100 / 5 |
| Frozen prospective refit | Fixed model contract refitted on mature history for future predictions | 5,695 / 521 |

The prospective refit includes **2,075 services from 2026**. Its latest training service is 27 August and latest training outcome is 26 September. Replaying its training probabilities verifies that the saved model reproduces its scores; it does not measure predictive accuracy.

The main model was selected from development results before the later historical holdout was accessed. Returning customers can appear in prior training for that later operational test. Historical source revisions cannot all be reconstructed, so the evaluation is a retrospective later-service test, rather than proof that predictions were actually logged during August. See the [held-out evaluation's limitations](../config/warranty_new_holdout_v5.json).

## 4. Every metric released to the dashboard

The [Gold evaluation view](../dbt/models/gold/dashboard_ml_evaluation.sql) exposes eight metrics for the selected model and corrected reference on the same **100 services, including five positive windows**. The reference is the earlier corrected ExtraTrees depth-6 contract, used to judge whether the selected model adds value.

| Metric / exact `metric_name` | Selected v5 ET10 | Reference ET6 | Interpretation |
|---|---:|---:|---|
| ROC AUC / `roc_auc` | 0.8905 | 0.8126 | Ranking discrimination: how often a positive window scores above a negative one. Random ranking is 0.5; perfect ranking is 1. It is not an accuracy percentage. |
| Average precision / `average_precision` | 0.3051 | 0.2723 | Precision averaged over increases in recall across score cutoffs. Useful for rare callbacks; the callback prevalence baseline here is 0.05. It is not precision at the frozen threshold. |
| Brier score / `brier_score` | 0.04106 | 0.04323 | Average squared probability error: mean `(predicted probability − actual 0/1 label)²`. Lower is better. |
| Threshold accuracy / `threshold_accuracy` | 94% | 92% | Correct alerts and correct non-alerts ÷ all service windows, using each model's frozen threshold. |
| Always-no-callback accuracy / `always_no_callback_accuracy` | 95% | 95% | Accuracy from predicting no callback for every service. It finds no callbacks and shows how an imbalanced sample can make raw accuracy look good. |
| Recall at 20 reviews / `review20_recall` | 80% | 60% | Positive windows found among the highest-risk 20 ÷ all five positive windows. |
| Precision at 20 reviews / `review20_precision` | 20% | 15% | Positive windows found ÷ the 20 services selected for review. |
| Positive windows found at 20 reviews / `review20_positive_windows_found` | 4 | 3 | Count found using equal review capacity. |

**The clearest management interpretation:** if staff could review 20 of these 100 service windows, the selected model's top 20 contained four of the five recorded callbacks. Sixteen selected services had no recorded callback in their covered window. The reference found three of five at the same review capacity. This is a historical prioritisation comparison; it is not a proven future staffing benefit.

At the main model's separate **0.19 threshold**, there were two correctly alerted callback windows, three alerts without a recorded callback, three missed callback windows and 92 correctly unalerted windows. That gives 94% accuracy and 40% precision/recall. The 80% recall above belongs to the **20-service review rule**, not the 0.19 threshold. Threshold precision/recall are in the committed evaluation JSON but are not additional metrics in the current Gold seed.

The 20% review precision is four times the 5% callback prevalence in this small sample. It is a descriptive result and does not prove that management will obtain four times better results in future.

### Dashboard aggregation rules

The source contains 16 rows: two model roles × eight metrics. A scorecard for the selected model must filter `model_role = selected_ap` and the required `metric_name`, then use `MAX(metric_value)`. Reference cards use `model_role = reference`. Use `MAX` for repeated cohort metadata such as `holdout_rows` and `holdout_positive_rows`; summing them multiplies the population.

The model page describes a fixed historical cohort. Ordinary sales-date, pest and location controls cannot recompute performance from these aggregate rows. An October date filter on the September evaluation timestamp would hide the evaluation rather than provide October accuracy. Keep this page outside those business filters.

## 5. What the evidence cannot yet establish

There are only **five positive windows** in the later holdout. Statistical intervals are wide and include no improvement over the reference for AUC and average precision. Therefore the model is a promising frozen experiment, with no dependable performance gain established yet.

The earlier 2026 diagnostic also showed a **first-service blind spot**: the main model missed all eleven first-service positive windows under its evaluated review and threshold rules. The later holdout has no first-service positives, so it cannot demonstrate that this weakness has been resolved. Do not use the overall ranking metric to imply equally good performance for every pest, package, premise or service stage.

A source correction on 30 September now recognizes titles beginning `CANCELLED`/`CANCELED`, even when Calendar's status still says confirmed. **Nine negative 2024–25 anchors in the frozen 5,695-row training input have this mismatch.** None is a direct 2026 held-out anchor, but the historical model was frozen before this correction. Its metrics therefore do not precisely represent a fresh fit under all corrected source rules. The nine rows have not been silently removed and the model has not been refitted to change the future experiment. The [submission record](CP2_OCTOBER_SUBMISSION.md) documents this limitation.

Recorded callbacks depend on source quality, matching, staff recording practices and the customer's decision to request a return. Weather and mapped surroundings can be associated with records without causing the outcome. Static contemporary map context also limits strict historical availability claims.

## 6. What happens next in the cloud

The [cloud cohort protocol](../config/cp2_cloud_cohort.json) was declared at **11:55 am Malaysia time on 30 September**, before its **1–27 October 2026** service cohort began. It uses the same frozen model and 30-day target.

The private Cloud Run collector checks Calendar every two minutes. When an eligible service reaches its scheduled end, it obtains fresh source information, builds validated features in bounded temporary BigQuery queries, scores the frozen model and stores a private immutable receipt within five minutes. Cloud operation does not require the laptop to remain on. Private scores and receipt indexes are not dashboard sources.

Every eligible service must have one timely receipt, and Calendar outcomes must be complete. A late prediction cannot replace a missed window. Earlier September cohorts remain incomplete; the October cohort has its own coverage audit. The current Gold model evaluation view does not contain dynamic prediction/missed-window counts, so a dashboard collection-status note needs dated verified evidence or a separately approved aggregate source.

Services on 27 October need observation through 26 November to finish their 30-day windows. The one-time cloud evaluation is scheduled for **12:00 noon Malaysia time on 27 November 2026**, conditional on complete evidence. It rejects missing/late predictions, incomplete outcomes and changed protocol/model hashes, and does not overwrite an existing final evaluation.

**CP2 can be submitted by 31 October.** The submission reports the historical results, their limitations, and actual prospective collection coverage. Waiting until November does not improve or change the frozen model; it allows the separate future outcomes to mature so performance can be measured honestly.

