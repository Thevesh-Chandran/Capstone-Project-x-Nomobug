# Nomobug dashboard — build guide

Updated 15 October 2026. This replaces the earlier build instructions in this file. Build in the existing Looker Studio report, using the approved Data Bloo-inspired mockup as the layout reference. Mockup numbers are illustrative; live charts must use BigQuery.

- Live report: https://datastudio.google.com/reporting/590914e8-066b-4671-a130-7a62a3af435a
- Complete mockup: ../outputs/dashboard_design/20261014_complete_system/index.html
- Exact field reference: CP2_DASHBOARD_FIELD_REFERENCE.md
- Recurring-payment definitions: CP2_RECURRING_PAYMENTS_DASHBOARD_GUIDE.md

## 1. What goes where

**Dashboard:** sales, customer groups, enquiries, booked visits, warranty visits, pests/packages, district sales, weather comparisons, recurring-payment summaries, reminders and data checks.

**Private website:** customer search/history, individual payment follow-up records, AI questions, area exploration, model evidence, weekly booking estimates, repeat-purchase review list and system status. Keep customer names, phone numbers, emails, exact addresses and individual experimental scores out of the unlisted dashboard.

Keep seven main navigation entries: Overview; Sales & customers; Enquiries; Services & warranty; Pests & packages; Areas & weather; Payments. Sales/Customers, Services/Warranty, and Areas/Weather are subpages. Data checks is supporting navigation. Keep model evidence pages hidden from ordinary navigation; do not delete their historical results.

## 2. Start with the design

Use the mockup for composition and the updated Overview for a working example. Build one page completely before copying its styles.

1. Open the report and click **Edit**.
2. Open **Theme and layout → Layout**. Use a desktop canvas around **1400 px wide**. Choose enough height for the page, normally 900–1100 px. This project targets laptops and PCs.
3. Use a pale blue-grey background, for example **#EEF3F8**, and white chart panels. Avoid large dark explanation blocks, background images and animation.
4. Use Arial or another single clean font throughout: page title 30–34 px; chart title 18–20 px; labels/table body 14–16 px; card values 36–44 px. Increase chart height before shrinking labels.
5. Use navy **#25384F** for headings, blue **#208FE5** for primary series, orange **#FF8354** for a second series, and purple/cyan for additional categories. Use the same colour for the same measure across pages. Avoid colouring every chart green.
6. Keep about 40 px outer padding and 24 px gaps. Align chart edges and panel heights. Use modest corners, around 12 px, and no heavy shadows.
7. Put the title at the upper left and relevant controls at the upper right. Follow with 3–4 important cards, then the main comparison charts. Put detail tables underneath.
8. Keep explanations in chart descriptions/tooltips where supported. Keep a short visible qualifier when it changes interpretation, such as **current records**, **assigned locations**, or **October incomplete**.

Suggested Overview geometry, in canvas pixels:

| Element | X | Y | Width | Height |
|---|---:|---:|---:|---:|
| Title | 40 | 30 | 600 | 55 |
| Date control | 1000 | 30 | 360 | 50 |
| Four cards | 40 / 376 / 712 / 1048 | 110 | 312 | 120 |
| Monthly combo | 40 | 300 | 850 | 310 |
| District bars | 914 | 300 | 446 | 310 |
| Package bars | 40 | 690 | 640 | 250 |
| Payment follow-up table | 704 | 690 | 656 | 250 |

Place each chart heading about 35 px above its chart. Do not let oversized text boxes overlap chart headers. If a heading is hard to select, double-click the blank upper part of its text box rather than the chart header beneath it.

## 3. Connect the correct data

Use **Resource → Manage added data sources** to reuse existing connectors. Add a new connector only when the view is absent.

For a new connection: **Add data → BigQuery → CP Google Sheet Nomobug → gold → approved view → Add**. The project ID is `profound-keel-500007-s4`.

Use stable **gold** views. Dated `cp2r_...` datasets are release snapshots and should not be connected as live reporting sources. If the dataset picker shows many snapshots, use **Show more items** until the stable `gold` entry appears.

If a published field is missing in Looker: edit the data source, click **Refresh fields**, inspect the proposed changes, and apply only the expected fields. This was needed for `month_start` in **Sales by area**.

Use **SUM** for the supplied count and amount fields. Do not use **Record Count** as a count of customers, purchases or visits: it counts aggregate source rows. Use RM for money, integers for counts, % for shares, mm for rainfall, and hours for freshness.

A monthly date field supports month-level reporting. Selecting a few days does not turn a monthly source into daily sales. Use whole-month ranges on sales pages. Do not compare partial October with a complete September as if they were equal periods.

## 4. Overview

Management question: **How is the business doing, and what needs a closer look?**

| Visual | Source | Dimension / metric | Settings |
|---|---|---|---|
| Sales card | `sales_monthly_recorded` | SUM `recorded_package_face_value_rm` | Label **Sales (RM)**; date `closed_month` |
| Packages sold card | Same | SUM `countable_package_rows` | Date `closed_month` |
| Booked visits card | `dashboard_service_monthly` | SUM `scheduled_service_event_rows` | Date `service_month` |
| Warranty visits card | Same | SUM `warranty_claim_event_rows` | Calendar signals, not a formal-claims count |
| Large monthly combo | `sales_monthly_recorded` | X `closed_month` at Year Month; SUM sales and SUM `countable_package_rows` | Sales bars, left axis; packages line, right axis; month ascending; legend visible |
| District sales bars | **Sales by area** (`dashboard_business_sales`) | `district`; SUM `sales_rm` | Horizontal; date `month_start`; assigned districts only; top five + Others |
| Package bars | **Sales by area** | `package`; SUM `sale_rows` | Horizontal; date `month_start`; descending count; keep Unspecified; top five + Others |
| Current payment follow-up table | `dashboard_recurring_payment_quality` | `billing_arrangement`; SUM `sales_total_recorded_paid_rm`, `contracts_with_scheduled_reminders_next_7_days`, `contracts_without_source_schedule` | Labels **Payment arrangement**, **Paid so far (RM)**, **Reminders · 7 days**, **Missing dates**; current snapshot |

For the district chart, use the existing **2026 sales — assigned districts** filter for the 2026 default. It excludes Unassigned only from this comparison, not from the overall Sales card. If you expand reporting to another year, replace the fixed-year restriction deliberately. Never allocate unknown addresses to a district just to make the totals match.

For readable district labels, the chart-local field is `REGEXP_REPLACE(district, "^.* / ", "")`. Retain the underlying source district for inspection. Drag the plot's inner left boundary rightwards to give names enough room; resizing the outer chart alone does not solve a cramped axis.

**Already implemented and rendered:** the combo, district and package bars, and payment follow-up table. Their current arrangement is a usable reference, not certification that every report page is finished.

## 5. Sales & customers

Use two subpages so all-history customer groups are not confused with selected-period sales.

### Sales

Top: Sales, packages sold, and number of records missing sales amounts if the selected source supports it. Main left: monthly sales bars/line. Main right: sales by package. Bottom: sales by pest and residential/commercial premise breakdown.

- Monthly source: `sales_monthly_recorded`; date `closed_month`; SUM `recorded_package_face_value_rm` and `countable_package_rows`.
- Breakdown source: **Sales by area**; date `month_start`; dimensions `package`, `pest`, `premise`; SUM `sales_rm` or `sale_rows`.
- Use one measure per ordinary bar chart. Do not stack sales amounts and purchase counts on one monetary scale.
- Use **Sales**, not profit. Package prices are not bank-confirmed cash receipts.
- Do not use the unreliable PAYMENTS tab for payment tracking.

### Customers

Source: **Customer summary** (`dashboard_business_customers`). This is **all-history customer grouping** and has no business-date dimension.

- Cards: SUM `customer_groups`; repeat groups filtered to the verified repeat segment; identity-review groups separately.
- Left: horizontal bars by `segment`, SUM `customer_groups`.
- Right: sales by `segment`, SUM `sales_rm`.
- Bottom: `segment`, customer groups, `programmes`, sales.

Inspect actual segment values before creating filters. A customer group can have several programmes; these are not interchangeable counts. Do not use a period selector on this source. Named customer rankings and search remain on the private website.

## 6. Enquiries

Management question: **How much enquiry activity is recorded, and how complete are its outcomes?**

Source: `prospect_reply_monthly_recorded`; date `first_reply_month`.

- Cards: SUM `prospect_candidate_rows`, `recorded_open_rows`, `recorded_closed_rows`, `exact_won_remark_rows`.
- Large chart: first reply month vs enquiry rows.
- Comparison chart: open and closed recorded statuses by month. Keep the WON remark as separate context because it can overlap the statuses.
- Small quality table: `undated_first_reply_rows`, `future_first_reply_rows`, `acquisition_review_rows` in an all-source view, so unknown dates are not hidden by a date filter.
- Optional payment-link context: `dashboard_payment_link_monthly`, date `payment_link_month`; SUM `payment_link_source_rows`, `recorded_won_rows`, `missing_status_rows`, `date_review_rows`.

Use **First staff reply month** in the description. These sources do not establish a verified enquiry-to-sale conversion rate or a live lead queue. Do not add unsupported marketing-channel or staff-conversion rankings.

## 7. Services & warranty

### Services

Top: Booked visits, package visits, warranty visits. Middle: a wide team/weekday heatmap plus team bars. Bottom: bookings over time and next-14-days table.

**Heatmap:** `dashboard_scheduling_capacity`; rows `calendar_name`; columns `day_of_week_number` or the existing Weekday field; SUM `scheduled_event_rows`. Use the heatmap appearance, readable cell labels, and enough row height for all six Calendars. Do not classify all Sunday appointments as placeholders: historical Sunday work is valid.

**Team bars:** same source; `calendar_name`, SUM `scheduled_event_rows`. Use short display aliases for the full Calendar names without changing grouping. These are team Calendars, not independently verified technician productivity.

**Month/week/day trend:** `dashboard_team_workload`; metric SUM `bookings`; date-range dimension `service_date`.

1. Select the time series, open **Setup**, enable **Drill down**.
2. Use `month_start`, `week_start`, `service_date` as the meaningful time levels. Looker may also create broader Year/Year Month levels automatically.
3. On the chart-local month field, choose **Data type → Date & Time → Year Month**, label **Month**.
4. On the chart-local week field, choose **ISO Year Week**, label **Week**. The source week starts on Monday.
5. Keep service date as Date. Set the default drill level to Month.
6. Use chart header arrows to move Month → Week → Day and back. Set the header visible if staff cannot discover the arrows.
7. Keep missing/future dates as gaps, not zero completed jobs. Do not leave a daily-grain month-start chart that draws needles between artificial zero days.

**Implemented and tested:** month, ISO week and day rendering; the original weekday/team heatmap stayed intact. An attempted separate dimension selector was removed after it affected other charts. Use the native chart drill-down.

**Upcoming table:** `dashboard_upcoming_appointments`; retain its verified visit-date/count fields and fixed next-14-days scope. It must not disappear when a historical date range is selected. Bookings are not completed treatments, staff hours or available slots.

### Warranty

- Monthly warranty visits and share from `dashboard_service_monthly`.
- Share: `SUM(warranty_claim_event_rows) / SUM(scheduled_service_event_rows)`, with a zero-denominator guard.
- Return-interval bars from `dashboard_recurrence_monthly`: `recurrence_bucket`, SUM `recorded_warranty_signal_rows`; date `service_month`.
- Order the known intervals chronologically and keep unknown/review groups visible.

Use **Warranty visits** with a tooltip explaining Calendar labels; do not rename the count **Formal warranty claims**. A scheduled paid follow-up, a Calendar warranty marker and a formal claim-sheet entry are different records.

Warranty policy: commercial clients and standalone residential 1x have no warranty. Residential 3x has 30 days after the actual third service; delays/rescheduling do not automatically remove entitlement. Residential 4x/6x/12x is covered throughout the service period and 30 days after the final service. Any pest is covered within the eligible package. Reconciled 1x + Upsell 2x is one three-service programme.

## 8. Pests & packages

Main left: sales by pest. Main right: purchases by package. Bottom: pest × package heatmap and a small comparison table.

For date-filterable sales and purchase charts, use **Sales by area** with date `month_start`, dimensions `pest` / `package`, metrics SUM `sales_rm` / `sale_rows`.

For the package-fit matrix, use `dashboard_package_fit_matrix`: rows `pest_type`, columns `package_type`, SUM `package_rows`; optional `contract_type` dropdown. This source is a **fixed 2026 snapshot**, so isolate it from a historical date control and label its scope. Do not imply it follows the sales-chart date range.

Keep mixed-pest labels together and preserve Unspecified categories. Splitting a combined pest label into several rows must not multiply sales. Payment-link evidence is not proof of full payment; omit that metric from the main page unless its limitation is explained.

## 9. Areas & weather

### Areas

Top: selected-period Sales and purchases, plus location coverage. Main: district sales bars and a district table. A map is secondary and requires verified geographic fields.

- Source **Sales by area**: `district`, SUM `sales_rm`, SUM `sale_rows`; date `month_start`.
- Keep **Unassigned** in a coverage table. The assigned-district ranking does not represent all sales.
- Use counts/amounts, not a district ranking of model accuracy from a handful of cases.
- Optional spatial view: `dashboard_spatial_area`, aggregate centroids and service/return counts. These area cells are analytical bins, not official districts or customer points.
- Optional cluster sensitivity: `dashboard_spatial_cluster_summary`; single-select `radius_km` 1/2/5, default 2. Never sum across radii. Radius changes cluster grouping, not model accuracy.

Keep a crowded map out of the main path. Detailed area exploration already belongs on the website.

### Weather

Source `dashboard_weather_monthly`; date `service_month`; split by `event_group`.

- Left: prior-14-day rainfall comparison in mm.
- Right: prior-seven-day humidity comparison in %.
- Bottom: weather-covered visits, total visits and coverage for each month/group.

For period summaries, weight the existing means by `complete_prior_14d_weather_rows`; do not average monthly means equally. For example, create row-level `weighted_rain = avg_prior_14d_precipitation_mm * complete_prior_14d_weather_rows`, then use `SUM(weighted_rain) / SUM(complete_prior_14d_weather_rows)` with a zero-denominator guard. Apply the same verified denominator to the published humidity means.

Prior rainfall describes each appointment's earlier weather window, not total company rainfall. The current aggregate has no district/pest/flood dimensions, so those filters cannot be added to it. Weather associations do not prove that rain caused a return visit.

## 10. Payments

Management question: **What is recorded as paid, what remains, and which reminder dates need attention?**

This is a current snapshot. Do not apply the general historical sales-date filter to its financial totals.

Source `dashboard_recurring_payment_quality`:

| Display label | SUM field |
|---|---|
| Contract sales (RM) | `recorded_contract_value_rm` |
| Paid so far (RM) | `sales_total_recorded_paid_rm` |
| Remaining balance (RM) | `positive_recorded_remaining_balance_rm` |
| Reminders · next 7 days | `contracts_with_scheduled_reminders_next_7_days` |
| Missing reminder dates | `contracts_without_source_schedule` |

**Current chart:** horizontal stacked bars, dimension `billing_arrangement`, SUM paid and positive remaining balance. Legend **Paid (RM)** / **Remaining (RM)**. Give the left axis enough room for arrangement names. Configuration is saved; confirm its renderer loads before declaring the page complete.

**Reminder workload:** `dashboard_recurring_reminder_schedule`; date `reminder_date`; SUM `scheduled_reminder_date_rows`; optional breakdown `billing_arrangement`. Use a daily column chart and a date/arrangement/count table. Default today through the next 30 days. The view's arrangement-level seven-day card and daily reminder counts have different grains; do not call summed daily counts unique contracts.

**Missing schedules:** quality source by arrangement; SUM `contracts_without_source_schedule`. Keep other quality flags separate because they overlap. A row of zero review flags is not itself an action item.

The owner's reminder dates are already dates to contact clients; do not subtract another seven days. Green means the date passed, not paid, reminded or overdue. SALES deposit plus cumulative Balance Paid establishes the recorded paid amount. PAYMENTS is excluded. Do not infer instalment amounts or repeat the whole balance against every future reminder date. Paid plus positive remaining can differ from contract value when source records need review; do not force the figures to balance by hiding rows.

### Refunds

Add a compact all-records refund section, separate from recurring balances:

- Source `dashboard_refund_monthly`; SUM `recorded_refund_amount_rm` and `refund_source_rows`.
- Label **Recorded refunds (known amounts)** and show `amount_review_rows` / `date_review_rows` alongside.
- The 15 October checked snapshot had 56 undated records, RM24,672.30 in known amounts and one amount-review record. Treat these as a dated check, not hard-coded dashboard values.
- Do not draw a monthly refund trend while all dates are missing. Do not let a date control hide these records and produce a misleading zero.
- Do not subtract unallocated refunds from sales or label the result net revenue/profit. A recorded status is not bank-transfer verification.

## 11. Supporting Data checks

Use `dashboard_source_freshness`: source, extraction timestamp and MAX `hours_since_extraction`. Show the timezone. Use `dashboard_data_quality`: source, issue code, affected rows and source denominator. Do not sum overlapping issue counts into one total or repeat denominators across issue codes.

Show matching, weather and location coverage with summed numerators/denominators from `dashboard_service_monthly`. A failed refresh can leave older approved data visible; a working chart alone does not prove today's refresh succeeded.

Only show source-backed actions: missing schedules, missing/ambiguous links, unassigned locations, stale sources. Do not create warnings about treatment failure, overdue debt or staffing shortages from these aggregates alone.

## 12. Final checks — do these before calling it finished

1. Every page has a clear purpose and the requested charts. Remove empty decorative panels and duplicate explanations.
2. Compare cards with the same source and period; do not compare customer all-history groups with a monthly purchase count.
3. Test a populated date/segment filter, then reset. Check every affected chart; isolate fixed-snapshot and upcoming sections.
4. Test Services Month → Week → Day and back. Confirm the heatmap and future table stay valid.
5. Check recurring totals and seven-day reminders against the same published snapshot; preserve unknown amounts/dates.
6. Show Unspecified/Unassigned coverage. Keep October labelled partial while it is incomplete.
7. Check fonts at normal desktop zoom, table widths, chart label margins, all team rows, and chart legends.
8. Check no customer contacts, exact addresses or individual risk scores appear. Existing link-sharing permission is unchanged by this guide.
9. Refresh once using **More report actions → Refresh data**. If a chart stays blank, verify its source, fields, filters and rendering; do not mark it complete just because settings saved.
10. Keep a screenshot of each finished page. Model predictions/results belong to the separate validation process; this dashboard does not make the experimental model reliable.

## Current handoff

Overview has been refined and visually checked. Services' original heatmap is restored; its month/week/day trend has been implemented and exercised in viewer mode. The current payment chart is configured as horizontal stacked bars. Other pages still need the design and acceptance checks above. The report as a whole is not yet certified finished.
