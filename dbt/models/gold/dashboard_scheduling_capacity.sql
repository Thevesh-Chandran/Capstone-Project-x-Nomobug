{{ config(schema='gold', tags=['gold', 'dashboard', 'scheduling']) }}
-- Daily/calendar scheduling context. Calendar entries are scheduled/recorded
-- workload, not proof that a treatment was completed.
select
    event_date_local as service_date,
    calendar_name,
    extract(dayofweek from event_date_local) as day_of_week_number,
    count(*) as scheduled_event_rows,
    countif(event_category = 'service') as normal_package_event_rows,
    countif(warranty_claim_candidate) as warranty_claim_event_rows,
    countif(event_category = 'complimentary' and not warranty_claim_candidate)
        as generic_complimentary_event_rows,
    countif(extra_visit_candidate) as extra_visit_signal_rows,
    countif(sales_record_id is not null) as matched_sales_event_rows,
    countif(sales_record_id is null) as unmatched_sales_event_rows,
    countif(match_status = 'ambiguous_sales') as ambiguous_sales_event_rows,
    'scheduled_calendar_workload_not_completed_treatment_or_capacity_hours' as denominator_evidence
from {{ ref('calendar_service_event_facts') }}
where event_date_local between date '2026-01-01' and date '2026-12-31'
group by service_date, calendar_name, day_of_week_number
