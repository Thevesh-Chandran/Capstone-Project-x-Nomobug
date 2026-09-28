{{ config(tags=['calendar', 'matching']) }}
with legacy_expected as (
  select 4884 as calendar_event_row, 'CUST1782' as sales_record_id union all
  select 10711, 'CUST1872' union all
  select 4744, 'CUST393' union all
  select 4976, 'CUST393' union all
  select 9062, 'CUST343' union all
  select 10762, 'CUST1712' union all
  select 9689, 'CUST1712' union all
  select 10738, 'CUST2018' union all
  select 10739, 'CUST2017' union all
  select 7450, 'CUST2018' union all
  select 7449, 'CUST2017' union all
  select 10894, 'CUST2018' union all
  select 10893, 'CUST2017' union all
  select 7228, 'CUST707' union all
  select 5264, 'CUST707' union all
  select 5460, 'CUST707'
), expected as (
  select fresh.calendar_event_row, old_case.sales_record_id
  from legacy_expected old_case
  left join {{ source('calendar_baseline_bronze', 'events') }} baseline
    on baseline.calendar_event_row = old_case.calendar_event_row
  left join {{ ref('calendar_events') }} fresh
    on fresh.calendar_id = baseline.calendar_id and fresh.event_id = baseline.event_id
)
select e.calendar_event_row, e.sales_record_id, m.matched_sales_record_id
from expected e left join {{ ref('calendar_event_matches') }} m using (calendar_event_row)
where m.matched_sales_record_id is distinct from e.sales_record_id
