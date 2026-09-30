# Current dashboard handoff — 1 October 2026

For step-by-step page settings and stakeholder decisions, use [the detailed dashboard build guide](CP2_DASHBOARD_BUILD_GUIDE.md). Read [the metric dictionary](CP2_METRIC_DICTIONARY.md) and [model explanation](CP2_MODEL_EXPLAINED.md) before interpreting charts.

The owner builds the Looker Studio report. The latest validated reporting release at handoff is `2026093011124282606c`; subsequent successful daily releases update the same stable Gold view names. Connect to `profound-keel-500007-s4.gold`, never to a dated `cp2r_...` candidate dataset. Keep source freshness visible using `dashboard_source_freshness`.

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

The older [design specification](deferred/LOOKER_STUDIO_BUILD_SPEC.md) remains useful for layout. Its September status and proposed restricted customer/site history are historical planning, not approval to expose private detail. Use aggregate management sources for this report. Customer contact details, exact addresses/coordinates, raw Calendar descriptions and individual experimental scores stay private.

Before sharing, reconcile representative totals to Gold using the same dates and filters; calculate shares from summed numerators and denominators; test a populated filter and reset to All; check desktop and narrow-screen rendering; and verify company-approved viewer access and the absence of private fields. Show source freshness and model limitations. Add attention items only when an approved source supports them.

The October submission uses historical results and actual collection coverage. Complete future-outcome evaluation remains scheduled for 27 November. [Submission checklist](CP2_OCTOBER_SUBMISSION.md).
