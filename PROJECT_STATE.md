# Nomobug Capstone Project State

Last updated: 2026-07-12

## Current Phase

This project is in Capstone Project 1 (CP1). CP1 is the planning and proposal phase. The actual build will start in CP2.

## Current Direction

The project is a weather-aware pest control analytics and decision-support dashboard for Nomobug Pest Control Services. It is not a CRM.

The goal is to help management understand:

- service and revenue trends
- marketing and funnel quality
- warranty and repeat-problem patterns
- treatment difficulty by area, pest type, and team
- recurrence windows and spatial hotspots
- weather-associated risk indicators
- upsell package effectiveness and package fit
- data quality and refresh status
- recommendation history and action outcomes

## Confirmed Stack

| Layer | Choice |
|---|---|
| Raw source | Google Sheets, CSV/Excel exports, Google Calendar |
| Extract/load | Python, Pandas, BigQuery client |
| Orchestration | Apache Airflow |
| Transformation and tests | dbt Core |
| Warehouse | BigQuery with Bronze/Silver/Gold layers |
| Visualization | Apache Superset |
| Weather history | Open-Meteo Historical Weather API |
| Weather forecast | Open-Meteo forecast first, with data.gov.my/MET as official warning support |
| Flood indicator | Public InfoBanjir/JPS where extraction is reliable, otherwise optional/manual |
| Local AI future work | Ollama |
| Packaging | Docker for local reproducibility, not as the main database |

## CP2 Build Order

1. Profile Google Sheets, CSV exports, and calendar data.
2. Define flexible data contracts, column aliases, and data quality rules.
3. Build Python extraction/loading scripts into BigQuery Bronze raw tables.
4. Build dbt models and tests for Silver cleaned tables and Gold dashboard marts.
5. Add area/postcode coordinate lookup and historical weather enrichment.
6. Create Airflow DAGs to orchestrate extraction, loading, dbt, testing, enrichment, and refresh logs.
7. Build Superset dashboards from Gold marts only.
8. Add pipeline logging, data quality dashboard, and recommendation log.
9. Add optional local Ollama explanation layer.

## Analytics Methods

Keep the project analytics-first, not heavy machine learning.

- DBSCAN for spatial repeat-problem hotspot detection.
- KDE as a heatmap visualization layer.
- Time-lag analysis for rainfall/weather windows.
- Logistic regression only if the data is sufficient.
- Recurrence window analysis for days until repeat claim or complimentary service.
- Rule-based treatment difficulty index.
- Descriptive package effectiveness and package-fit analysis for upsell.

The warranty dataset is expected to be around 200+ records, so complex ML should be avoided unless it clearly improves the result.

## Latest Proposal Status

The current proposal file is `docs/Nomobug_Capstone_Proposal_CP1_Updated.docx`.

Latest checks:

- 42 total reference entries after adding Airflow/dbt technical references.
- 27 literature matrix rows.
- Around 24 academic/research-like sources, with tool/API documentation kept as technical support references.
- Literature review expanded with 2020+ sources on pest decision-support systems, DSS adoption, spatial clustering, dashboard design, data quality, rainfall modelling, and AI-assisted pest monitoring.
- Word export/render check passed after the latest reference expansion.

Latest data-engineering direction:

- Keep the existing proposal title.
- Strengthen the methodology around an Airflow-orchestrated ELT pipeline.
- Use Python for extraction/loading, BigQuery for the warehouse, dbt Core for SQL transformations/tests/lineage, and Superset for Gold-mart dashboards.
- Use flexible data contracts rather than strict schema rejection because the company data is messy.
- Include pipeline logs: `etl_run_log`, `source_contract_status`, `data_quality_log`, `record_match_log`, `weather_enrichment_log`, `dbt_test_results`, and `mart_refresh_status`.

## Important Wording Rules

Use:

- weather-associated risk
- risk indicator
- higher observed risk
- review indicator
- requires closer monitoring

Avoid:

- weather caused pest activity
- technician caused failure
- this area will definitely fail

## GitHub Privacy Rules

Do not commit:

- raw customer exports
- calendar extracts with names, phones, emails, or addresses
- Google credentials
- OAuth tokens
- generated CSV outputs
- rendered proposal QA images/PDFs

Commit:

- proposal documents
- safe planning markdown
- scripts
- templates
- anonymised or synthetic sample data only

## Current Important Files

- `README.md`: workspace overview
- `PROJECT_BRIEF.md`: project concept and architecture summary
- `PROJECT_STATE.md`: compact handoff/context guide
- `docs/Nomobug_Capstone_Proposal_CP1_Updated.docx`: current CP1 proposal
- `scripts/fetch_calendar_events.py`: Google Calendar extraction/parser script
- `scripts/test_open_meteo_history.py`: Open-Meteo historical API test script

## Next Recommended Work

1. Final read-through of the CP1 proposal before submission.
2. If supervisor requests more depth, add short paragraphs for selected literature matrix papers rather than adding more random references.
3. Create a data source mapping sheet from actual Google Sheets tabs.
4. Confirm which exact Google Calendar fields are reliable.
5. Build safe synthetic samples for GitHub.
6. Prepare CP2 starter tasks: BigQuery project setup, dbt Core project skeleton, Airflow Docker setup, Superset local Docker setup, and Python extract/load skeleton.
