{{ config(schema='gold', tags=['gold', 'spatial']) }}
-- One row per scheduled/recorded warranty-claim proxy with a street-or-better
-- coordinate candidate. This includes explicit warranty labels and
-- post-package sequences such as 4/3 or 5/3. Clusters support sensitivity
-- review, not pest spread.
with signals as (
    select *
    from {{ ref('calendar_service_event_facts') }}
    where warranty_claim_candidate
      and heatmap_eligible
      and location_precision_tier in ('precise_candidate', 'street_candidate')
      and event_date_local between date '2026-01-01' and date '2026-12-31'
), clustered as (
    select
        *,
        st_clusterdbscan(service_geography, 1000, 3) over () as cluster_1km,
        st_clusterdbscan(service_geography, 2000, 3) over () as cluster_2km,
        st_clusterdbscan(service_geography, 5000, 3) over () as cluster_5km
    from signals
)
select
    calendar_event_row,
    event_date_local,
    event_category as repeat_signal_type,
    warranty_claim_reason,
    sales_record_id,
    address_hash,
    latitude,
    longitude,
    service_geography,
    location_precision_tier,
    location_uncertainty_radius_m,
    cluster_1km,
    cluster_2km,
    cluster_5km,
    weather_coverage_status,
    complete_prior_14d_weather,
    prior_3d_precipitation_mm,
    prior_7d_precipitation_mm,
    prior_14d_precipitation_mm,
    prior_7d_relative_humidity_mean_pct,
    prior_7d_soil_moisture_0_to_7cm_mean,
    'scheduled_or_recorded_repeat_proxy_not_confirmed_reinfestation' as outcome_evidence
from clustered
