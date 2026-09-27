{{ config(tags=['analytics_ml']) }}
select flood_anchor_id
from {{ source('flood_quality', 'gdacs_reported_flood_context_by_anchor') }}
where flood_anchor_id != lower(to_hex(sha256(concat(population, '|', sales_record_id,
    '|', cast(anchor_date as string)))))
   or not regexp_contains(gdacs_source_sha256, r'^[0-9a-f]{64}$')
union all
select any_value(flood_anchor_id)
from {{ source('flood_quality', 'gdacs_reported_flood_context_by_anchor') }}
group by population, sales_record_id, anchor_date
having count(*) != 1
