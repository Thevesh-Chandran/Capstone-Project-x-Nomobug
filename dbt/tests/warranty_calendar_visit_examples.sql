{{ config(tags=['calendar', 'matching']) }}
with legacy_expected as (
  select 7093 as calendar_event_row, 'CUST482' as sales_record_id, false as extra union all
  select 7197, 'CUST482', true union all
  select 7223, 'CUST482', true union all
  select 11123, 'CUST2102', true
), expected as (
  select fresh.calendar_event_row, old_case.sales_record_id, old_case.extra
  from legacy_expected old_case
  left join {{ source('calendar_baseline_bronze', 'events') }} baseline
    on baseline.calendar_event_row = old_case.calendar_event_row
  left join {{ ref('calendar_events') }} fresh
    on fresh.calendar_id = baseline.calendar_id and fresh.event_id = baseline.event_id
)
select e.calendar_event_row, e.sales_record_id
from expected e
left join {{ ref('warranty_calendar_visits') }} v
  on v.calendar_event_row = e.calendar_event_row and v.sales_record_id = e.sales_record_id
where v.calendar_event_row is null or v.extra_visit_candidate is distinct from e.extra
