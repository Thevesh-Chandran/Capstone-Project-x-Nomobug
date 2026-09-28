{{ config(schema='analytics_ml', tags=['analytics_ml'], materialized='table') }}
-- Preserve the callback population and outcome unchanged. Missing flood coverage
-- remains distinguishable from an observed dry location.
with anchors as (
    select a.*,
        lower(to_hex(sha256(concat(a.population, '|', cast(a.sales_record_id as string),
            '|', cast(a.anchor_date as string))))) as flood_anchor_id
    from {{ ref('warranty_callback_fixed_horizon_dataset') }} a
)
select a.*,
    f.gfm_prior_7d_max_flood_fraction_1km,
    f.gfm_prior_14d_max_flood_fraction_1km,
    f.gfm_prior_30d_max_flood_fraction_1km,
    coalesce(f.gfm_prior_30d_observed_days, 0) as gfm_prior_30d_observed_days,
    coalesce(f.gfm_prior_30d_flood_detected_days, 0) as gfm_prior_30d_flood_detected_days,
    f.gfm_days_since_detected_flood_capped_30d,
    f.gfm_days_since_valid_observation,
    f.gfm_prior_30d_max_valid_fraction_1km,
    f.gfm_last_observation_at,
    f.gfm_last_available_at,
    f.gfm_source_catalogue_sha256,
    f.gfm_fetched_at,
    coalesce(f.gfm_status, 'missing_anchor_context') as gfm_status,
    d.gdacs_prior_7d_reported_events,
    d.gdacs_prior_14d_reported_events,
    d.gdacs_prior_30d_reported_events,
    d.gdacs_days_since_reported_event_capped_30d,
    d.gdacs_last_report_available_at,
    d.gdacs_last_report_event_at,
    d.gdacs_source_sha256,
    d.gdacs_fetched_at,
    coalesce(d.gdacs_status, 'missing_anchor_context') as gdacs_status
from anchors a
left join {{ source('flood_quality', 'gfm_flood_context_by_anchor') }} f
    on a.flood_anchor_id = f.flood_anchor_id
   and a.population = f.population
   and cast(a.sales_record_id as string) = f.sales_record_id
   and a.anchor_date = f.anchor_date
left join {{ source('flood_quality', 'gdacs_reported_flood_context_by_anchor') }} d
    on a.flood_anchor_id = d.flood_anchor_id
   and a.population = d.population
   and cast(a.sales_record_id as string) = d.sales_record_id
   and a.anchor_date = d.anchor_date
