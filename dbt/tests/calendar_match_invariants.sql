{{ config(tags=['calendar', 'matching']) }}
select 'calendar_match_row_count' as check_name from unnest([1])
where (select count(*) from {{ source('calendar_bronze', 'events') }}) != (select count(*) from {{ ref('calendar_event_matches') }})
union all
select 'calendar_match_row_unique'
from {{ ref('calendar_event_matches') }}
group by calendar_event_row
having count(*) != 1
union all
select 'accepted_match_status'
from {{ ref('calendar_event_matches') }}
where match_status not in ('high_invoice', 'medium_phone_title_qualifier', 'medium_phone_date_session', 'medium_calendar_sequence', 'medium_closed_date_evidence', 'medium_phone', 'medium_email', 'low_address', 'ambiguous_sales', 'payment_link_only', 'unmatched')
