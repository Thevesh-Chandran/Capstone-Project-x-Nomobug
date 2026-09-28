{{ config(schema='gold', tags=['gold', 'dashboard', 'looker']) }}
-- Aggregate only confirmed recorded warranty signals. Planned package visits
-- and generic extra entries are not silently labelled recurrence.
select
    date_trunc(event_date_local, month) as service_month,
    recurrence_bucket,
    recurrence_reason,
    count(*) as recorded_warranty_signal_rows,
    countif(property_text_available) as property_text_available_rows,
    countif(not property_text_available) as property_review_rows,
    'recorded_calendar_warranty_signal_rows_not_unique_customers_or_confirmed_reinfestations'
        as denominator_evidence
from {{ ref('dashboard_recurrence_windows') }}
where recurrence_signal_candidate
group by service_month, recurrence_bucket, recurrence_reason
