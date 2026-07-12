# Nomobug Capstone Workspace

This workspace is now focused on the current Nomobug capstone direction:

**Weather-aware pest control analytics and decision support using Python extract/load scripts, Apache Airflow, BigQuery, dbt Core, Apache Superset, Google Sheets, Google Calendar, and weather data.**

This is not the old CRM prototype. The old React/Express/PostgreSQL prototype has been moved into `archive/old-react-express-prototype` so it does not mix with the current CP1/CP2 plan.

## Current Phase

This project is currently in **Capstone Project 1 (CP1)**.

CP1 focuses on:

- proposal writing
- data understanding
- architecture planning
- source-to-table mapping
- cleaning and exclusion rules
- flexible data contracts
- Airflow/dbt/BigQuery ELT design
- analytics method selection
- dashboard design
- evaluation planning

Implementation starts in **Capstone Project 2 (CP2)**.

## Planned CP2 Architecture

```text
Google Sheets / CSV / Google Calendar / Weather APIs
        |
        v
Python Extract/Load Scripts
        |
        v
Apache Airflow Orchestration
        |
        v
BigQuery Bronze Raw Tables
        |
        v
dbt Core Transformations and Tests
        |
        v
BigQuery Silver Clean Tables / Gold Analytics Marts
        |
        v
Apache Superset Dashboards
        |
        v
Management Decision Support
```

Optional future extension:

```text
BigQuery dashboard marts
        |
        v
Local Ollama AI
        |
        v
Recommendation explanations and recommendation log
```

## Active Folder Structure

```text
.
  README.md
  PROJECT_BRIEF.md
  PROJECT_STATE.md
  docs/
    Nomobug_Capstone_Proposal_CP1_Updated.docx
  scripts/
    fetch_calendar_events.py
    test_open_meteo_history.py
  data/
    samples/
      local CSV exports only, ignored by Git
  tools/
    build_nomobug_proposal.py
  archive/
    old-react-express-prototype/
```

## Active Scripts

### Google Calendar Extraction

`scripts/fetch_calendar_events.py`

Purpose:

- fetch selected Nomobug team calendars
- clean Google Calendar HTML descriptions
- parse event titles such as `GPC 1/3`, `GPC 4/5`, `GPC 1/12`, and `GPC CONSULTATION`
- extract structured fields such as customer name, premise name, address, package, pest problem, phone, email, estimated size, session stage, and event category

This supports:

- scheduling capacity analysis
- technician/team workload analysis
- warranty/extra session identification
- treatment difficulty analysis

### Historical Weather API Test

`scripts/test_open_meteo_history.py`

Purpose:

- test whether Open-Meteo Historical Weather API works
- fetch historical rain, precipitation, temperature, humidity, and weather code by coordinate and date range
- save the returned data to CSV for inspection

Example:

```powershell
python scripts/test_open_meteo_history.py 3.0738 101.5183 2026-06-01 2026-06-24
```

This creates:

```text
data/samples/open_meteo_history_sample.csv
```

Generated CSV outputs are ignored by Git. Do not commit raw company exports, calendar extracts, customer names, phone numbers, emails, or full addresses.

## Data Source Direction

Internal company data:

- Google Sheets exports
- downloaded Excel/CSV files
- Google Calendar API for scheduling data

Weather data:

- Open-Meteo Historical Weather API for historical service-date matching
- Open-Meteo forecast or data.gov.my/MET forecast for future planning
- Public InfoBanjir as optional flood/rainfall support if extraction is reliable

## Analytics Focus

The project will focus on:

- customer segmentation
- marketing and funnel analytics
- payment and payment-link tracking
- service and revenue analytics
- scheduling capacity
- warranty and repeat-problem analysis
- treatment difficulty by area, pest type, and team
- recurrence window analysis
- spatial hotspot detection
- weather-associated area risk
- upsell package effectiveness and package-fit recommendations
- data quality reporting
- recommendation logging

## Important Wording Rules

Use careful analytical wording:

- `weather-associated risk`
- `risk indicator`
- `higher observed risk`
- `review indicator`
- `requires closer monitoring`

Avoid unsupported causal wording:

- do not say weather caused pest activity unless statistically proven
- do not blame technicians directly
- do not claim an area will definitely fail

## Local Archive

The previous React/Express/PostgreSQL prototype is stored in:

```text
archive/old-react-express-prototype/
```

It is kept only as a reference. The current build direction is Airflow + Python extract/load + BigQuery + dbt Core + Superset.
The archive is intentionally ignored by Git so the GitHub repository stays focused on the current capstone plan.

## Privacy Rule for GitHub

This repository should contain planning documents, scripts, and safe templates only. Raw company data, Google credentials, calendar tokens, generated CSV exports, and rendered QA files must stay local and are ignored by Git.
