{{ config(tags=['calendar', 'matching']) }}
with expected as (
    select 1073 as calendar_event_row, 'CUST659' as sales_record_id union all
    select 1134, 'CUST1686' union all
    select 1137, 'CUST1684' union all
    select 4758, 'CUST1601' union all
    select 7097, 'CUST1670' union all
    select 7116, 'CUST1671' union all
    select 8956, 'CUST1694'
)
select e.calendar_event_row, e.sales_record_id, m.matched_sales_record_id
from expected e
left join {{ ref('calendar_event_matches') }} m using (calendar_event_row)
where m.matched_sales_record_id is distinct from e.sales_record_id
