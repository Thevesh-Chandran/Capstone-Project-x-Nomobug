# Settlement age and holiday follow-up — 18 October2026

Owner requested actual testing of the previously identified sources. Downloaded the21.4MB Copernicus GHS-AGE1km release and official Cabinet2024/2025/2026 PDFs. Used existing PDF libraries; no new dependencies or third-party code installed.

Results: `outputs/model_validation/20261018_age_holidays/Age_and_Holiday_Test.html` and matching `.ipynb`. Share only `Age_and_Holiday_Review.zip`, which contains aggregate outputs, not private address matches or raw customer snapshots.

## Actual testing

- Question: recorded pest-related return within30days of a paid service. Existing93-input ExtraTrees comparison; same fitting/calibration/property-purged chronology for every variant.
-10initial fits: existing inputs, festival dates, weekday, age proxy, all additions across2025Q3/Q4. Later periods chosen because GHS-AGE was released June26,2025. Earlier training inputs reconstructed from2020-built-stock context available before evaluation begins. No2026 pest assessment.
-36of68 precise-address candidates had nine agreeing raster samples;97of3620 earlier services had accepted age codes. Only34of1600 evaluation service windows had codes. Remaining values unknown.
-Pooled1600evaluation windows,194returns: referenceTP74/FP166/FN120/TN1240; ageTP80/FP162/FN114/TN1244. Precision30.83%→33.06%, recall38.14%→41.24%, accuracy82.12%→82.75%; always-no87.88%.
-Age initially improved AP/Brier in both periods.12follow-up fits: availability-only and five address-group code permutations across two periods.3/5shuffled controls also passed the same screen. No convincing independent age-effect or significance claim; hold candidate.
-Festival dates did not consistently improve return prediction.78rolling forecast fits tested three festival-week counts against the fixed earlier-selected forecast settings on13development origins. Errors increased1.9%bookings,3.4%packages,16.1%sales. No later assessment used for these forecast checks.

## Definitions and limits

Age code is the dominant epoch when half of the1kmcell's2020built surface was reached; it is not the construction date of a customer's building. Location uncertainty<=250m plus nine offset samples is an approximate spatial screen, not a footprint match or complete circular uncertainty proof.

Festival dates are a manually verified partial federal/common KL-Selangor calendar. No substitute days or extra gazettes inferred; no assumptions of actual company closure. Current publication/revision history is incomplete. Day-of-week inputs tested separately.

This is adaptive historical research on previously inspected periods; controls were declared after seeing the initial gain. No operational model promotion. Frozen files verified unchanged.8targeted tests pass with one existing rasterio deprecation warning.10saved prediction sets independently checked against their metrics. Notebook executed with project harness, nbformat validated, no native-kernel run. Source URL/hash/size receipts retained.
