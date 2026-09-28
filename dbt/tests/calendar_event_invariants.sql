{{ config(tags=['calendar']) }}
select 'calendar_row_count' as check_name from unnest([1])
where (select count(*) from {{ source('calendar_bronze', 'events') }}) != (select count(*) from {{ ref('calendar_events') }})
union all
select 'calendar_event_row_unique'
from {{ ref('calendar_events') }}
group by calendar_event_row
having count(*) != 1
union all
select 'cancelled_rows_retained'
from unnest([1])
where (select count(*) from {{ source('calendar_bronze', 'events') }} where status = 'cancelled')
    != (select count(*) from {{ ref('calendar_events') }} where status = 'cancelled')
union all
select 'administrative_warranty_reminder_excluded'
from unnest([1])
where (
    select countif(
        event_id = '3n1h00canopusgqmd1sqi001tv'
        and event_category = 'administrative'
        and not service_candidate
    )
    from {{ ref('calendar_events') }}
) != 1
