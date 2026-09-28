{{ config(schema='gold', tags=['gold', 'spatial']) }}
-- One row per geocoded service property with one or more recorded warranty
-- signals. Property-level clustering prevents repeated callbacks at one
-- address from manufacturing a neighbourhood hotspot.
select
    address_hash,
    any_value(latitude having max event_date_local) as latitude,
    any_value(longitude having max event_date_local) as longitude,
    any_value(service_geography having max event_date_local) as service_geography,
    min(event_date_local) as first_repeat_signal_date,
    max(event_date_local) as latest_repeat_signal_date,
    count(*) as recorded_warranty_signal_rows,
    count(distinct sales_record_id) as distinct_sales_packages,
    countif(complete_prior_14d_weather) as complete_prior_14d_weather_rows,
    avg(if(complete_prior_14d_weather, prior_7d_precipitation_mm, null))
        as avg_prior_7d_precipitation_mm,
    avg(if(complete_prior_14d_weather, prior_7d_relative_humidity_mean_pct, null))
        as avg_prior_7d_relative_humidity_pct,
    avg(if(complete_prior_14d_weather,
        prior_7d_soil_moisture_0_to_7cm_mean, null)) as avg_prior_7d_soil_moisture
from {{ ref('spatial_repeat_signal_events') }}
where address_hash is not null
group by address_hash
