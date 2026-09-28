{{ config(tags=['calendar', 'matching']) }}
-- Shared-phone examples: distinguish houses by precise address; preserve the
-- active close-date/session sequence when a visit uses an older address; and
-- link a 3x House & Car service stream to its six-session compound sale.
-- Syed's House 2 package visit at event 9738 physically took place at House 1;
-- the title/SALES link and actual Calendar service address are separate facts.
with legacy_expected as (
    select 7266 as calendar_event_row, 'CUST1772' as sales_record_id union all
    select 5061, 'CUST1772' union all
    select 5086, 'CUST1772' union all
    select 11040, 'CUST2302' union all
    select 9891, 'CUST2302' union all
    select 7247, 'CUST811' union all
    select 10935, 'CUST2198' union all
    select 9656, 'CUST2198' union all
    select 1740, 'CUST2264' union all
    select 1593, 'CUST2023' union all
    select 9738, 'CUST2159'
    union all select 1060, 'CUST1612'
    union all select 1077, 'CUST1612'
    union all select 1134, 'CUST1686'
    union all select 1461, 'CUST1686'
    union all select 9771, 'CUST1686'
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
