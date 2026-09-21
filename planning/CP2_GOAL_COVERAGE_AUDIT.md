# CP2 goal coverage audit

Reviewed against the CP1 proposal `Thevesh AL Chandran_24017717_proposal.pdf`,
the current `planning/cp2_scope.md`, and the deployed dbt/Python structure on
15 September 2026. The proposal is historical context; the current scope and
owner-confirmed operating rules take precedence.

## Objective coverage

| CP1 objective | Current evidence | Status | Remaining work |
|---|---|---|---|
| Review BI, pest decision-support, service-quality, weather-risk, spatial and explainable methods | Proposal literature review, method notes, project scope and interpretation rules are preserved | In progress as a report activity | Finish the final literature/method discussion and connect each chosen method to measured project evidence |
| Design a weather-aware architecture integrating Sheets, Calendar, service, claims, refunds, payments, upsell and weather | Live Sheets/Calendar inventory; BigQuery Bronze/Silver/Gold/Quality layers; source authority rules; sanitized geocoding and Open-Meteo enrichment | Implemented for the current prototype | Add the production run log, last-success publication rule and hosted execution |
| Develop a tested CP2 ELT prototype with contracts and quality checks | Python extraction/loaders, preserved Bronze snapshots, dbt models/tests, matching regression tests, spatial/weather checks and local tests | Implemented locally and in BigQuery | One integrated API-to-Gold command, scheduled execution, failure recovery and refresh evidence |
| Implement descriptive/diagnostic and selected predictive/prescriptive indicators | Service/package warranty marts, monthly source-record marts, recurrence/scheduling/refund/package-fit/difficulty marts, historical weather-lag features, property-level DBSCAN sensitivity, and a time-held-out weather/team/operational model comparison | Implemented as a non-production feasibility prototype | Add the recommendation decision log; predictive release remains rejected until stronger outcome and treatment-quality evidence exists |
| Evaluate pipeline, dashboard usability, insight usefulness and output reliability | Row/column preservation, reconciliation and dbt/Python tests; explicit limitation documentation | Partially implemented | Manual KPI reconciliation, Looker usability tasks/feedback, privacy release check, refresh test, and model/cluster evaluation evidence |

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
6. **Predictive model:** the selected v2 target is a recorded Calendar warranty
   signal within 60 days after a unique three-session completion anchor. Model
   choice uses three pre-2026 walk-forward folds; the selected balanced random
   forest averages ROC AUC 0.554 and average precision 0.385 across those folds.
   The 405-row 2026 reporting cohort has ROC AUC 0.622 and average precision
   0.434, but it was inspected during earlier development and is not a pristine
   final holdout. The top-half priority-review band has 48.3% precision and
   65.3% recall; the top-20% tier is unsupported and disabled. Retain this as a
   feasibility result, not production scoring or evidence of causation.
7. **Recommendation log:** no management-action log has been published yet.
   Future rules must store the reason, evidence, confidence/review label, action
   and later outcome instead of embedding unexplained text in a chart.
8. **Refresh/deployment:** Cloud Run Jobs + Scheduler, GitHub Actions CI,
   unattended OAuth handling, a last-success indicator, rollback/retention and
   Looker Studio are planned but not deployed.
9. **Evaluation:** automated tests are evidence of pipeline correctness, not
   evidence of dashboard usefulness. Manual spreadsheet reconciliation, user
   tasks/feedback and a privacy-safe release check remain required.
10. **Flood/current-warning context:** the proposal listed flood or warning
    indicators as optional weather context, but no approved flood-warning source
    is loaded. Rainfall fields must not be presented as flood observations.

## Proposal choices superseded by the current scope

Apache Airflow, Apache Superset/Preset, KDE, Ollama, LTV, additional ML
algorithms and a full CRM/payment-gateway build are not core deliverables now.
The active scope selects BigQuery, dbt Core, Cloud Run Jobs + Cloud Scheduler,
GitHub Actions CI, Looker Studio, one defensible predictive experiment and
DBSCAN. A proposal option is not evidence that the component has been built.

## Safe implementation order from this audit

1. Live-validate the published recurrence-window and scheduling-capacity marts
   with owner examples and explicit denominators/package-property safeguards.
2. Validate separate treatment-difficulty components before selecting weights
   and testing the sensitivity of any composite score.
3. Validate the refund and descriptive upsell/package marts; keep unsupported
   predictions flagged as unavailable.
4. Freeze the predictive target, run the baseline and held-out evaluation, or
   record an explicit infeasibility decision with evidence.
5. Add the integrated refresh/run log and failure-preserving publication path.
6. Wire Looker Studio to approved Gold views, then perform manual KPI checks,
   privacy review and user testing.

This audit is a coverage checklist, not a claim that the remaining work is
complete. It prevents the dashboard from implying unique customers, completed
treatments, cash settlement, causal weather effects or predictive accuracy that
the source evidence does not support.
