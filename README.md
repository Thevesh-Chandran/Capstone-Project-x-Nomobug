# Nomobug Analytics

Repository for the Nomobug weather-aware pest-control analytics and decision-support system. The system is intended to combine operational, service-outcome, scheduling, location, and weather data for management analysis.

This is an analytics and data-engineering repository, not a CRM application.

## Repository Status

CP2 implementation is at the source-understanding and pipeline-design stage. The repository currently contains extraction prototypes, architecture material, and implementation notes. A production data pipeline, analytical models, and dashboards have not been added yet.

## Repository Contents

```text
assets/                Architecture diagrams
data/                  Data-workspace policy and safe placeholders
scripts/               Source-extraction prototypes
CP2_START_HERE.md      Implementation notes and planned build order
```

## Source Prototypes

- `scripts/fetch_calendar_events.py` reads selected Google Calendar events and parses semi-structured booking details.
- `scripts/test_open_meteo_history.py` tests historical weather retrieval from Open-Meteo.

These scripts are exploratory and require further validation, testing, configuration, and privacy controls before production use.

## Data and Secrets

The repository must not contain raw company exports, customer or employee personal data, full Calendar extracts, credentials, OAuth tokens, API keys, or generated outputs containing identifying information.

Use anonymised or synthetic samples for committed tests. Keep real source data and credentials in approved local storage outside version control.
