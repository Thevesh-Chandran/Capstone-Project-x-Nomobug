# CP2 Implementation Guide

> Current progress and batch order: **[PROJECT_STATUS.md](PROJECT_STATUS.md)**.
> This older guide contains historical implementation notes below. Do not use its
> old Immediate Next Task or verification statements as current project status.

Paths and commands in this guide are relative to the repository root, not this folder.

## Project Direction

CP2 will implement the data engineering and analytics workflow proposed during CP1. The system should help Nomobug review service outcomes, repeat pest problems, warranty and refund patterns, treatment difficulty, spatial hotspots, weather-associated indicators, scheduling context, and upsell performance.

The selected stack is Python/pandas API extraction, BigQuery, dbt Core with `dbt-bigquery`, scikit-learn predictive modelling and DBSCAN, Cloud Run Jobs with Cloud Scheduler, and Looker Studio. GitHub Actions supports CI/deployment. Neon Free is retained as a manual fallback, not an automatic failover. Docker packages execution; dashboard users only need a browser. Billing-linked BigQuery targets low/no charges but zero spending cannot be guaranteed.

Use `planning/PROJECT_STATUS.md` for verified progress and `planning/CP2_SEP_NOV_IMPLEMENTATION_PLAN.md` for milestone dates. Older provider references within the dated plan are superseded by the current stack above. Sessions are at most one hour, and can pull future work forward. Deadline feasibility must be reviewed, not assumed.

## First Milestone: Understand the Real Data

Do not begin with dashboards or machine learning. Inspect current Google Sheets and Calendar API responses. Existing CSV exports are historical debugging references, not the primary pipeline input.

1. Inventory every usable source, sheet, tab, and Calendar.
2. Record column names, data types, date coverage, row counts, and update frequency.
3. Identify candidate keys such as customer ID, service reference, normalised phone number, service date, and area or postcode.
4. Measure missing values, duplicates, invalid dates, inconsistent labels, and unmatched records.
5. Create a confirmed data dictionary and source-to-target mapping.
6. Validate the selected free infrastructure against measured storage, runtime, privacy and access requirements before customer-data loading.

## Recommended Build Order

1. Data profiling and quality report.
2. Flexible source contracts and alias mappings.
3. One small end-to-end extraction and raw-loading pipeline.
4. Cleaned service, warranty, refund, payment, Calendar, area, and weather tables.
5. Tested analytical joins and dashboard-ready marts.
6. Historical weather enrichment and area/postcode lookup.
7. Recurrence windows, treatment difficulty, and hotspot analytics.
8. BI dashboards with day, week, and month filtering.
9. Scheduled refresh, pipeline logs, and recommendation log.
10. Required predictive-model and DBSCAN evaluation, privacy review and release evidence. No optional AI layer in the core build.

## Analytics Approach

- Descriptive analysis for service, revenue, warranty, refund, scheduling, and upsell trends.
- DBSCAN for spatial repeat-problem clusters when coordinate coverage is sufficient.
- Heatmap and DBSCAN visualisation; KDE is not a core requirement.
- Rainfall time-lag features for weather-associated analysis.
- Required predictive experiment: establish a defensible target, baseline, leakage-safe split and held-out evaluation; use an interpretable model such as logistic regression where appropriate. Insufficient labels require an explicit feasibility decision, not silent removal of the workstream.
- Recurrence-window and interval comparisons for the timing of repeat problems.
- Transparent rule-based treatment-difficulty and recommendation logic.

Historical warranty sample size is not evidence of current label sufficiency. Recheck eligible records and outcome coverage before model selection; avoid unnecessary complexity.

## Interpretation Rules

Use wording such as `weather-associated risk`, `higher observed risk`, `review indicator`, and `requires closer monitoring`. Technician-related results support management review and must not be presented as proof of blame. Weather indicators show association unless stronger causal evidence is established.

## Historical Data-Understanding Outputs — Live Recheck Pending

The initial profiling has produced:

- a source inventory;
- a sheet and column inventory;
- row counts and date coverage;
- missing-value and duplicate summaries;
- preliminary keys and relationships;
- a list of fields that should be retained, cleaned, derived, excluded, or manually reviewed.

## Immediate Next Task

Live `2026` extraction passed with 32,580 rows and 24 columns on 3 September. Run `python scripts/extract_prospects_2026.py` to review the newly added column mapping/completeness output. It preserves displayed values, header mapping and Sheet row positions, and prints labels/counts only. Eight synthetic extractor tests pass. Then approve cloud fields/access and implement the first transactional Neon Bronze load with count, rerun and failure checks. No CSV dependency or separate practice dataset. Expand sources only after this slice passes.

Verified by student output: local Python/database imports and a Python query returning six Neon schemas. Not yet verified: live API-to-Neon loading, PostgreSQL dbt adapter, scheduled execution, dashboard, predictive model or DBSCAN. The old `profile_prospects_all_rows.py` drops all-blank rows and does not retain original Sheet row numbers; do not treat it as a production loader unchanged.

## Current Source-Audit Result

The CP1 proposal, logbook, and Gantt workbooks remain preserved locally under the ignored `docs/` folder. Read-only OAuth access has confirmed two Google Sheets workbooks containing sixteen tabs and six shared Nomobug Calendars. Full local snapshots and profiles have been generated under the ignored `data/raw/` and `data/profiles/` folders.

The confirmed source inventory and profiling summaries are stored in `config/`. The canonical dictionary remains a draft until the observed columns, business meanings, candidate keys, and cross-source relationships are reviewed with Nomobug. Fields still marked as unconfirmed must not be treated as authoritative.

## Safe Google Access

Do not paste credentials, access tokens, API keys, customer data, spreadsheet IDs, or Calendar IDs into chat, source code, commits, screenshots, or the tracked CSV templates.

Private Google Sheets and Calendar data normally require OAuth 2.0 or a service account with explicit access; an API key alone does not grant access to private company data. The existing Calendar prototype uses an OAuth desktop flow. For CP2, keep the downloaded OAuth client JSON and generated token JSON outside version control, preferably in the ignored `secrets/` folder or another protected local folder.

For a new source or renewed setup, the initial inventory should be metadata-only. Existing historical inventory is available; do not repeat onboarding unnecessarily:

1. List accessible spreadsheets, sheet tabs, and header rows without exporting full records.
2. List accessible calendars and their IDs without exporting event descriptions.
3. Confirm timezones, date coverage, ownership, update frequency, and approximate row or event counts.
4. Select a small date window and create an anonymised profiling sample locally.
5. Record the confirmed structures in local working copies before updating the tracked templates.

Only after those checks should the project extract full local snapshots or begin the first end-to-end pipeline.

### Local setup sequence

1. In Google Cloud, enable the Google Sheets API and Google Calendar API.
2. Reuse the existing authorized OAuth client/token if valid. Only troubleshoot or create a replacement client when required; do not overwrite the working credentials blindly.
3. Save the file locally as `secrets/google_oauth_client.json`. This folder is ignored by Git.
4. Copy `config/google_source_ids.example.json` to `secrets/google_source_ids.json` and add only approved spreadsheet IDs to the local copy.
5. Run `python scripts/inventory_google_sources.py`. The browser consent flow requests read-only Sheets and Calendar access.
6. Review the ignored output at `data/profiles/google_source_metadata.json` before any row-level extraction.

The discovery output records spreadsheet titles, tab names, tab grid settings, Calendar names, Calendar timezones, and access roles. It does not retrieve Sheet cell values, Calendar events, or event descriptions.

### Local source profiling

For a simple Google Colab-style experience in local Jupyter or VS Code, open these notebooks and run each cell from top to bottom:

- `notebooks/01_prospects_2026_b2b_profile.ipynb`
- `notebooks/02_sales_payments_profile.ipynb`
- `notebooks/03_calendar_events_profile.ipynb`

They use ordinary pandas DataFrames and load every populated source row. Only small previews are displayed so the notebook remains responsive. Before committing after a local run, clear all notebook outputs because previews can contain private company data.

The equivalent command-line scripts are:

The following simple scripts load all populated Sheet rows or all historical Calendar event occurrences in the configured finite date window:

```powershell
python scripts/prototypes/profile_prospects_all_rows.py
python scripts/prototypes/profile_session_payment_all_rows.py
python scripts/prototypes/profile_calendars_all_events.py
```

- `profile_prospects_all_rows.py` reads the two selected tabs in `Prospects List - Nomobug`: `2026` and `B2B FOLLOW UP`.
- `profile_session_payment_all_rows.py` reads the selected operational tabs in `SESSION & PAYMENT (NMB)- CHIA` and excludes `LTV`.
- `profile_calendars_all_events.py` follows Calendar pagination for all six confirmed Nomobug calendars from 2000-01-01 through today.

Raw CSV extracts are written only to ignored `data/raw/` folders. Aggregate column profiles and source summaries are written to ignored `data/profiles/` folders. Do not move raw outputs into a tracked directory.
