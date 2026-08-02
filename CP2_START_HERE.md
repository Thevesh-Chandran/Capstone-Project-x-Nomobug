# CP2 Implementation Guide

## Project Direction

CP2 will implement the data engineering and analytics workflow proposed during CP1. The system should help Nomobug review service outcomes, repeat pest problems, warranty and refund patterns, treatment difficulty, spatial hotspots, weather-associated indicators, scheduling context, and upsell performance.

Platform choices remain flexible. Tools such as BigQuery, Apache Airflow, dbt Core, Apache Superset, Docker, and Ollama are candidates to evaluate, not requirements that must all be used.

## First Milestone: Understand the Real Data

Do not begin with dashboards or machine learning. Start by inspecting the actual Google Sheets exports and Calendar data.

1. Inventory every usable source, sheet, tab, and Calendar.
2. Record column names, data types, date coverage, row counts, and update frequency.
3. Identify candidate keys such as customer ID, service reference, normalised phone number, service date, and area or postcode.
4. Measure missing values, duplicates, invalid dates, inconsistent labels, and unmatched records.
5. Create a confirmed data dictionary and source-to-target mapping.
6. Decide the implementation stack after the data requirements are understood.

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
10. Optional local AI explanation layer only after the analytics are reliable.

## Analytics Approach

- Descriptive analysis for service, revenue, warranty, refund, scheduling, and upsell trends.
- DBSCAN for spatial repeat-problem clusters when coordinate coverage is sufficient.
- KDE for hotspot visualisation.
- Rainfall time-lag features for weather-associated analysis.
- Logistic regression only if the labelled warranty data is sufficient and validation is meaningful.
- Recurrence-window and interval comparisons for the timing of repeat problems.
- Transparent rule-based treatment-difficulty and recommendation logic.

The expected warranty dataset is only around 200 or more records. Complex models should not be added merely to make the project appear more technical.

## Interpretation Rules

Use wording such as `weather-associated risk`, `higher observed risk`, `review indicator`, and `requires closer monitoring`. Technician-related results support management review and must not be presented as proof of blame. Weather indicators show association unless stronger causal evidence is established.

## Immediate Next Task

Profile the downloaded company workbooks and produce:

- a source inventory;
- a sheet and column inventory;
- row counts and date coverage;
- missing-value and duplicate summaries;
- preliminary keys and relationships;
- a list of fields that should be retained, cleaned, derived, excluded, or manually reviewed.
