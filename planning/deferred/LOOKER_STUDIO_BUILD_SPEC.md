# Nomobug Looker Studio build specification

**Current handoff (1 October):** Start with [the current dashboard handoff](../CP2_DASHBOARD_HANDOFF.md). It supersedes historical source-readiness and model statements below. Stable Gold views are refreshed by the daily governed cloud release.

Status (16 September 2026): user created the Looker report, connected 13 sources,
and built a first overview draft. User approved the business-focused redesign
below. The older page instructions further below are retained as source reference;
the revised navigation and priorities supersede their page order and card layout.

## Approved dashboard redesign — 16 September 2026

Design for management questions and actions. References supplied by the user
(Zoho FSM screenshots and Insectram text) are inspiration, not a request to
replicate their entire operational product or import their claims.

| Page | Business question | Existing foundation | Work still required |
| --- | --- | --- | --- |
| Business overview | How are we doing; what needs attention? | Sales, payments, service monthly views | Comparable-period changes; evidence-backed attention queue |
| Sales & customers | Where do enquiries and sales come from? | Prospect Silver, sale facts, package-fit and payment-link views | Approved enquiry/source aggregates; cross-source conversion and missing-WON reconciliation; customer identity validation |
| Services & teams | What is scheduled and how is work distributed? | Daily calendar workload view | Fresh upcoming-event detail; validated appointment statuses before completion/cancellation KPIs |
| Pest recurrence & hotspots | Where do problems keep returning? | Recurrence, treatment groups, area and cluster views | Site-level drill-through; explain denominators and sample sizes |
| Customer & site history | What happened at this property under this package? | Linked sale/payment/calendar facts | Restricted detail source and navigation; preserve customer/site/package identities and combined-payment uncertainty |
| Weather & seasonal patterns | How do recorded problems vary with weather/time? | Monthly weather associations and cached features | Coverage-aware comparisons; additional history for stronger seasonal conclusions |

Supporting pages: Data quality and Model evaluation. Matching coverage, geocoding
coverage, undated refunds and model scores belong here rather than headline cards.
Keep weather coverage visible beside weather comparisons where it affects meaning.

### First overview release

Five cards with plain labels and definitions:

| Label | Source | SUM metric | Date dimension |
| --- | --- | --- | --- |
| Sales value | sales_monthly_recorded | recorded_package_face_value_rm | closed_month |
| Payments recorded | payments_monthly_recorded | recorded_payment_entry_amount_rm | payment_month |
| Packages sold | sales_monthly_recorded | countable_package_rows | closed_month |
| Scheduled visits | dashboard_service_monthly | scheduled_service_event_rows | service_month |
| Warranty visits | dashboard_service_monthly | warranty_claim_event_rows | service_month |

Sales value means recorded eligible package face value. Payments are payment
entries, with combined amounts counted once. Packages sold is not unique customers.
Warranty visits means Calendar entries classified under the agreed warranty rules;
neither service count is proof of completed treatment.

Below the cards: separate sales/payment trends, scheduled and warranty visit
trends, then a Needs attention section when its record-level evidence is built.
Do not populate a fabricated or empty-zero attention queue while it is unavailable.
Do not stack normal_package_service_event_rows with warranty_claim_event_rows:
current SQL predicates can overlap. Derive mutually exclusive categories first.

Use 2026 as reporting-year scope with month selection and visible source freshness.
Default comparisons should use the latest complete common reporting month only
after source coverage is verified. Partial-month comparisons require equal elapsed
periods and daily data; monthly aggregates cannot establish that alignment.
Customer timelines can show prior-year context without changing selected-year KPIs.

Customer/site details are a planned restricted management view, not yet approved
for inclusion in the existing aggregate release sources. Match customer identity,
package closing dates, title/site evidence and actual visit location separately.
Shared phones do not merge branches; a changed visit address does not by itself
change package ownership. Preserve explicitly confirmed exceptions.

Keep current Looker charts for reuse. First revise overview cards and labels;
build missing Gold measures before requesting more manual chart construction.
No dispatch editing, live technician GPS, invoicing workflow or automated risk
decisions are implied by this dashboard redesign.

## Earlier source and metric reference

Reporting period is calendar year 2026.

## Audience and use

The primary audience is Nomobug management. The report supports weekly workload
review and monthly service, warranty, location, weather, sales/payment and refund
review. It is decision support, not a CRM, proof of treatment completion, proof
of cash settlement, or an automated customer-risk system.

Connect Looker Studio only to the aggregate Gold views in the current handoff,
including the explicitly listed sales and payments monthly views.
Do not connect the report to Bronze, restricted Silver, raw Calendar text, exact
event coordinates, or the experiment prediction table.

## Page 1 — Management overview

Use `gold.dashboard_service_monthly` for the service trend:

- scorecards: scheduled service entries, recorded warranty-signal entries,
  matched-to-sale entries, and warranty-signal share;
- monthly combo chart: scheduled entries as bars and warranty-signal share as a
  line;
- coverage cards: heatmap-eligible entries and warranty signals with complete
  prior-14-day weather.

Use `gold.sales_monthly_recorded`, `gold.payments_monthly_recorded` and
`gold.dashboard_refund_monthly` as separate cards/charts. Do not blend their
amounts into revenue or net cash: SALES is recorded package face value, PAYMENTS
is recorded payment-entry value, and REFUND status is not bank-settlement proof.

## Page 2 — Service and recurrence

- `gold.dashboard_recurrence_monthly`: stacked monthly bars by
  `recurrence_bucket`, using `recorded_warranty_signal_rows`. This source already
  excludes planned package visits and generic extra entries.
- `gold.dashboard_scheduling_capacity`: date/calendar heat table or time series
  using `scheduled_event_rows`, with warranty and complimentary rows as separate
  components. Label it scheduled/recorded workload, not completed jobs or staff
  capacity hours.
- `gold.dashboard_treatment_difficulty`: comparison table for groups with
  `sufficient_volume_for_comparison = true`. Show warranty, non-warranty extra
  visit and linked-refund shares separately. Do not show the null composite score.

## Page 3 — Spatial and weather

Use `gold.dashboard_spatial_area` for the management map:

- geography: `area_centroid_latitude` + `area_centroid_longitude`;
- bubble size: `scheduled_service_event_rows`;
- colour: `repeat_signal_share`;
- tooltip: scheduled entries, recorded warranty signals and matched sale records.

Each point is a geohash-5 analytical area representing several kilometres and
already requires at least five scheduled entries. It is not a customer property
coordinate and its visual bubble radius must not be described as pest spread.

Use `gold.dashboard_spatial_cluster_summary` for DBSCAN sensitivity:

- filter/control: `radius_km` with 1, 2 and 5 km options;
- map or table: cluster centroid, `distinct_service_properties` and
  `recorded_warranty_signal_rows`;
- optional context: complete-weather rows and average prior-seven-day weather.

Clusters require at least three distinct properties, so repeated callbacks at
one address cannot manufacture a hotspot. The 1/2/5 km values are alternative
DBSCAN neighbour-distance assumptions. They
do not mean pests travel that radius. Do not combine all three settings into one
cluster count; compare them as sensitivity scenarios.

Use `gold.dashboard_weather_monthly` for a two-series monthly comparison between
recorded warranty signals and other scheduled service entries. Weather means use
only complete prior-14-day windows; always show `complete_weather_coverage_share`
beside the averages. Label the result an Open-Meteo reanalysis association, not
property weather or a causal driver.

## Page 4 — Package, payment-link and refund evidence

- `gold.dashboard_package_fit_matrix`: package rows, recorded face value,
  payment-entry evidence rate, scheduled entries and warranty-signal share by
  pest/package/contract. This is descriptive package-fit evidence, not an upsell
  prediction or rejected-offer model.
- `gold.dashboard_payment_link_monthly`: monthly link rows and recorded `WON`
  outcomes. Do not call this conversion until the cross-source funnel denominator
  is reconciled.
- `gold.dashboard_refund_monthly`: recorded refund rows/amounts, with date, amount,
  status and unmatched-ID review counts visible. Do not call `COMPLETE` cash paid.

## Page 5 — Predictive experiment evaluation

Use only aggregate evaluation outputs, never package-level reporting scores.
Show the selected model, ROC AUC, average precision, Brier score, reporting
population and positive count. Display the status prominently as `experimental
priority-review ranking`. Use `gold.dashboard_ml_evaluation` for the selected
v5 ExtraTrees depth-10 model and corrected reference. The held-out population
contains 100 services and five callback-positive windows; the selected model
found four positives among the highest-risk 20 services. Its ROC AUC is 0.8905
and average precision is 0.3051. The small positive sample prevents a dependable
improvement claim.

The target is a recorded corrective Calendar callback within days 1–30 after
a matched paid service, scored immediately after its scheduled end. Contractual
warranty eligibility is separate. Show aggregate evaluation and limitations;
keep individual experimental risk scores private. Follow the current handoff
for the separate October collection and November outcome-evaluation dates.

## Controls and metric policy

- Default date range: 1 January–31 December 2026. Do not include October or other
  months outside 2026 merely because a later Calendar event exists.
- Use date controls only on sources containing the relevant month/date field.
  Looker controls do not reliably cross unrelated data sources without blending.
- Keep calendar, pest, package, contract and DBSCAN-radius filters on the pages
  where those dimensions exist; do not fabricate missing dimensions through joins.
- Recompute shares from their numerator and denominator fields. Do not average
  subgroup percentages or sum distinct-package counts across overlapping groups.
- Preserve null months/review categories in finance exception tables; null does
  not mean zero.

## Privacy and release gate

The report must not expose names, phone numbers, emails, addresses, refund bank
details, raw Calendar descriptions, exact service-event coordinates, or package-
level experimental scores. Use owner-only editing and company-approved viewer
access. Before sharing, verify every page at desktop and narrow width, test one
populated filter and reset to All, reconcile representative totals to BigQuery,
and confirm source labels/caveats remain visible.
