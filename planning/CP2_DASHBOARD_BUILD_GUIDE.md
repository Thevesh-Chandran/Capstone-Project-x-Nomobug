# CP2 management dashboard: detailed build guide

Prepared 1 October 2026 from the deployed Gold schemas and current dbt SQL. Audience: company owner, sales manager and operations manager. Use it in a weekly workload review and a monthly business review. The owner builds the existing Looker Studio report; this guide does not certify its current charts or viewer permissions.

Start with [the finance/customer metric dictionary](CP2_METRIC_DICTIONARY.md), [operations/weather dictionary](CP2_OPERATIONS_METRIC_DICTIONARY.md), [model explained](CP2_MODEL_EXPLAINED.md), and [the exact field/type reference](CP2_DASHBOARD_FIELD_REFERENCE.md).

## What the dashboard should help management do

1. Understand recorded sales demand, payment activity and service workload.
2. Identify groups with substantial recorded return work and decide where to investigate.
3. Plan future appointments using the scheduled workload distribution.
4. Judge whether environmental comparisons and model results have enough evidence to use.
5. Assign correction of missing/ambiguous source information before acting on a misleading total.

The report's recommendations should be tied to visible evidence. Examples: review unmatched Calendar links, clarify missing payment references, investigate short-interval return records, or inspect workload concentration. The current records do not establish a profitable pest segment, insufficient staffing, treatment failure, or a rain-caused infestation. Set business targets with management after agreeing on definitions and baselines.

## Common setup in Looker Studio

Preserve useful existing charts. Add the stable BigQuery `profound-keel-500007-s4.gold` views needed for each page. Never connect to dated `cp2r_...` datasets: the daily job publishes through stable names. Do not connect this aggregate management report to raw Bronze/Silver, contact details, exact service locations or individual predictions.

For each chart: add the chosen chart type; select its data source; choose the dimension and measure below; explicitly set aggregation; select its date-range dimension where one exists; add chart filters; then format and test it. Dates are dates, RM fields are currency, counts are whole numbers, probabilities/shares are percentages, rainfall is mm. `Record Count` counts summary rows, not services/packages: use the supplied count fields with SUM.

Use page-scoped controls. Set a date range dimension explicitly for every date-driven chart. Monthly views support whole-month comparisons, not equal-elapsed-day comparisons. Start with a verified complete reporting month and compare it with the preceding complete month; show current-month activity separately as partial. The first October daily refresh is scheduled at 06:00 MYT. Its completion must be checked before claiming it includes the full September endpoint.

Pest, package and Calendar/team controls affect only sources that actually contain those dimensions. A shared date field name does not make unrelated categorical controls work across sources. Test each affected chart after a filter selection. Pages 6 and 7 use fixed 2026 views without dates; page 9 is a fixed historical evaluation. Do not put the management date control on these pages.

For rates, divide summed counts and return null when the denominator is zero. A null means unavailable. Never average percentages from unequal groups. For example, warranty-signal share is `SUM(warranty_claim_event_rows) / SUM(scheduled_service_event_rows)`. Looker Studio supports explicit aggregate formulas; use a CASE guard for a zero denominator. [Calculated fields](https://docs.cloud.google.com/looker/docs/studio/about-calculated-fields), [date ranges](https://docs.cloud.google.com/looker/docs/studio/set-report-date-ranges), [controls](https://docs.cloud.google.com/looker/docs/studio/about-controls).

Keep the layout consistent: page title and period, relevant controls, a few main cards, charts explaining the pattern, then a small evidence/review table. Start with about 1,200 px width and check narrow rendering before sharing. Use neutral colours for workload; use an attention colour for supported exceptions. A higher warranty count alone is not a bad-performance verdict. Show sample sizes beside shares.

## Page 1 — Business overview

Question: **What changed in recorded business activity, and what should we review first?**

| Component | Source and setup | Management use |
|---|---|---|
| Sales value card | `sales_monthly_recorded`; SUM `recorded_package_face_value_rm`; date `closed_month` | Track recorded package value |
| Packages sold card | Same source; SUM `countable_package_rows` | Track sold package rows; an upgrade may create another row |
| Payments recorded card | `payments_monthly_recorded`; SUM `recorded_payment_entry_amount_rm`; date `payment_month` | Track dated sheet payment-entry amounts |
| Scheduled visits card | `dashboard_service_monthly`; SUM `scheduled_service_event_rows`; date `service_month` | Track Calendar workload |
| Warranty-signal visits card | Same source; SUM `warranty_claim_event_rows` | Track recorded return workload |
| Two separate monthly lines | Sales value by `closed_month`; payments by `payment_month` | Compare trajectories while preserving different accounting meanings |
| Monthly workload chart | Service month; normal, warranty and other categories below | Explain total Calendar activity |
| Source freshness table | `dashboard_source_freshness`; `source_name`, `extracted_at_utc`, `hours_since_extraction`; MAX age | Tell management which source snapshot they are viewing |

Safe service stack: normal = `normal_package_service_event_rows`; warranty = `warranty_claim_event_rows`; other = `scheduled_service_event_rows - normal_package_service_event_rows - warranty_claim_event_rows`. Current normal and warranty categories are exclusive. Do not add a broad extra-visit count as another exclusive category.

Add a small, dated review panel only after inspecting the supporting page: e.g. missing references or unmatched services with their actual count and source. Do not invent red/green thresholds, an empty zero queue, or recommendations from the chart alone. The overview should link to the detailed pages rather than repeat their tables.

## Page 2 — Enquiries and customer information

Question: **How much enquiry activity is recorded, and how complete is its outcome information?**

Source `prospect_reply_monthly_recorded`; date `first_reply_month`. This is the first staff reply month, not necessarily the enquiry arrival month.

| Component | Setup |
|---|---|
| Cards | SUM `prospect_candidate_rows`, `recorded_open_rows`, `recorded_closed_rows`, `exact_won_remark_rows` |
| Monthly activity line | Dimension `first_reply_month`; SUM `prospect_candidate_rows` |
| Outcome annotation table | Month; open, closed, exact-WON counts side by side. WON is a separate remark indicator and can overlap statuses, so do not stack all three |
| Source exceptions table | SUM `undated_first_reply_rows`, `future_first_reply_rows`, `acquisition_review_rows`; keep a separate all-source view so null dates are visible |
| Payment-link context table | `dashboard_payment_link_monthly`; date `payment_link_month`; SUM `payment_link_source_rows`, `recorded_won_rows`, `missing_status_rows`, `date_review_rows` |

Useful action: review enquiry status and acquisition documentation. OPEN/CLOSED are source conversation annotations, not a current live lead queue. The source-row denominator for payment links includes retained unqualified rows; do not calculate a conversion funnel by dividing WON or sales by that total.

The current aggregate does **not** support unique customers, repeated-conversation counts, B2B inspection bookings, marketing channel performance, customer retention, or new-versus-returning rates. B2B is extracted but has no approved management booking/funnel aggregate. Record these as missing measurements, rather than zero results. Customer/site history needs a separately reviewed identity model and restricted source; do not connect private detail to fill the page.

## Page 3 — Sales and payments

Question: **How are recorded package value and payments changing, and which finance records need review?**

Use sales and payment monthly sources separately. Cards: recorded package face value, packages sold, recorded payment amount and dated payment entries (`dated_nonfuture_rows`). Add two monthly charts and two compact finance exception tables. Sales exceptions: missing totals, inferred close years, undated sales, excluded dispositions. Payment exceptions: missing amounts, text dates, undated entries, combined references, references needing review.

Date controls use `closed_month` for sales and `payment_month` for payments. Explain this beside the charts: payment entries recorded later can refer to earlier packages. A null-month row belongs in an exceptions table outside the selected-period chart. In the table, display an Unknown date label and its retained counts.

Use SUM for monetary values and count fields. Do not subtract payments from sales as outstanding balance, sum joined payment amounts per package, or call the result profit/net revenue. Combined-reference payments are counted once in the payment source; their amounts are not allocated across sales. Mean package price requires a priced-package denominator not currently published; omit AOV for now.

Action: review malformed amounts and references in the source; ask finance to verify settlement or outstanding balance through the appropriate records when those decisions are required.

## Page 4 — Services and teams

Question: **Where is scheduled workload concentrated, and are appointments linked to the right package?**

Source `dashboard_scheduling_capacity`; date `service_date`; dropdown `calendar_name`. Calendar names represent the source team/Calendar label, not a verified individual technician assignment.

| Component | Setup |
|---|---|
| Cards | SUM `scheduled_event_rows`, `warranty_claim_event_rows`; matching share = SUM `matched_sales_event_rows` / SUM `scheduled_event_rows` |
| Daily workload line | `service_date`; SUM `scheduled_event_rows`; optional breakdown `calendar_name` |
| Team workload bars | `calendar_name`; SUM `scheduled_event_rows`; include counts in labels |
| Weekday/team heat table | Rows `calendar_name`, columns `day_of_week_number`, SUM `scheduled_event_rows`; 1=Sunday through 7=Saturday |
| Daily review table | Date, Calendar, scheduled count, warranty count, unmatched count, ambiguous count |

Use a selected historical period for activity review and a separate clearly labelled next-14-days section for upcoming scheduling. Give future charts their own explicit relative date range and isolate them from the historical date control; test that changing the historical period does not change the upcoming period. A future recorded appointment is workload on the calendar, not a completed job. Current sources do not provide capacity hours, completion rates, travel efficiency or staff success rankings.

Action: inspect concentrated future days and manually check whether redistribution is appropriate; resolve unmatched/ambiguous package links before interpreting breakdowns. The aggregate table cannot identify an individual appointment to change; that requires a separate restricted operational view or Calendar review.

## Page 5 — Warranty signals, returns and refunds

Question: **How much return work is recorded, how soon does it occur, and what refund records need follow-up?**

| Component | Setup |
|---|---|
| Return workload cards | Monthly service source; SUM warranty signals; weighted warranty share |
| Recorded returns by interval | `dashboard_recurrence_monthly`; `recurrence_bucket`; SUM `recorded_warranty_signal_rows`; order 0–7, 8–14, 15–30, 31–60, 61+ days, then unknown/review buckets |
| Monthly return distribution | Same source; date `service_month`, breakdown `recurrence_bucket` |
| Refund cards/trend | `dashboard_refund_monthly`; date `refund_month`; SUM `refund_source_rows`, `recorded_refund_amount_rm` |
| Refund exception table | Linked/unmatched rows, status/amount/date review counts, recorded-complete count; preserve undated rows |

An interval is from a warranty-signal entry to the immediately preceding matched service-like entry at the same sale and exact normalized address text. That preceding visit can itself be a warranty visit. This is not uniformly days after the last paid treatment. Keep `no_previous_event` and property-review categories visible; missing intervals do not become zero days.

Formal claim-sheet entries, Calendar warranty signals and model-positive service windows are three different counts. Do not add them into one claims total. Formal claims currently need an approved aggregate source before a dashboard card is added. Recorded refund amount/status is source evidence; COMPLETE is not bank-transfer confirmation.

Show the owner's policy as a short definition: commercial and residential 1x have no warranty; residential 3x can claim within 30 days after the third service; residential 4x/6x/12x can claim throughout the service period and through 30 days after the final service, for any pest. Linked 1x plus Upsell 2x must be interpreted as the reconciled episode. A return signal does not by itself decide entitlement.

Action: inspect substantial short-interval return workload and unresolved refund records. Treatment failure and pest reinfestation require further evidence.

## Page 6 — Pests and packages

Question: **Which recorded pest/package combinations drive business value and review workload?**

This page is explicitly **2026 snapshot context**. It has no month control because its current sources have no date field.

Use `dashboard_package_fit_matrix`. Dropdowns: `pest_type`, `package_type`, `contract_type`; test each against this source. Keep original raw labels, including mixed-pest bundles. Display null/unrecorded labels as Unknown, without guessing a pest or package.

| Component | Setup |
|---|---|
| Package mix bars | `pest_type` or `package_type`; SUM `package_rows` |
| Recorded value by pest/package | SUM `recorded_package_face_value_rm`; RM |
| Package matrix | Rows `pest_type`, columns `package_type`; SUM `package_rows` |
| Context table | Pest, package, contract; package rows, packages with payment evidence, scheduled entries, warranty signals |
| Payment evidence share | SUM `packages_with_payment_evidence` / SUM `package_rows` |
| Warranty workload share | SUM `warranty_claim_event_rows` / SUM `scheduled_event_rows`; show both counts |

Payment evidence means at least one linked entry, not paid in full. The view combines packages closed in 2026 and their 2026 Calendar activity, including recorded future dates. Its package-row and face-value totals are therefore not interchangeable with the overview's dated nonfuture sales metrics. Do not duplicate sales value by splitting mixed pests into several rows.

Add a service-review table from `dashboard_treatment_difficulty`: area, Calendar, pest, package, scheduled events, warranty events, non-warranty extra visits, package-linked refund context. Filter `sufficient_volume_for_comparison = true`; this retains source groups with at least five entries, so label the filtered scope. Recompute shares from SUM counts when grouping rows. Omit the null composite difficulty score. Refund context can repeat across visits for a package; it is not a count of distinct refunds or a verdict about a team.

Action: choose substantial groups for manual source/service review and discuss package demand. These descriptive metrics do not prove package suitability, profitability or causal team differences.

## Page 7 — Locations and hotspots

Question: **Where are recorded service and return workloads concentrated, and how sensitive are clusters to the distance setting?**

This is another **2026 snapshot** page without month, pest or team controls.

Area source `dashboard_spatial_area`: use a bubble map at aggregate area centroids; size by SUM `scheduled_service_event_rows`, colour by SUM `repeat_signal_event_rows` / SUM `scheduled_service_event_rows`. Tooltip/table: `area_cell`, scheduled entries, return signals and share. Areas are geohash-5 bins of several kilometres with at least five entries. They are not customer property points. Display area IDs as analytical area codes until a verified locality-name lookup exists.

If the chart needs one geo field, create a text latitude/longitude pair from the aggregate centroid fields and set its geographic type to Latitude, Longitude. Use the centroid fields, never restricted property coordinates. Follow the [Google Maps reference](https://docs.cloud.google.com/looker/docs/studio/google-maps-reference) and verify that plotted locations fall within the expected Malaysia service area.

Cluster source `dashboard_spatial_cluster_summary`: use a single-select `radius_km` control with 1, 2 and 5 km; default 2 km. Show a cluster-centroid map and table with `cluster_id`, `distinct_service_properties` and `recorded_warranty_signal_rows`. Use one radius at a time, because cluster IDs are meaningful only within that scenario. Do not sum counts across the three radii. Cluster creation requires at least three distinct properties; unclustered noise is omitted.

Show location coverage from the monthly service source in a separate labelled coverage panel for the same 2026 scope. Distinct package counts across areas/properties are not globally additive. The radius changes the clustering scenario; it does not retrain the callback model or change its held-out accuracy.

Action: identify areas to investigate and discuss routing/service demand. A hotspot is a pattern in recorded service data, not an outbreak declaration or pest travel distance.

## Page 8 — Weather and seasonal patterns

Question: **Do recorded return visits and other appointments have different prior-weather context, and is coverage sufficient to compare?**

Source `dashboard_weather_monthly`; date `service_month`; breakdown `event_group` into recorded warranty signal and other scheduled service entry. Show two-series monthly prior-14-day rain comparison, a humidity comparison, and a coverage table containing scheduled rows, complete-weather rows and coverage share for each group/month. Soil moisture can be a secondary chart if management finds it useful. Keep rainfall and humidity on separate unit scales.

Monthly mean rain fields (`avg_prior_3d_precipitation_mm`, `avg_prior_7d_precipitation_mm`, `avg_prior_14d_precipitation_mm`) describe cumulative prior-window rainfall per event, then averaged across covered events. They are not total rainfall across the company. Humidity is a prior-seven-day mean percentage; soil moisture is a prior-seven-day shallow-layer mean. Service day is excluded from prior windows.

For each mean, create row-level `weighted_rain_14d = avg_prior_14d_precipitation_mm * complete_prior_14d_weather_rows`, then plot `SUM(weighted_rain_14d) / SUM(complete_prior_14d_weather_rows)`, with a zero-denominator guard. Repeat the weighting for humidity/other weather fields. Coverage = SUM complete rows / SUM scheduled rows. An unweighted AVG of monthly means gives small months the same influence as large ones.

Use only complete prior-14-day windows for these published means. Data are roughly 9 km Open-Meteo reanalysis estimates, not a weather sensor at the property. Future scheduled entries can have missing weather. A fresh source release alone does not prove complete weather coverage. Current weather aggregates have no pest/area dimensions and no flood fields, so those controls/charts need new approved views.

Action: investigate weather-associated patterns and discuss seasonal preparation when coverage supports the comparison. Rainfall, flooding and nearby water cannot be declared causes from these comparisons.

## Page 9 — Callback model: evidence and validation

Question: **Could the model help prioritize a manageable number of reviews, and how much confidence should management have?**

Source `dashboard_ml_evaluation`. Keep this page on its fixed historical cohort, without a management date/pest/location filter.

| Component | Setup |
|---|---|
| Sample-size cards | MAX `holdout_rows` = 100; MAX `holdout_positive_rows` = 5 |
| Callbacks found card | Filter `model_role = selected_ap`, `metric_name = review20_positive_windows_found`; MAX `metric_value` = 4 |
| Review precision card | Selected role, `metric_name = review20_precision`; MAX value = 20% |
| Equal-budget comparison bars | Filter `metric_name = review20_positive_windows_found`; dimension `model_name`, MAX `metric_value`; selected 4 vs reference 3 |
| Metric comparison pivot | Rows `metric_name`, columns `model_name`, MAX `metric_value`; set appropriate per-metric formats or use separate tables for ratios and counts |

The view has 16 rows: two models × eight metrics. SUM of repeated sample-size fields would multiply the sample. Filter each performance card to one model and one metric before using MAX.

Explain: of 100 later historical service windows, five had recorded callbacks; reviewing the top 20 scores found four of them, while 16 reviewed services had no recorded callback in that window. AUC 0.8905 is ranking performance, not 89.05% accuracy. Threshold accuracy is 94%, while predicting no callbacks for everyone gives 95% because positives are rare. The frozen top-20 review policy and the fixed probability threshold are different evaluations.

Show the small-positive-sample uncertainty and first-service weakness prominently. The model's 93 predictors cover service/package stage, history, pests/premise/method, prior weather, terrain/water proximity and location uncertainty. Satellite/report flood and land-cover fractions were investigated but are not included in the selected frozen model. Neither chart filters nor DBSCAN radius recalculate model performance.

Use a dated text statement for October prospective status only after checking the private audit. This Gold view does not contain live prediction counts or misses. Future accuracy remains pending until complete outcomes, no earlier than 27 November. Keep individual scores private. [Full explanation](CP2_MODEL_EXPLAINED.md).

Action: decide whether further validation is worthwhile. No automatic warranty, customer-treatment or staff-assessment decision is supported.

## Page 10 — Data quality and refresh status

Question: **Which inputs need correction, and how current is the last approved report?**

Freshness and issue counts describe the current published whole-source snapshot. They have no business reporting-date dimension. Scope any date control only to the dated service-coverage charts and label their selected period separately.

| Component | Setup |
|---|---|
| Source snapshot table | `dashboard_source_freshness`; source, extraction time, release run ID, age hours |
| Oldest snapshot card | MAX `hours_since_extraction`; hours, no SUM |
| Issue review table | `dashboard_data_quality`; source and issue code, affected rows, source rows, issue share |
| Matching/location coverage | `dashboard_service_monthly`; summed matched/eligible counts divided by total scheduled entries |
| Warranty weather coverage | Same source; SUM complete-weather warranty rows / SUM warranty rows |

For a source/issue row, use MAX or SUM as appropriate to its unique row; when regrouping issue rows, do not sum denominators or total affected counts across codes. The same record can have several issues. A combined payment reference or text date may be a handled category, rather than an error. `reviewed_date` is the view's query date, not source extraction time.

Show extraction timestamps with an explicit timezone. If displaying Malaysia local time, use a verified UTC+8 conversion rather than merely changing the label. A failed refresh preserves the previous approved views; it must not be presented as current just because a chart loads. Do not infer last-run success from freshness alone; the private audit supplies that operational evidence.

Action: assign source fixes, check stale inputs and repeat reconciliation after changes. Privacy and reconciliation are acceptance gates before sharing the report.

## Build sequence and acceptance

Build pages 1, 3 and 4 first; then 5 and 6; then 2, 7 and 8; finish model and quality. This gets the main business decisions visible early while keeping all required areas covered. Customer histories, validated B2B funnel/unique prospects, settled cash/outstanding balance, completed work, and formal-claim aggregates are explicit evidence gaps; do not silently present substitute metrics.

For every chart, verify the source, date scope, aggregation, numerator/denominator, filter behaviour and displayed label. Compare a selected-period total and a reset-to-All total to Gold. Preserve null/review categories, test a populated filter, and inspect desktop/narrow layout. Check every source and page for private fields and approved viewer permissions. The reviewed source definitions do not certify a report until its actual rendered charts and permissions are checked.
