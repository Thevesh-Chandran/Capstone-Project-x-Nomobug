{{ config(schema='gold', tags=['gold', 'dashboard', 'looker']) }}
-- Descriptive weather association only. Means use complete prior-14-day
-- windows; missing weather is retained in the coverage denominator.
select
    date_trunc(event_date_local, month) as service_month,
    if(warranty_claim_candidate, 'recorded_warranty_signal',
       'other_scheduled_service_entry') as event_group,
    count(*) as scheduled_event_rows,
    countif(complete_prior_14d_weather) as complete_prior_14d_weather_rows,
    safe_divide(countif(complete_prior_14d_weather), count(*))
        as complete_weather_coverage_share,
    avg(if(complete_prior_14d_weather, prior_3d_precipitation_mm, null))
        as avg_prior_3d_precipitation_mm,
    avg(if(complete_prior_14d_weather, prior_7d_precipitation_mm, null))
        as avg_prior_7d_precipitation_mm,
    avg(if(complete_prior_14d_weather, prior_14d_precipitation_mm, null))
        as avg_prior_14d_precipitation_mm,
    avg(if(complete_prior_14d_weather, prior_7d_relative_humidity_mean_pct, null))
        as avg_prior_7d_relative_humidity_pct,
    avg(if(complete_prior_14d_weather,
        prior_7d_soil_moisture_0_to_7cm_mean, null))
        as avg_prior_7d_soil_moisture,
    'open_meteo_reanalysis_association_not_property_measurement_or_causal_effect'
        as weather_evidence
from {{ ref('calendar_service_event_facts') }}
where event_date_local between date '2026-01-01' and date '2026-12-31'
group by service_month, event_group
