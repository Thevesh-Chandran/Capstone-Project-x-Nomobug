{{ config(tags=['analytics_ml']) }}
select flood_anchor_id
from {{ source('flood_quality', 'gfm_flood_context_by_anchor') }}
where flood_anchor_id != lower(to_hex(sha256(concat(population, '|', sales_record_id,
    '|', cast(anchor_date as string)))))
   or not regexp_contains(gfm_source_catalogue_sha256, r'^[0-9a-f]{64}$')
   or gfm_prior_30d_observed_days is null
   or gfm_prior_30d_flood_detected_days is null
   or gfm_prior_30d_observed_days not between 0 and 30
   or gfm_prior_30d_flood_detected_days not between 0 and gfm_prior_30d_observed_days
union all
select any_value(flood_anchor_id)
from {{ source('flood_quality', 'gfm_flood_context_by_anchor') }}
group by population, sales_record_id, anchor_date
having count(*) != 1
