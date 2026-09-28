select 'missing_release_timestamp' as failure
from {{ ref('dashboard_source_freshness') }}
where release_run_id is not null and extracted_at_utc is null
union all
select 'duplicate_source'
from {{ ref('dashboard_source_freshness') }}
group by source_name
having count(*) != 1
union all
select 'unexpected_source_count'
from (select count(*) as source_count from {{ ref('dashboard_source_freshness') }})
where source_count != 11
