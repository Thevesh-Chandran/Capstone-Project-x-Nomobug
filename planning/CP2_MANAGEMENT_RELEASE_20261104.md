# Management website release — 4 November 2026

Oracle/Metabase remains on hold. Looker Studio remains the dashboard. No Oracle account, VM or paid upgrade was created.

## Released

Cloud Run portal revision `cp2-portal-00093-cop` serves the lighter page headers, coloured series, management-facing Prediction models, technical evidence, customer filters and Google Calendar viewer. Six approved calendars are configured; their existing Google access controls remain. Bookings must be created or changed in Google Calendar; the embedded view does not make reservations. Slot options use the travel allowance entered by staff, not a measured road journey.

The follow-up plan initially renders 20 records and loads 20 more on request, without removing other eligible services. Browser verification expanded 20 to 40 of 150. Original scoring and experimental model bundles are unchanged.

Removed the unverified 1.2-hour duration assumption for return visits. Forecast plus historical mean absolute error is explicitly an illustrative staffing scenario, not a prediction interval or guaranteed requirement.

## Evidence and monitoring

The model monitor is a historical replay, not proof of new prospective performance. Null outcomes and duplicate service keys are rejected. Its observed/expected ratio is displayed as a diagnostic and is not applied to live scores or planning totals. The monthly diagnostic is scheduled for 06:30 Malaysia time on the first day, after reporting. Its reviewed implementation is `scripts/run_monthly_return_risk_check.py`; the Scheduler execution uses the same code as a job argument, leaving the normal daily job command unchanged.

Email failure/freshness alerting is enabled for the owner. A disposable execution exited before reading sources or changing published data. The resulting Cloud Monitoring failure email was received. A separate scheduler-triggered full reporting release succeeded, preserving the normal daily schedule.

## Data checks

`gold.dashboard_sales_pest_groups` is deployed. Dated groups reconcile to monthly reporting. Undated rows reconcile separately to the source facts; five undated sales explain their omission from monthly totals. The refreshed private business export has 23 pest groups. The grouping view is available for Looker charts; this release does not claim those Looker chart configurations were edited.

Uncertain district assignments remain conservative and visible as unassigned. Missing source facts are not guessed. District rules have not been loosened.

## Verification

The full local suite passed 792 tests before the additional monitoring regression test, and the focused monitoring suite then passed 22 tests. The isolated public source review passed 476 tests with 3 optional skips. Both calendar and follow-up interface checks passed. The new pest view passed dbt build and its not-null test, plus independent amount/count reconciliation. The deployed Google Calendar viewer and model explanations were checked in the browser.
