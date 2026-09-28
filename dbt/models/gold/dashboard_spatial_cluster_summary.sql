{{ config(schema='gold', tags=['gold', 'dashboard', 'looker']) }}
-- Property-level DBSCAN sensitivity summary. Exact property coordinates,
-- address hashes and package identifiers are excluded from this release layer.
with expanded as (
    select
        radius_km,
        cluster_id,
        service_geography,
        recorded_warranty_signal_rows,
        distinct_sales_packages,
        complete_prior_14d_weather_rows,
        avg_prior_7d_precipitation_mm,
        avg_prior_7d_relative_humidity_pct,
        avg_prior_7d_soil_moisture
    from {{ ref('spatial_repeat_signal_property_clusters') }} e
    cross join unnest([
        struct(1 as radius_km, e.cluster_1km as cluster_id),
        struct(2 as radius_km, e.cluster_2km as cluster_id),
        struct(5 as radius_km, e.cluster_5km as cluster_id)
    ])
    where cluster_id is not null
)
select
    radius_km,
    cluster_id,
    st_y(st_centroid(st_union_agg(service_geography))) as cluster_centroid_latitude,
    st_x(st_centroid(st_union_agg(service_geography))) as cluster_centroid_longitude,
    count(*) as distinct_service_properties,
    sum(recorded_warranty_signal_rows) as recorded_warranty_signal_rows,
    sum(distinct_sales_packages) as property_level_sales_package_rows,
    sum(complete_prior_14d_weather_rows) as complete_prior_14d_weather_rows,
    avg(if(complete_prior_14d_weather_rows > 0, avg_prior_7d_precipitation_mm, null))
        as avg_prior_7d_precipitation_mm,
    avg(if(complete_prior_14d_weather_rows > 0, avg_prior_7d_relative_humidity_pct, null))
        as avg_prior_7d_relative_humidity_pct,
    avg(if(complete_prior_14d_weather_rows > 0,
        avg_prior_7d_soil_moisture, null))
        as avg_prior_7d_soil_moisture,
    'dbscan_minimum_3_distinct_service_properties_sensitivity_not_pest_spread_radius'
        as cluster_evidence
from expanded
group by radius_km, cluster_id
