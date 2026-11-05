# Short management usability test

Use a company-approved viewer account after the live report's charts and filters are complete. This evaluates the report; it does not prove model reliability, prevented callbacks or money saved. No customer messages are sent as part of this test.

Use `templates/cp2_dashboard_usability.csv`. Keep participant codes anonymous. Enter observed start/end timestamps with timezone (for example `2026-10-11T14:00:00+08:00`), the actual answer, and `yes`/`no` for correctness and help. Leave unattempted tasks blank. Do not insert invented observations. Record source freshness and the exact date filters in the session notes, because live answers can change.

| Task ID | Ask management to do this | Check the answer against |
|---|---|---|
| reminders | Find the scheduled reminder workload for today and the following six days. Explain whether a passed date means paid. | `dashboard_attention`, category Payment reminders; sum entries only within this category. Passed/green dates do not prove payment or a message sent. |
| balances | Find recorded remaining balances for recurring contracts and explain whether they are overdue. | `dashboard_recurring_payment_quality`, sum positive_recorded_remaining_balance_rm. Positive balance is not overdue debt. PAYMENTS is excluded. |
| bookings | Compare upcoming visits across team Calendars for the same seven-day period. | `dashboard_scheduling_capacity`; same dates, summed scheduled_event_rows by calendar_name. Scheduled is not completed. |
| model_tradeoff | Explain the highest-ranked 20 services in the historical model test. | 4 callback-positive windows found, 16 selected without a recorded callback, 1 positive missed; 100 services and 5 positives total. 80% capture is not accuracy. |
| weather_evidence | Determine whether adding more environmental inputs consistently improved the model. | `dashboard_feature_comparison`: no consistent gain across mean AP and capture. These are development comparisons; no causal rainfall claim. |
| freshness | Find how recently the sources were extracted and identify a stale or unknown source if one exists. | `dashboard_source_freshness`; max source age, with missing ages unknown. The action list explicitly uses a 36-hour review flag. |

Run `python -m scripts.summarize_cp2_usability PATH_TO_RESPONSES.csv --output outputs/usability/SESSION_ID/summary.json` with the project's Python environment. The untouched template produces `not_tested`, not a pass. A failed task is useful evidence: record the issue, repair the report and use a separately dated attempt. Do not overwrite the earlier attempt.

Completion requires actual stakeholder attempts, representative date/category-filter checks, readable narrow-screen output and viewer access verification. An agent checking chart bindings is not a substitute for participant evidence.
