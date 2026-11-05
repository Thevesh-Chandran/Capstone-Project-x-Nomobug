# Expanded model research — 18 October 2026

Completed a bounded extension requested by the owner: alternative targets, outside predictors, model families and chronological training-history choices. No production model or future-test protocol was changed.

Open `outputs/model_validation/20261018_expanded_targets/Model_Research_Explained.html` or the matching `.ipynb`. The notebook embeds aggregate tables and charts and can be shared without the private source folder.

## Scope and actual results

252 target/model/input/history configurations: 96 first-purchase classifiers, 108 programme-purchase classifiers and 48 next-week forecasting configurations. Also ran ten paired development fits with official district population. Threshold comparisons are not independent test samples.

- First-purchase repeat targets: 30/60/90/180 days; 320 common assessment customers, respectively 6/9/10/13 positive outcomes. No candidate passed.
- Programme-purchase targets: 30/90/180 days; 356 assessment purchase dates, respectively 8/15/21 positive outcomes. Past-purchase features are computed before the anchor. Same-customer earlier purchases are allowed for this ongoing-customer use case; uncertainty resamples customer groups.
- The 90-day programme candidate (boosting, 19 inputs, last-year history) had TP8, FP26, FN7, TN315: accuracy90.7%, precision23.5%, recall53.3%. Always-no accuracy95.8%. Not dependable high precision.
- Next-week bookings, packages and sales:14 later weeks. Selected models lost to development-selected simple baselines. Booking MAE10.91 vs10.31; packages4.52 vs4.23; salesRM5096.98 vsRM4104.71.
- Downloaded ERA5 regional rain/temperature/humidity and tested lagged inputs. The latest included weather day precedes the seven-day availability buffer. No future weather used. Regional proxy and reanalysis revisions remain limitations.
- Downloaded DOSM district population;695/2501 source sale rows joined. Population inputs did not improve AP and Brier consistently across periods, so were not retained.
- Found Copernicus GHS-AGE2025: neighbourhood built-stock age proxy, not verified building age; not trained in this round. Official holiday calendars found but not extracted/tested. No verified building-specific online pest-history source obtained.

## Method and limits

Customer development:2024Q4,2025Q1,2025Q2; label windows must mature before every fit. Assessment:2026-01-01 through2026-04-14, all windows mature by2026-10-11. The180-day target lacked50 mature training rows for the first development fold; a documented feasibility amendment uses the two2025 folds before its assessment.

Forecast development:13 fortnightly origins Jan–Jun2026; assessment:14 weekly origins Jul6–Oct5. All-history vs365-day customer history and all-history vs52-week forecasting are selected using development data, not best test percentages.

The source is the pinned14October release, not a new live extraction. These historical periods were inspected previously; this extension is adaptive research, not an untouched final test. The customer-history extension was declared after reviewing the first-purchase outcomes. Keep the original future evaluation unchanged.

A stopped export initially omitted full first-purchase development leaderboards. The recovery script reran development only, reproduced all four original selections exactly, and did not access/alter assessment predictions. Original protocol and amendment retained.

## Verification and reproducibility

-13 targeted tests passed, including maturity purges, no future weather, no later upsell inputs, and past-only customer/forecast history.
-All13 saved prediction sets independently recomputed for confusion counts/forecast MAE. Some policy outputs duplicate the same selected model and are not independent evidence.
-Frozen bundle and current model-pointer hashes unchanged.
-Seven notebook code cells executed;nbformat validated;zero error outputs;two figures rendered and inspected. No separate native Jupyter-kernel execution.
-Source hashes, protocols, searches, downloaded data and receipts are in the output folder. Private customer snapshots and hashed-customer predictions must not be shared as a whole-folder export.

No new candidate passed the improvement gates. Recommendation: retain simple forecasts as explicitly uncertain planning aids; keep return/repurchase classification experimental. This research does not certify the remaining collector flags or complete November outcomes.
