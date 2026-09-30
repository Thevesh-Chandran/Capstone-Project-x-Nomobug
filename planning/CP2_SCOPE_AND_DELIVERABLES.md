# Nomobug CP2 scope and deliverables

Repository-relative paths are used throughout.

## System Goal

Build a web-based analytics decision-support system that combines Nomobug's Google Sheets, Google Calendars, weather data, predictive modelling, and spatial clustering.

## Five Essential Business Questions

1. How many prospect interactions, unique prospects, repeated conversations, and B2B inspection bookings are recorded?

2. What sales were closed, how much money was received, and what outstanding balances remain?

3. What services actually occurred according to Google Calendar, broken down by date, pest, area, package, and team?

4. Where and when are warranty claims, repeat pest problems, refunds, and spatial hotspots occurring, and what weather patterns are associated with them?

5. Which eligible cases have higher predicted risk, what evidence contributes to that result, and how reliable is the prediction?

## Required Sources

### Prospects

- 2026
- B2B FOLLOW UP

### Session and Payment

- SALES
- PAYMENTS
- PAYMENT LINK
- WARRANTY CLAIM
- REFUND
- Recurring Payments
- Commercial Clients

### Operations

- All six Nomobug Google Calendars
- Open-Meteo historical weather

## Source Authority Rules

- Google Calendar is authoritative for scheduled/recorded service dates; a confirmed event alone does not prove treatment was completed.
- SALES is authoritative for sales, package, customer type, payment status, and balance information.
- PAYMENTS represents individual recorded payments. Its old completion-status column is no longer maintained and must not be used to decide whether money was received; malformed/missing amounts still need review.
- PAYMENT LINK represents customers who were sent a payment link.
- Repeated prospect phone numbers are not automatically duplicates.
- Commercial Clients and Recurring Payments must not duplicate SALES facts.
- LTV is excluded.
- Refund bank details are excluded from analytics and dashboards.

## Required Technical Components

- Python and pandas extraction
- BigQuery primary warehouse datasets: Bronze, Silver, Gold, Quality, Audit, and Analytics ML. Neon Free PostgreSQL retained as a manually selected fallback; no automatic failover or dual-write.
- dbt Core with the BigQuery adapter for primary transformations, documentation, and tests. PostgreSQL-specific SQL remains fallback-only.
- Predictive modelling with a baseline and held-out evaluation
- DBSCAN clustering with parameter and sensitivity evidence
- Cloud Run Jobs with Cloud Scheduler for the production batch pipeline, subject to cost and authentication checks
- GitHub Actions for CI and deployment
- Looker Studio for the management dashboard, using approved reporting views
- Dockerfile for pipeline packaging and reproducibility
- Automated quality checks
- Pipeline run logging
- Privacy-safe dashboard views

## Implementation Constraints — 3 September 2026

- User now permits a billing-linked BigQuery design while targeting a $0 bill. Billing-enabled usage carries residual charge risk; query quotas and local guards are not a guaranteed spending cap. Verify billing and cost controls with the user before uploads; no automatic upgrades or trial-dependent hosting.
- Up to one hour of student time daily, including learning and debugging. Pull work forward when possible; September 30, October 31 and November 30 remain milestone deadlines, subject to explicit feasibility/risk review rather than a guaranteed delivery claim.
- Live Google Sheets/Calendar APIs are the primary source. CSV snapshots are optional debugging/backups, not required manual inputs.
- BigQuery Bronze/Silver and initial Gold facts have been deployed in asia-southeast1. Cloud Run/Scheduler are selected for later production work but are not deployed. Neon remains a manual fallback; quota failure stops work for a deliberate fallback decision.
- Preserve every source observation and its original row position before transformations. Distinguish genuine repeat enquiries, exact repeats, blank/template rows and reload duplication.
- Free-plan limits, privacy approval for third-party storage, unattended OAuth, model labels and coordinate availability must be validated. Do not silently remove predictive ML or DBSCAN when feasibility is weak.
- Business/dashboard areas remain required; related areas may share dashboard pages. No additional model or decorative chart work before core acceptance checks pass.
- Follow `planning/CP2_OCTOBER_SUBMISSION.md` for current acceptance status and `planning/CP2_PROJECT_HISTORY.md` for older checkpoints. The dated plan is a milestone guide; its older platform references are superseded by the current scope and status.

## Required Dashboard Areas

1. Executive overview
2. Prospects and B2B funnel
3. Sales and payments
4. Service operations
5. Warranty and refunds
6. Weather and recurrence
7. Heatmap and DBSCAN hotspots
8. Predictive analytics
9. Recommendations
10. Data quality and refresh status

## Excluded From the Core Build

- LTV
- Apache Airflow
- Supabase
- FastAPI
- Power BI
- Tableau
- Preset Starter / Apache Superset
- Metabase
- Streamlit
- Self-hosted Superset
- Ollama or generative AI
- Additional ML algorithms unless the required model is complete
- KDE or additional clustering methods unless DBSCAN is complete

## Completion Rule

A component is complete only when:

- its output is reproducible;
- its acceptance test passes;
- its business meaning is documented;
- its privacy controls are checked;
- its limitations are stated; and
- I can explain what the code or platform configuration does.
