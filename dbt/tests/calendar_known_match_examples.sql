{{ config(tags=['calendar', 'matching']) }}
with expected as (
  select 3419 as calendar_event_row, 'CUST427' as sales_record_id union all
  select 3508, 'CUST533' union all
  select 8840, 'CUST533' union all
  select 9136, 'CUST533' union all
  select 5142, 'CUST1972' union all
  select 9359, 'CUST1972' union all
  select 7093, 'CUST482' union all
  select 7197, 'CUST482' union all
  select 7223, 'CUST482' union all
  select 4836, 'CUST1640' union all
  select 8983, 'CUST1129' union all
  select 9045, 'CUST1792' union all
  select 5452, 'CUST2250' union all
  select 11123, 'CUST2102'
)
select e.calendar_event_row, e.sales_record_id, m.matched_sales_record_id
from expected e left join {{ ref('calendar_event_matches') }} m using (calendar_event_row)
where m.matched_sales_record_id is distinct from e.sales_record_id
