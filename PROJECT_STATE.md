# Nomobug Capstone Project State

Last updated: 2026-07-17

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

## Possible Platform Stack

Supervisor feedback on 2026-07-17: the CP1 methodology should not lock the project into one fixed platform too early. BigQuery, Airflow, dbt Core, Docker, Superset, and Ollama are now described as possible platform choices. The final CP2 stack will be confirmed after data profiling, feasibility testing, cost/setup review, and supervisor/company feedback.

| Layer | Choice |
|---|---|
| Raw source | Google Sheets, CSV/Excel exports, Google Calendar |
| Extract/load | Python and Pandas, with the relevant API/warehouse client |
| Orchestration | Possible Apache Airflow, or scheduled Python jobs if simpler |
| Transformation and tests | Possible dbt Core, or SQL/Python transformation scripts |
| Analytics storage | Possible BigQuery, or another suitable analytics warehouse/database |
| Visualization | Possible Apache Superset, or another BI/dashboard platform |
| Weather history | Open-Meteo Historical Weather API |
| Weather forecast | Open-Meteo forecast first, with data.gov.my/MET as official warning support |
| Flood indicator | Public InfoBanjir/JPS where extraction is reliable, otherwise optional/manual |
| Local AI future work | Possible local model such as Ollama |
| Packaging | Possible Docker setup for local reproducibility, not as the main database |

## CP2 Build Order

1. Profile Google Sheets, CSV exports, and calendar data.
2. Define flexible data contracts, column aliases, and data quality rules.
3. Build Python extraction/loading scripts into raw staging tables.
4. Build transformation models and tests for cleaned tables and dashboard marts.
5. Add area/postcode coordinate lookup and historical weather enrichment.
6. Create a scheduled workflow to orchestrate extraction, loading, transformations, testing, enrichment, and refresh logs.
7. Build BI dashboards from curated marts only.
8. Add pipeline logging, data quality dashboard, and recommendation log.
9. Add optional local AI explanation layer.

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

- Added a possible platform stack flow figure into Chapter 3.
- Added a CP2 Gantt chart subsection into Chapter 4.
- Created editable CP1/CP2 Gantt workbook at `docs/Nomobug_CP1_CP2_Gantt_Chart.xlsx`.
- Created architecture image at `assets/nomobug_project_tech_stack_flow.png`.
- Canva generation was attempted but blocked by Canva quota, so the final visual was generated locally.
- Standardized the proposal formatting to Times New Roman, 12 pt body text, 1.5 line spacing, justified body paragraphs, and APA-style references.
- Revised the proposal so CP1 warehouse/data-source/tool sections read as planned logical designs rather than final implemented schemas.
- Updated the methodology after supervisor feedback so BigQuery, Airflow, dbt Core, Docker, Superset, and Ollama are presented as possible platforms, not locked CP2 decisions.
- Replaced confusing appendices with clearer planning appendices for data sources, dashboard outputs, and proposed logical warehouse layers.
- Added more organic in-text citations in Chapter 1 and strengthened citation support for BI, dashboards, data quality, weather-associated risk, and DSS significance.
- 42 total reference entries after adding Airflow/dbt technical references.
- 27 literature matrix rows.
- Around 24 academic/research-like sources, with tool/API documentation kept as technical support references.
- Literature review expanded with 2020+ sources on pest decision-support systems, DSS adoption, spatial clustering, dashboard design, data quality, rainfall modelling, and AI-assisted pest monitoring.
- Word export/render check passed after the latest formatting update.

Latest data-engineering direction:

- Keep the existing proposal title.
- Strengthen the methodology around an ELT/data engineering pipeline, while keeping platform choices flexible for CP2.
- Use Python for extraction/loading and evaluate possible platforms for orchestration, storage, transformations, dashboards, and local AI during CP2.
- Use flexible data contracts rather than strict schema rejection because the company data is messy.
- Include pipeline logs such as `etl_run_log`, `source_contract_status`, `data_quality_log`, `record_match_log`, `weather_enrichment_log`, transformation test results, and `mart_refresh_status`.

## Latest Logbook Status

The current logbook file is `docs/Logbook_Template.docx`.

Latest checks:

- Logbook updated through Week 10.
- Week 10 updated with the CP1/CP2 Gantt workbook and project technical stack flow diagram preparation.
- Week 1-4 date ranges corrected to May 2026.
- Week 5-10 entries added as a natural progression from CRM exploration to analytics, data understanding, calendar parsing, weather research, architecture selection, proposal strengthening, and data-engineering scope.
- Word export check passed after the latest update.

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
- `docs/Logbook_Template.docx`: current CP1 logbook updated through Week 10
- `docs/Nomobug_CP1_CP2_Gantt_Chart.xlsx`: editable CP1 and CP2 Gantt workbook
- `assets/nomobug_project_tech_stack_flow.png`: possible platform stack flow image used in the report
- `scripts/fetch_calendar_events.py`: Google Calendar extraction/parser script
- `scripts/test_open_meteo_history.py`: Open-Meteo historical API test script

## Next Recommended Work

1. Final read-through of the CP1 proposal before submission.
2. Send supervisor the updated proposal plus the project technical stack flow image.
3. If supervisor requests more depth, add short paragraphs for selected literature matrix papers rather than adding more random references.
4. Create a data source mapping sheet from actual Google Sheets tabs.
5. Confirm which exact Google Calendar fields are reliable.
6. Build safe synthetic samples for GitHub.
7. Prepare CP2 starter tasks: Python extract/load skeleton, data profiling, possible warehouse setup, possible transformation project skeleton, possible workflow scheduler setup, and possible BI dashboard setup.
