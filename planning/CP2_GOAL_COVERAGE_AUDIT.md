# CP2 goal coverage audit

Reviewed against the CP1 proposal `Thevesh AL Chandran_24017717_proposal.pdf`,
the current `planning/cp2_scope.md`, and the deployed dbt/Python structure on
15 September 2026. The proposal is historical context; the current scope and
owner-confirmed operating rules take precedence. Current updates were reviewed
on 28 September 2026; old dated evidence below remains historical context.

## Objective coverage

| CP1 objective | Current evidence | Status | Remaining work |
|---|---|---|---|
| Review BI, pest decision-support, service-quality, weather-risk, spatial and explainable methods | Proposal literature review, method notes, project scope and interpretation rules are preserved | In progress as a report activity | Finish the final literature/method discussion and connect each chosen method to measured project evidence |
| Design a weather-aware architecture integrating Sheets, Calendar, service, claims, refunds, payments, upsell and weather | Live Sheets/Calendar inventory; BigQuery Bronze/Silver/Gold/Quality layers; source authority rules; sanitized geocoding and Open-Meteo enrichment | Implemented for the current prototype | Add the production run log, last-success publication rule and hosted execution |
| Develop a tested CP2 ELT prototype with contracts and quality checks | Python extraction/loaders, preserved Bronze snapshots, dbt models/tests, matching regression tests, spatial/weather checks and local tests; local API-to-temporary-BigQuery model scoring and failure-preserving run log | Local model path implemented; Gold refresh remains pinned | Governed fresh-source API-to-Gold release, hosted execution and unattended credential recovery |
| Implement descriptive/diagnostic and selected predictive/prescriptive indicators | Service/package warranty marts, monthly source-record marts, recurrence/scheduling/refund/package-fit/difficulty marts, historical weather-lag features, property-level DBSCAN sensitivity, and a time-held-out weather/team/operational model comparison | Implemented as a non-production feasibility prototype | Add the recommendation decision log; predictive release remains rejected until stronger outcome and treatment-quality evidence exists |
| Evaluate pipeline, dashboard usability, insight usefulness and output reliability | Row/column preservation, reconciliation and dbt/Python tests; 12 independent business KPI row/month checks against real pinned Bronze/Gold sources; live model refresh test | Partially implemented | Reconcile newly pinned Gold after refresh, Looker usability tasks/feedback, privacy release check and complete future model/cluster evaluation evidence |

## What is already aligned

- Google Sheets and the six Google Calendars are the live source scope. Bronze
  keeps source values and row/event positions; Silver and Gold do not silently
  delete ambiguous records.
- SALES identifies a package/sale, not a unique person. A repeated phone number
  can represent a different property or a later sale. Calendar dates remain the
  operational service dates; a Calendar entry is not completion proof.
- Calendar matching now uses invoice/email/phone, guarded title/session/date,
  closed-date anchors, and address/name context for shared-phone properties.
  Name-only matching is not automatic.
- Warranty candidates include post-package sequences such as `4/3` and `5/3`
  and explicit warranty/claim/callback visits. Formal WARRANTY CLAIM rows stay
  at their own grain and are not multiplied by Calendar events.
- Refund bank details, raw contacts, full addresses and raw Calendar text are
  retained only where needed for controlled processing and are not projected
  into reporting Gold views.
- Weather is an approximately 9 km Open-Meteo reanalysis enrichment with local
  grid features and an explicit service-region mean fallback for ML coverage.
  Current outputs use association language and expose scope rather than
  presenting weather as causation.
- Spatial outputs use sanitized coordinates and property-grain DBSCAN sensitivity checks. A
  cluster or heatmap is not a pest-spread radius or a claim that every event was
  completed.

## Planned in the proposal but not silently claimed as complete

1. **Recurrence windows:** a provisional package/property-aware interval view now
   uses the proposal buckets (0–7, 8–14, 15–30, 31–60, 61+ days). Planned
   package sessions remain separate from warranty/complimentary/extra signals.
   It still needs live validation against owner examples.
2. **Treatment difficulty:** separate warranty, non-warranty additional-visit
   and package-refund context shares are available. The earlier equal-weight
   score counted overlapping signals and is now withheld pending validation.
3. **Scheduling capacity:** a provisional daily/Calendar workload mart now
   separates normal, warranty, complimentary/extra and unmatched event rows.
   It is not technician capacity or completed-treatment hours.
   Technician attribution is also not yet a validated analytical dimension;
   raw technician fields remain preserved for later review.
4. **Refund analysis:** a provisional monthly source-record summary now keeps
   linked/unmatched, status, date and amount-review counts. Every refund row is
   preserved and linked where possible, but a finance KPI or root-cause rate is
   not approved yet.
5. **Upsell/package fit:** a provisional descriptive package/pest/contract matrix
   and PAYMENT LINK monthly source-record view now show payment-entry evidence,
   Calendar warranty signals and recorded link outcomes. The owner-confirmed
   PAYMENTS completion-status column is no longer maintained. PAYMENT LINK WON
   remains a recorded outcome; rejected/no-response offer coverage has not been
   established. Descriptive package/payment-link
   reporting is possible; predictive fit must wait for a defensible label.
   Prospect/B2B funnel reporting is likewise descriptive until the link, booking
   and outcome semantics are reconciled.
6. **Predictive model:** corrected v5 ExtraTrees predicts recorded corrective
   Calendar callbacks during days 1–30 after a matched paid service. It is
   distinct from warranty entitlement; recorded commercial callbacks remain
   valid outcomes. On a newer 100-service retrospective test, its top 20 risk
   scores found four of five positive windows, versus three for the corrected
   reference (AUC 0.891 versus 0.813). The interval includes no gain. A local
   live feed now scores recent services; the first run produced 205 private
   scores but zero prospective logs. Complete future outcomes and reliable
   first-service detection have not been established. [Current guide](CP2_START_HERE.md).
7. **Recommendation log:** no management-action log has been published yet.
   Future rules must store the reason, evidence, confidence/review label, action
   and later outcome instead of embedding unexplained text in a chart.
8. **Refresh/deployment:** Local read-only model refresh, two-minute Windows
   Calendar trigger, SHA-verified private run logs, exact-retry prospective
   logging and last-success indicator are implemented. Hosted Cloud Run Jobs +
   Scheduler, GitHub Actions CI, unattended OAuth handling, permanent fresh
   Gold publication and Looker Studio are not deployed.
9. **Evaluation:** 12 business KPI checks independently reconcile real pinned
   Bronze and Gold rows/monthly totals. Fresh Sheets differ from pinned Gold,
   so those totals are not current. Automated tests and reconciliation do not
   establish dashboard usefulness; user tasks/feedback, the refreshed Gold
   acceptance check and a privacy-safe release check remain required.
10. **Flood/current-warning context:** observed nearby Copernicus GFM context and
    separate GDACS regional flood reports now enrich the experimental callback
    dataset. Their 35 comparisons did not improve development selection; only
    37 anchors have reliable GFM observations and none contains detected flooding.
    See [the flood evaluation](archive/model_evaluations/CP2_FLOOD_MODEL_EVALUATION.md). No live warning
    feed or confirmed property flood indicator is implemented. Rainfall fields
    remain distinct from flood observations.

## Proposal choices superseded by the current scope

Apache Airflow, Apache Superset/Preset, KDE, Ollama, LTV, additional ML
algorithms and a full CRM/payment-gateway build are not core deliverables now.
The active scope selects BigQuery, dbt Core, Cloud Run Jobs + Cloud Scheduler,
GitHub Actions CI, Looker Studio, one defensible predictive experiment and
DBSCAN. A proposal option is not evidence that the component has been built.

## Remaining acceptance order

1. Monitor local future prediction coverage through the frozen cohort. Retain
   missed windows explicitly and evaluate complete Calendar outcomes only after
   26 November; no backfilled score counts as future evidence.
2. Refresh the governed Bronze/Silver/Gold source pins, reconcile the resulting
   current KPIs, and review recurrence, scheduling, treatment-difficulty,
   refund and upsell examples at their correct grains with the owner.
3. Harden hosted execution, unattended read-only sign-in recovery, CI, retention
   and privacy review. The local runner depends on this PC being awake.
4. Build and test the deferred Looker Studio dashboard using approved reporting
   views after the core data and model acceptance checks.

This audit is a coverage checklist, not a claim that the remaining work is
complete. It prevents the dashboard from implying unique customers, completed
treatments, cash settlement, causal weather effects or predictive accuracy that
the source evidence does not support.
