# Nomobug Capstone Project Brief

## Project Title

**Weather-Aware Pest Control Decision-Support Dashboard**

Using BigQuery, spatial hotspot detection, treatment difficulty analytics, and prescriptive intelligence for Nomobug Pest Control Services.

## CP1 and CP2 Boundary

This project is currently in **Capstone Project 1 (CP1)**. CP1 focuses on the proposal, problem analysis, literature review, methodology, architecture design, work plan, expected outcomes, and evaluation plan.

The actual system implementation will be carried out in **Capstone Project 2 (CP2)**. CP2 will involve building the ETL pipeline, BigQuery warehouse, Superset dashboards, analytics scripts, and evaluation with company users.

## Project Purpose

Nomobug currently stores operational data in Google Sheets and Google Calendar. The data includes leads, sales, services, warranty claims, refunds, payment records, upsell records, technician assignments, and service scheduling.

The problem is that these records are spread across separate files and are mainly used for recording, not decision-making. Management has to manually compare different sources to understand warranty patterns, repeat problems, treatment difficulty, refund causes, weather-associated risk, and upsell performance.

The proposed project will turn this scattered data into a web-based analytics and decision-support dashboard.

## Proposed Architecture

```text
Google Sheets / CSV / Google Calendar
        |
        v
Python ETL and Analytics Pipeline
        |
        v
BigQuery Cloud Data Warehouse
        |
        v
Apache Superset Dashboards
        |
        v
Management Decision Support
```

Future extension:

```text
BigQuery analytics outputs
        |
        v
Local Ollama AI service
        |
        v
Recommendation log and dashboard explanations
```

## Main Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Raw data source | Google Sheets, CSV/Excel, Google Calendar | Company records and scheduling data |
| ETL and analytics | Python, Pandas, scikit-learn | Cleaning, transformation, weather enrichment, DBSCAN, scoring |
| Data warehouse | BigQuery | Store raw staging tables, cleaned core tables, and dashboard marts |
| Dashboard | Apache Superset | Browser-based BI dashboards and filters |
| Deployment support | Docker | Reproducible local services such as Superset, Python worker, and future Ollama |
| Future AI | Ollama | Local AI-generated explanations and recommendations without paid API cost |

## BigQuery Storage Design

The data warehouse will use three layers:

1. **Staging tables**
   Raw imported data from Google Sheets, CSV/Excel, Google Calendar, and weather sources.

2. **Cleaned core tables**
   Standardised customer, service, warranty, refund, payment, upsell, area, pest, and calendar records.

3. **Analytics marts**
   Dashboard-ready tables for area risk, treatment difficulty, recurrence windows, hotspot detection, upsell package fit, data quality, refresh status, and recommendations.

## Key Data Relationships

| Relationship | Join / Matching Method |
|---|---|
| Customers to services | `customer_id`, fallback to normalised phone number |
| Services to warranty claims | `service_id`, or `customer_id + service date window + pest type` |
| Services to refunds | `customer_id/service_id + refund date after service date` |
| Services to calendar events | service date + customer name/phone/event title with match confidence |
| Services to area | standardised area/postcode |
| Services to weather | area/postcode coordinate + service date |
| Upsell records to payments | customer ID + payment date near upsell window |
| Recommendations to outcomes | related customer, service, area, pest type, and generated date |

## Data Cleaning and Quality Rules

The project will not silently delete messy records. Raw records will be preserved in staging tables, then cleaned and flagged.

Examples of cleaning:

- standardise date formats
- normalise phone numbers
- standardise pest names such as `lipas`, `cockroach`, and `cockroaches`
- standardise area and postcode labels
- map areas to centroid coordinates
- categorise refund reasons
- parse Google Calendar event types
- attach rainfall and humidity by service date

Examples of flags:

- missing value
- duplicate candidate
- invalid date
- unmatched customer
- unknown area/postcode
- low calendar match confidence
- missing weather enrichment

A record may be excluded from one analysis but still used in another. For example, a service with missing coordinates can still be used in revenue trends, but not in DBSCAN hotspot detection.

## Main Analytics Modules

1. Executive Summary
2. Marketing and Funnel
3. Area and Weather Risk
4. Treatment Difficulty
5. Warranty and Repeat Analysis
6. Recurrence and Hotspots
7. Upsell Intelligence
8. Scheduling Capacity
9. Refund Root Cause
10. Data Quality and Refresh
11. Recommendation Log

## Analytics Methods

The project is analytics-first, not heavy machine learning.

Recommended methods:

- descriptive BI by day, week, and month
- DBSCAN for repeat-problem hotspot detection
- KDE heatmap visualisation
- recurrence window analysis
- service interval comparison
- weather time-lag analysis
- logistic regression only if the data is sufficient
- rule-based treatment difficulty scoring
- package-fit analysis for upsell recommendations

This approach is suitable because the warranty dataset is expected to contain around 200+ records, which is limited for complex machine learning.

## Data Quality Report

The Data Quality Report will show:

- missing-value summary
- duplicate-record count
- invalid-date count
- unmatched-customer count
- area/postcode match confidence
- weather-enrichment coverage
- calendar matching confidence
- last refresh status

This helps the company understand whether dashboard insights are based on strong or incomplete data.

## Scheduled Refresh

The proposed system will use near-real-time scheduled refresh, not streaming real-time processing.

Possible refresh options:

- scheduled Python ETL job
- BigQuery scheduled query
- manual refresh during prototype testing

This is enough because the main business questions are based on day/week/month trends, not second-by-second operations.

## Privacy and Governance

The system will support anonymised reporting views.

Academic and management reports should use:

- customer ID
- general area/postcode
- pest type
- service type
- package type
- claim/refund category

Reports should avoid exposing:

- customer names
- full phone numbers
- full addresses

Technician analysis must be framed as a **review indicator**, not blame.

Weather analysis must be framed as **weather-associated risk**, not proof that weather caused pest problems.

## Recommendation Log

The Recommendation Log will store:

- recommendation type
- generated date
- related customer/service/area
- reason for recommendation
- confidence or review label
- management action taken
- later outcome

This prepares the project for future local AI using Ollama. The analytics engine will compute the score, and Ollama can later explain the recommendation in plain language.

## Expected CP2 Deliverables

- Python ETL pipeline
- BigQuery staging, cleaned, and mart tables
- Superset dashboards
- data quality dashboard
- weather enrichment output
- treatment difficulty index
- recurrence window analysis
- DBSCAN hotspot detection
- upsell package-fit matrix
- recommendation log
- evaluation report with company feedback

## One-Sentence Description

This project proposes a weather-aware pest control decision-support dashboard that uses company operational data, BigQuery, Python analytics, Superset visualisation, and future local AI recommendations to help Nomobug improve service planning, recurrence monitoring, treatment difficulty analysis, and upsell strategy.
