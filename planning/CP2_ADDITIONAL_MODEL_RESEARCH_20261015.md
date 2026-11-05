# Additional predictive models — research completed 15 October 2026

Recommendation: keep the existing pest-return v5 model unchanged. A simple weekly booking forecast and an experimental 90-day repeat-purchase ranking are the most useful additions to investigate. No new model is cleared for dependable operational use.

Tested 216 complete forecasting configurations across three targets, two horizons and three history windows, plus six repeat-purchase classifiers. The original model and October protocol hashes were unchanged.

## Forecast comparison

| Target / horizon | Development-selected method | Test MAE | Selected baseline MAE | Error reduction |
|---|---|---:|---:|---:|
| weekly_bookings_h1 | hist_gradient_boosting / all | 11.56 | 23.00 | 49.7% |
| weekly_bookings_h4 | random_forest / 2026_only | 42.55 | 42.00 | -1.3% |
| weekly_packages_h1 | holt_damped / last_52_weeks | 4.57 | 4.79 | 4.7% |
| weekly_packages_h4 | holt_damped / last_52_weeks | 13.73 | 11.67 | -17.7% |
| weekly_sales_rm_h1 | catboost / 2026_only | 5073.35 | 5033.85 | -0.8% |
| weekly_sales_rm_h4 | seasonal_52 / all | 15498.78 | 15498.78 | 0.0% |

MAE is mean absolute error: bookings/packages in counts, sales in RM. It is not classification accuracy. Four-week targets are the sum of the next four weeks; their nine test origins overlap and are not independent.

### The baseline check changes the booking recommendation

Boosting reduced one-week booking error from 23.00 to 11.56 against the development-selected same-week-last-year baseline, winning nine of twelve weeks. However, a post-test sensitivity check found that the four-week moving average had lower error: **9.31 bookings**, versus **11.56** for boosting. The advanced model is about 24.2% worse than this alternative. Do not advertise the 49.7% gain as superiority over simple forecasting.

The moving-average diagnostic had WAPE 13.5%, versus 16.8% for boosting. This does not mean “86.5% accuracy.” The simple method was identified after viewing this test block, so it needs a new forward test; it is not a newly confirmed winner on untouched data.

The research gate passed for boosting only relative to the preselected baseline. That limited pass is insufficient for promotion after the stronger baseline and source-quality checks. None of the other five target/horizon experiments met the original improvement gate.

The illustrative 90% development-residual interval for boosting covered 12/12 later weeks but averaged 68.6 bookings wide; broad intervals and only eight calibration origins limit planning precision. Four-week booking coverage was only 4/9; it must not be advertised as a calibrated 90% interval.

## Repeat-purchase prediction

Question: after a customer’s first **recorded** paid programme, will they buy a different programme within 90 days? An upsell within the same reviewed programme is not a repeat purchase. This differs from the current pest-return model.

Development: 262 customers, 8 repeat buyers. Final training: 1221 mature customer histories. Later test: **557 customers, 19 repeat buyers**. Development-selected histogram gradient boosting found **13/19 (68.4%)** repeat buyers in a list of **112 customers**; **99 did not repurchase** within the window. Random selection would find about **3.82** buyers at the same review capacity. Ranking lift is **3.40×**; exploratory 90% customer-bootstrap interval **2.49–4.30×**.

Average precision was 0.0939 against 0.0341 prevalence; ROC AUC 0.7613. The list precision was only 11.6%. These metrics describe ranking, not calibrated purchase probabilities. Selection had only eight development positives; testing had nineteen. The predeclared twenty-positive minimum failed. Do not relax it after seeing results.

Potential use: prioritise human follow-up, with experimental status and false-alert counts. Do not send automatic marketing messages, promise purchases or label customers as lost. Prospective validation and probability calibration remain required.

## Data and leakage audit

Immutable release: `cp2r_20261014045314a561c6`. Three bounded BigQuery reads each used a dry run and 100 MiB cap; total successful processed bytes: 215,928.

- Booking series: 157 complete reconstructed weeks, 7,909 records after excluding the left-censored first week and the current partial week. Weekly year groupings can include dates from an adjacent calendar year.
- Sales/package series: 135 complete weeks. Five undated sales were excluded. Nineteen included sales have missing amounts (nine in 2024, six in 2025, four in 2026); the monetary target sums known recorded amounts and does not estimate those missing values. There are 405 inferred Sales years plus five unresolved dates.
- Zero weeks mean no included records in this release, not proof that collection was complete. Changes in recording or business size can create artificial trends.
- Current Calendar edits/cancellation state reconstruct historical labels. 546 Calendar rows dated in 2026 were updated after their anchor-day midnight; this is a limitation, not proof that each update was after service or improper. Historical as-of labels/features cannot be fully reconstructed from this export.
- Training uses only prior weeks; direct four-week training targets end before the forecast origin. No future weather or already-booked-future totals are used. Development ends before the final July–October block; model/window choice is frozen before its test scores.
- Repeat training labels mature before evaluation starts. Each customer appears once. Only initial-day features are used; later upgrades, final balances and appointment counts are excluded. Four profiles with undated purchases, 130 uncertain identities, 164 immature profiles and eight without an observed dated purchase were excluded. Current matching is retrospective.
- Neither the booking labels nor customer labels establish completed treatments, settled cash, profit, or genuine satisfaction. Historical evaluation is not an already-logged prospective forecast.

## Methods and research sources

Forecast candidates: last observation, recent four/eight-week mean, annual seasonal naive, simple exponential smoothing, damped Holt, Ridge, Poisson, random forest, Extra Trees, histogram gradient boosting (squared and count losses), CatBoost. All/52-week/2026-only histories were compared. Money targets did not use Poisson. Forty-eight expected seasonal-baseline fits were unavailable because the 2026-only window has fewer than 52 weeks.

ARIMA/ETS are valid research directions, but statsmodels was not installed and no new dependency was added. SES and damped Holt were implemented with training-only parameter fitting. Prophet, deep networks and fine district models were not run: the series contain only 135–157 weekly observations, changing recording regimes and limited repeated annual cycles. Their suitability is unproven, not ruled out universally.

Cancellation prediction needs reliable historical change/replacement linkage and as-of snapshots; a current CANCELLED title is insufficient. Payment-lateness prediction needs actual payment dates/instalment allocations; reminders and green formatting are not such labels. Enquiry conversion needs validated enquiry-to-sale links and a mature conversion horizon. Those tasks were assessed and withheld rather than given manufactured targets.

- [Forecasting: Principles and Practice — benchmarks, time-ordered validation, errors and intervals](https://otexts.com/fpp3/toolbox.html)
- [scikit-learn — lagged features and time-series forecasting](https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html)
- [scikit-learn — average precision](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)
- [CatBoost — regression API](https://catboost.ai/docs/en/concepts/python-reference_catboostregressor)
- [statsmodels — SARIMAX](https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.sarimax.SARIMAX.html)

## Additions and remaining work

Prepared reproducible protocols, scripts, source receipts, per-origin predictions, selected-model records, diagnostics, figures and a companion notebook. No current model, cloud schedule, live dashboard, OAuth permission or source record was changed.

Recommended next additions are a clearly experimental weekly booking forecast (simple moving-average baseline shown alongside any challenger) and a repeat-purchase prioritisation pilot. Log new forecasts/rankings before outcomes and assess them against frozen baselines. Weekly booking outcomes mature weekly; repeat-purchase labels require 90 days, so a new repeat test started now cannot fully mature by 30 November. A November submission can report this historical study honestly, not a completed 90-day future test.

Validation: 18 relevant tests passed, including later-outcome invariance, four-week time boundaries, linked-upsell labels, unknown/immature exclusions and existing v5 entrypoint guards. No full dbt run was needed because no warehouse transformation changed.

Artifacts: `results.json`, `repeat90_results.json`, `predictions.csv`, `development_leaderboard.csv`, `all_baseline_sensitivity.csv`, `source_receipt.json`, `run_manifest.json`, `protected_artifact_check.json`. See `research_companion.ipynb` for an executed reading companion.

### Final packaging and visual checks
Two fitted research estimators and the simple moving-average specification are packaged in candidate_registry.json; none is active. Repeat holdout scores replayed identically. All three original frozen model binaries matched their manifest hashes. The repeat ranking cutoff tie audit retained exactly 13 cases under either tie ordering. Three exported figures were visually inspected for labels and values; the companion contains five executed cells and three saved image outputs, with no cell errors. Notebook UI rendering itself was not inspected.

