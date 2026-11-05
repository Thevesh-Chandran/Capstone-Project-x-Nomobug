# Current dashboard handoff — 14 October 2026

The actual [Looker report](https://datastudio.google.com/reporting/590914e8-066b-4671-a130-7a62a3af435a) now has 14 pages. The project team is editing the live report at the owner's request. The older owner-build instructions below are historical checkpoints.

The current design uses a neutral canvas, dark text, blue/orange/purple/cyan/amber chart colours and pale-blue table headers. Generic introductions and repeated instruction blocks have been reduced. Images are not used as dashboard components. The desktop/laptop layout is the owner's current priority.

Added approved aggregate sources: `gold.dashboard_business_sales`, `gold.dashboard_business_services`, and `gold.dashboard_business_customers`. The Customers page shows all recorded history: 2,284 customer profiles, 162 repeat customers, RM229,528.66 repeat-customer sales and 130 identity-review groups. Repeat means two or more paid programmes, with reviewed linked upsells counted as one programme. Individual profiles remain in the private website. The separate model-area test still contains 100 held-out services and is not the population for business area rankings.

All 14 pages have received a content/design review. Verification is **not complete**: several native chart frames remain blank in the controlled browser, although their Looker BigQuery jobs complete without query errors. A normal-Chrome viewing check is pending. Do not claim that every chart renders or that dashboard acceptance has passed. Weather source verification found 20 monthly groups, 3,074 visits and 2,769 complete-weather visits; the bounded query processed 201,342 bytes. See [live verification](../outputs/business_implementation/20261014/live_verification.md), [weather source check](../outputs/business_implementation/20261014/weather_source_check.json), and [Looker job checks](../outputs/business_implementation/20261014/looker_weather_jobs.json).

Source age follows the last report data refresh: the published freshness view uses `CURRENT_TIMESTAMP()`. Reminder dates are staff reminder dates, not payment or sent-message confirmations. PAYMENTS remains excluded from contract balances. The report's existing link access is unchanged; contacts, exact locations and individual experimental scores remain excluded.

The current frozen prospective collection window is **10–30 October**, with full outcomes no earlier than **30 November**, subject to collection and outcome completeness checks. Earlier 5–27 October / 27 November dates below are superseded historical plans. The model remains experimental; dashboard refinements do not change its weights or evidence.

## Historical checkpoints — 4 October 2026

For step-by-step page settings and stakeholder decisions, use [the detailed dashboard build guide](CP2_DASHBOARD_BUILD_GUIDE.md). Read [the metric dictionary](CP2_METRIC_DICTIONARY.md) and [model explanation](CP2_MODEL_EXPLAINED.md) before interpreting charts.

The owner builds the Looker Studio report. The latest validated reporting release at handoff is `20261004125916e732f9`: 201 warehouse build/test steps and 16 independent KPI checks passed. Subsequent successful daily releases update the same stable Gold view names. Connect to `profound-keel-500007-s4.gold`, never to a dated `cp2r_...` candidate dataset. Keep source freshness visible using `dashboard_source_freshness`. Service summaries include the corrected reviewed 1x plus Upsell 2x programme. Both recurring-payment aggregate sources are deployed; PAYMENTS remains excluded from the recurring tracker.

| Management content | Stable Gold view | Interpretation |
|---|---|---|
| Sales value and packages sold | `sales_monthly_recorded` | Recorded package face value and countable package rows |
| Payments recorded | `payments_monthly_recorded` | Sheet payment-entry amounts, combined entries counted once |
| Scheduled and warranty-signal visits | `dashboard_service_monthly` | Recorded Calendar activity; formal claim rows have a different grain |
| Workload by date/team Calendar | `dashboard_scheduling_capacity` | Scheduled/recorded workload |
| Recorded return intervals | `dashboard_recurrence_monthly` | Source-backed interval buckets with denominators |
| Area and cluster patterns | `dashboard_spatial_area`, `dashboard_spatial_cluster_summary` | Aggregate geography; 1/2/5 km DBSCAN settings are sensitivity scenarios |
| Weather patterns | `dashboard_weather_monthly` | Observational comparison; show complete-weather coverage |
| Package/payment-link/refund context | `dashboard_package_fit_matrix`, `dashboard_payment_link_monthly`, `dashboard_refund_monthly` | Descriptive records; conversion and settlement require additional evidence |
| Source freshness and quality | `dashboard_source_freshness`, `dashboard_data_quality` | Extraction time, issue counts and denominators |
| Model evaluation | `dashboard_ml_evaluation` | Aggregate frozen v5 held-out results only |

The model page shows **selected v5 ExtraTrees depth 10**, a recorded corrective Calendar callback within days 1–30 after a matched paid service, and **100 held-out services with five callback-positive windows**. ROC AUC is 0.8905, average precision 0.3051, and the highest-risk 20 services contained four of five positives. Five positives are too few to establish a dependable gain. The evaluation view's 5,333 training rows belong to the held-out experiment; the separate prospective refit uses 5,695 mature services. Keep those populations distinct and report October collection coverage until future outcomes mature. See [current model evidence](CP2_CORRECTED_MODEL_CANDIDATES_V5.md).

The model page also needs a dated limitations note from the [1 October broad review](CP2_BROAD_MODEL_REVIEW.md): 37 additional contracts found no qualified replacement, and a separate 13-service/one-positive later-period check found zero positives in three reviews. This follow-up is not in the existing Gold evaluation view and uses a different historical fitting cutoff. Do not pool its metrics with the 100-service evaluation or present either result as completed October prospective performance.

The older [design specification](deferred/LOOKER_STUDIO_BUILD_SPEC.md) remains useful for layout. Its September status and proposed restricted customer/site history are historical planning, not approval to expose private detail. Use aggregate management sources for this report. Customer contact details, exact addresses/coordinates, raw Calendar descriptions and individual experimental scores stay private.

Before sharing, reconcile representative totals to Gold using the same dates and filters; calculate shares from summed numerators and denominators; test a populated filter and reset to All; check desktop and narrow-screen rendering; and verify company-approved viewer access and the absence of private fields. Show source freshness and model limitations. Add attention items only when an approved source supports them.

The October submission uses historical results and actual collection coverage. Complete future-outcome evaluation remains scheduled for 27 November. [Submission checklist](CP2_OCTOBER_SUBMISSION.md).

## Additional stakeholder requirement — recurring payments

The [4 October live recurring-payment review](CP2_RECURRING_PAYMENTS_REVIEW.md) confirms that the tab is an automatic positive-balance copy of SALES, with 174 matching rows including 30 recurring-arrangement candidates. Raw ingestion is included; validated instalment due dates, payment allocation, overdue amounts and reminder queues are **not implemented**. Existing dates are the owner-defined staff reminder schedule; they do not identify unpaid instalments or reminders already sent. Cancellation and conflicting custom notes need targeted review. Add this as a separate finance requirement before claiming the dashboard supports contract-payment reminders. Do not expose private contact details in the aggregate report or count the derived rows as additional sales/payments.

A read-only tracker implementation adds 34 sale/arrangement candidates, including two zero-balance historical cases. **Owner decision on 4 October: PAYMENTS is excluded from recurring tracking.** The current register and `dashboard_recurring_payment_quality` use only SALES recorded deposits/balance-paid amounts and remaining balances, plus Recurring Payments reminder dates. There is no payment timeline or actual last-payment date in the tracker. The aggregate sources are published to stable Gold in release `2026100404180522111f`, and the hosted reporting image is updated. Use them to show recorded amount/schedule coverage, not overdue balances or reminders actually sent. The private register stays outside this aggregate management report. The owner confirms source dates are staff reminder dates; green means only elapsed. Show upcoming scheduled reminders separately from paid progress. Do not add a lead-time offset or infer sent/paid status from green. Individual instalment allocation remains unavailable.


## Recurring payments page added - 4 October

Use [Page 11: recurring payments and staff reminders](CP2_RECURRING_PAYMENTS_DASHBOARD_GUIDE.md) for exact sources, fields, charts, filters and acceptance checks. `dashboard_recurring_payment_quality` adds recorded arrangement value, paid amounts, positive remaining balances and upcoming arrangement counts. `dashboard_recurring_reminder_schedule` adds daily future reminder workload. Both stable Gold sources were published in release `2026100404180522111f`, and the hosted reporting image was updated. The owner builds the Looker page. PAYMENTS is excluded, and green only means the reminder date has passed.

## Source/privacy audit checkpoint - 4 October

Use only the explicitly approved aggregate management sources in this handoff and the recurring-page guide. Gold also contains restricted intermediates: `dashboard_recurrence_windows`, `dashboard_warranty_package_metrics`, refund/claim fact views and spatial event/property views contain identifiers or hashes. Their names do not approve them for management report connections. Viewer access must be checked separately; the local release schema gate is not deployed yet. Stable materialized fact tables are older checkpoints, while approved aggregate wrappers point at the daily release. Model page: show historical results and **incomplete October collection**, not a promised complete future accuracy result. See [the project review](CP2_PROJECT_REVIEW_20261004.md).


## Current handoff — 4 October, 22:06 MYT

The complete guide and all 11 design mockups are in [the build pack](../outputs/dashboard_design/20261004_complete_guide/index.html), with a [written guide](../outputs/dashboard_design/20261004_complete_guide/CP2_dashboard_complete_build_guide.md). Labels use plain management language; exact source fields stay in build notes. Seventeen approved aggregate schemas were checked. Mockups are design references, not live company totals. Static navigation/assets and representative PNG layouts were checked; browser rendering was not verified because the browser disallowed local-file preview. The owner builds and checks the actual Looker report.

The owner's latest instruction replaces the October submission deadline with completion after the new future test. See [the declared test](CP2_OCTOBER5_TEST.md): 5–27 October collection, earliest complete evaluation 27 November. Earlier status paragraphs above remain historical checkpoints.
