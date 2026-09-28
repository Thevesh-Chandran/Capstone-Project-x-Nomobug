{{ config(tags=['calendar', 'matching']) }}
with legacy_expected as (
    select 1073 as calendar_event_row, 'CUST659' as sales_record_id union all
    select 1134, 'CUST1686' union all
    select 1137, 'CUST1684' union all
    select 4758, 'CUST1601' union all
    select 7097, 'CUST1670' union all
    select 7116, 'CUST1671' union all
    select 8956, 'CUST1694'
), expected as (
    select fresh.calendar_event_row, old_case.sales_record_id
    from legacy_expected old_case
    left join {{ source('calendar_baseline_bronze', 'events') }} baseline
      on baseline.calendar_event_row = old_case.calendar_event_row
    left join {{ ref('calendar_events') }} fresh
      on fresh.calendar_id = baseline.calendar_id and fresh.event_id = baseline.event_id
)
select e.calendar_event_row, e.sales_record_id, m.matched_sales_record_id
from expected e
left join {{ ref('calendar_event_matches') }} m using (calendar_event_row)
where m.matched_sales_record_id is distinct from e.sales_record_id
