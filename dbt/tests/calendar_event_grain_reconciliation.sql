{{ config(tags=['gold']) }}
-- Separate Calendar reconciliation keeps each check below the 100 MiB query cap.
select 'calendar_service_event_count' as failure
from unnest([1])
where (select count(*) from {{ ref('calendar_service_event_facts') }}) !=
      (select count(*) from {{ ref('calendar_events') }} where service_candidate)
union all
select 'calendar_match_preserved'
from {{ ref('calendar_service_event_facts') }} g
join {{ ref('calendar_event_matches') }} m using (calendar_event_row)
where g.sales_record_id is distinct from m.matched_sales_record_id
