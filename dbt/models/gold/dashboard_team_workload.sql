{{ config(schema='gold', tags=['gold', 'dashboard', 'scheduling'], materialized='view') }}
-- Team-level booking heatmaps. Calendar names are team assignments, not proof of
-- individual technician assignments, completed work, capacity or occupied hours.
select
    service_date,
    date_trunc(service_date, week(monday)) as week_start,
    date_trunc(service_date, month) as month_start,
    format_date('%a', service_date) as weekday,
    mod(extract(dayofweek from service_date) + 5, 7) + 1 as weekday_order,
    calendar_name as team,
    scheduled_event_rows as bookings,
    normal_package_event_rows as paid_package_bookings,
    warranty_claim_event_rows as warranty_signal_bookings,
    unmatched_sales_event_rows as unmatched_sale_bookings,
    denominator_evidence
from {{ ref('dashboard_scheduling_capacity') }}
