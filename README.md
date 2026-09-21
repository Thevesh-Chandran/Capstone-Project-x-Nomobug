# Nomobug Analytics

Repository for the Nomobug weather-aware pest-control analytics and decision-support system. The system is intended to combine operational, service-outcome, scheduling, location, and weather data for management analysis.

This is an analytics and data-engineering repository, not a CRM application.

## Repository Status

CP2 has verified BigQuery Bronze snapshots for Prospects, eight operational Sheets tabs and six Calendars. Silver matching and an initial three-view Gold fact layer pass dbt checks. Financial and warranty KPIs, weather enrichment, predictive ML, DBSCAN, automation and the dashboard remain to be completed. Neon is a manual fallback. See [current status](planning/PROJECT_STATUS.md).

## Planned Stack

Python/pandas, BigQuery, dbt Core (`dbt-bigquery`), scikit-learn, Cloud Run Jobs with Cloud Scheduler, Looker Studio and GitHub Actions for CI/deployment. Neon PostgreSQL remains a manual fallback. Docker supports reproducible execution. Live Google Sheets, Google Calendar and Open-Meteo APIs are the source interfaces; CSV exports are optional backups.

The build targets RM0 usage within verified free allowances. Billing-linked BigQuery has residual charge risk; the RM10 budget alert and query byte cap are active controls. Cloud Run and Looker Studio are selected but not yet deployed.

## Repository Contents

```text
planning/              Scope, schedule, migration checklist and writing reference
config/                Source maps, dictionary drafts and quality findings
scripts/               Active BigQuery workflow and shared source tooling
  neon/                Preserved manual fallback scripts
  prototypes/          Older exploration scripts; not the active pipeline
notebooks/             Beginner-friendly pandas profiling notebooks
tests/                 Offline synthetic regression tests
data/                  Local data workspace (private contents ignored)
docs/                  Preserved CP1 documents and proposal (local only)
secrets/               Private credentials (ignored)
```

## Source Tooling

- The three numbered notebooks provide the main step-by-step pandas workflow for local Jupyter or VS Code.
- `scripts/inventory_google_sources.py` discovers approved Google Sheets and Calendar metadata.
- The three `profile_*_all_*` scripts create local raw snapshots and data-quality profiles.
- `scripts/prototypes/fetch_calendar_events.py` is retained as the Calendar parsing prototype.
- `scripts/prototypes/test_open_meteo_history.py` is retained as the historical-weather prototype.

See `scripts/README.md` for the active script inventory. Historical prototypes remain separate from the tested first-source pipeline; broader production validation is pending.

## Data and Secrets

The repository must not contain raw company exports, customer or employee personal data, full Calendar extracts, credentials, OAuth tokens, API keys, or generated outputs containing identifying information.

Use anonymised or synthetic samples for committed tests. Keep real source data and credentials in approved local storage outside version control.
