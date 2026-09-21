{{ config(tags=['calendar', 'weather']) }}
-- Daily mean across the observed service-region weather grid. This is a
-- transparent fallback for events without validated coordinates; it captures
-- broad temporal/seasonal weather, not property-level conditions.
with daily as (
    select
        weather_date,
        avg(temperature_2m_mean_c) as temperature_2m_mean_c,
        avg(precipitation_sum_mm) as precipitation_sum_mm,
        avg(relative_humidity_2m_mean_pct) as relative_humidity_2m_mean_pct,
        avg(soil_moisture_0_to_7cm_mean) as soil_moisture_0_to_7cm_mean,
        count(*) as contributing_grid_cells
    from {{ source('quality', 'open_meteo_weather_daily_all') }}
    group by weather_date
)
select
    weather_date,
    contributing_grid_cells,
    temperature_2m_mean_c as event_day_temperature_mean_c,
    precipitation_sum_mm as event_day_precipitation_mm,
    relative_humidity_2m_mean_pct as event_day_relative_humidity_mean_pct,
    soil_moisture_0_to_7cm_mean as event_day_soil_moisture_0_to_7cm_mean,
    sum(precipitation_sum_mm) over (
        order by weather_date rows between 3 preceding and 1 preceding
    ) as prior_3d_precipitation_mm,
    sum(precipitation_sum_mm) over (
        order by weather_date rows between 7 preceding and 1 preceding
    ) as prior_7d_precipitation_mm,
    sum(precipitation_sum_mm) over (
        order by weather_date rows between 14 preceding and 1 preceding
    ) as prior_14d_precipitation_mm,
    avg(relative_humidity_2m_mean_pct) over (
        order by weather_date rows between 7 preceding and 1 preceding
    ) as prior_7d_relative_humidity_mean_pct,
    avg(soil_moisture_0_to_7cm_mean) over (
        order by weather_date rows between 7 preceding and 1 preceding
    ) as prior_7d_soil_moisture_0_to_7cm_mean,
    count(*) over (
        order by weather_date rows between 14 preceding and 1 preceding
    ) = 14 as complete_prior_14d_weather
from daily
