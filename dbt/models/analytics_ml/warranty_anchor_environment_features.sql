{{ config(schema='analytics_ml', tags=['analytics_ml', 'weather'], materialized='table') }}
-- Antecedent environment at Calendar-event grain. Every contributing weather
-- date is strictly before the service date; event-day/future weather is excluded.
-- The cached IFS grid is approximately 9 km. These are regional exposure proxies,
-- not evidence of property flooding or a causal explanation of a claim.
{% set windows = [1, 3, 7, 14, 30] %}
{% set weather_fields = [
    'precipitation_sum_mm', 'temperature_2m_mean_c',
    'relative_humidity_2m_mean_pct', 'soil_moisture_0_to_7cm_mean'
] %}
with aggregated as (
    select
        l.calendar_event_row,
        l.event_date_local,
        l.weather_location_id,
        l.weather_eligible,
        max(w.weather_date) as latest_weather_date_used,
        {% for days in windows %}
        countif(w.weather_date >= date_sub(l.event_date_local, interval {{ days }} day))
            as prior_{{ days }}d_weather_rows,
        count(distinct if(w.weather_date >= date_sub(l.event_date_local, interval {{ days }} day),
            w.weather_date, null)) as prior_{{ days }}d_weather_days_available,
        {% for field in weather_fields %}
        countif(w.weather_date >= date_sub(l.event_date_local, interval {{ days }} day)
            and w.{{ field }} is not null) as valid_{{ field }}_{{ days }}d,
        {% endfor %}
        sum(if(w.weather_date >= date_sub(l.event_date_local, interval {{ days }} day),
            w.precipitation_sum_mm, null)) as precipitation_{{ days }}d,
        {% endfor %}
        {% for days in [7, 14, 30] %}
        countif(w.weather_date >= date_sub(l.event_date_local, interval {{ days }} day)
            and w.precipitation_sum_mm >= 1) as wet_days_{{ days }}d,
        {% endfor %}
        countif(w.weather_date >= date_sub(l.event_date_local, interval 14 day)
            and w.precipitation_sum_mm >= 10) as heavy_rain_days_14d,
        max(if(w.weather_date >= date_sub(l.event_date_local, interval 14 day),
            w.precipitation_sum_mm, null)) as max_daily_precipitation_14d,
        max(if(w.precipitation_sum_mm >= 1, w.weather_date, null)) as last_rain_date,
        {% for days in [7, 30] %}
        avg(if(w.weather_date >= date_sub(l.event_date_local, interval {{ days }} day),
            w.temperature_2m_mean_c, null)) as temperature_mean_{{ days }}d,
        avg(if(w.weather_date >= date_sub(l.event_date_local, interval {{ days }} day),
            w.relative_humidity_2m_mean_pct, null)) as relative_humidity_mean_{{ days }}d,
        avg(if(w.weather_date >= date_sub(l.event_date_local, interval {{ days }} day),
            w.soil_moisture_0_to_7cm_mean, null)) as soil_moisture_mean_{{ days }}d,
        {% endfor %}
        -- The cache contains daily mean temperature, not daily temperature maxima.
        max(if(w.weather_date >= date_sub(l.event_date_local, interval 7 day),
            w.temperature_2m_mean_c, null)) as maximum_daily_mean_temperature_7d
    from {{ ref('calendar_event_locations') }} l
    left join {{ source('quality', 'open_meteo_weather_daily_all') }} w
      on l.weather_eligible
     and w.weather_location_id = l.weather_location_id
     and w.weather_date >= date_sub(l.event_date_local, interval 30 day)
     and w.weather_date < l.event_date_local
    group by l.calendar_event_row, l.event_date_local,
             l.weather_location_id, l.weather_eligible
), completeness as (
    select *,
        {% for days in windows %}
        prior_{{ days }}d_weather_rows = {{ days }}
        and prior_{{ days }}d_weather_days_available = {{ days }}
        {% for field in weather_fields %}
        and valid_{{ field }}_{{ days }}d = {{ days }}
        {% endfor %}
            as complete_prior_{{ days }}d_weather{% if not loop.last %},{% endif %}
        {% endfor %}
    from aggregated
)
select
    calendar_event_row,
    event_date_local,
    weather_location_id,
    weather_eligible,
    latest_weather_date_used,
    {% for days in windows %}
    prior_{{ days }}d_weather_rows,
    prior_{{ days }}d_weather_days_available,
    complete_prior_{{ days }}d_weather,
    if(complete_prior_{{ days }}d_weather, precipitation_{{ days }}d, null)
        as prior_{{ days }}d_precipitation_mm,
    {% endfor %}
    {% for days in [7, 14, 30] %}
    if(complete_prior_{{ days }}d_weather, wet_days_{{ days }}d, null)
        as prior_{{ days }}d_wet_days_1mm,
    {% endfor %}
    if(complete_prior_14d_weather, heavy_rain_days_14d, null)
        as prior_14d_heavy_rain_days_10mm,
    if(complete_prior_14d_weather, max_daily_precipitation_14d, null)
        as prior_14d_max_daily_precipitation_mm,
    -- A dry 30-day window is represented by 30, rather than fabricated recency.
    if(complete_prior_30d_weather,
        coalesce(least(date_diff(event_date_local, last_rain_date, day), 30), 30), null)
        as days_since_last_rain_1mm_capped_30d,
    {% for days in [7, 30] %}
    if(complete_prior_{{ days }}d_weather, temperature_mean_{{ days }}d, null)
        as prior_{{ days }}d_temperature_mean_c,
    if(complete_prior_{{ days }}d_weather, relative_humidity_mean_{{ days }}d, null)
        as prior_{{ days }}d_relative_humidity_mean_pct,
    if(complete_prior_{{ days }}d_weather, soil_moisture_mean_{{ days }}d, null)
        as prior_{{ days }}d_soil_moisture_0_to_7cm_mean,
    {% endfor %}
    if(complete_prior_7d_weather, maximum_daily_mean_temperature_7d, null)
        as prior_7d_temperature_max_c,
    if(complete_prior_14d_weather,
        precipitation_3d / 3.0 - (precipitation_14d - precipitation_3d) / 11.0, null)
        as prior_3d_vs_previous_11d_daily_rain_trend_mm,
    'quality.open_meteo_weather_daily_all;ecmwf_ifs;prior_dates_only'
        as environment_feature_source,
    case
        when not weather_eligible then 'location_not_weather_eligible'
        when complete_prior_30d_weather then 'local_0_1_degree_grid_complete_prior_30d'
        else 'local_0_1_degree_grid_partial_prior_window'
    end as environment_feature_scope
from completeness
