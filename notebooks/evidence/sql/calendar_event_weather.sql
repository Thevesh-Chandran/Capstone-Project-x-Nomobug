{{ config(tags=['calendar', 'weather']) }}
-- Reanalysis association features at Calendar-event grain. These variables
-- describe a roughly 9 km weather grid and must not be presented as causes.
with weather_extent as (
    select max(weather_date) as max_weather_date
    from {{ source('quality', 'open_meteo_weather_daily_all') }}
), aggregated as (
    select
        l.calendar_event_row,
        l.event_date_local,
        l.weather_location_id,
        x.max_weather_date,
        countif(w.weather_date = l.event_date_local) as event_day_rows,
        countif(w.weather_date between date_sub(l.event_date_local, interval 14 day)
            and date_sub(l.event_date_local, interval 1 day)) as prior_14d_days_available,
        max(if(w.weather_date = l.event_date_local, w.temperature_2m_mean_c, null))
            as event_day_temperature_mean_c,
        max(if(w.weather_date = l.event_date_local, w.precipitation_sum_mm, null))
            as event_day_precipitation_mm,
        max(if(w.weather_date = l.event_date_local, w.relative_humidity_2m_mean_pct, null))
            as event_day_relative_humidity_mean_pct,
        max(if(w.weather_date = l.event_date_local, w.soil_moisture_0_to_7cm_mean, null))
            as event_day_soil_moisture_0_to_7cm_mean,
        sum(if(w.weather_date between date_sub(l.event_date_local, interval 3 day)
                and date_sub(l.event_date_local, interval 1 day),
            w.precipitation_sum_mm, null)) as prior_3d_precipitation_mm,
        sum(if(w.weather_date between date_sub(l.event_date_local, interval 7 day)
                and date_sub(l.event_date_local, interval 1 day),
            w.precipitation_sum_mm, null)) as prior_7d_precipitation_mm,
        sum(if(w.weather_date between date_sub(l.event_date_local, interval 14 day)
                and date_sub(l.event_date_local, interval 1 day),
            w.precipitation_sum_mm, null)) as prior_14d_precipitation_mm,
        avg(if(w.weather_date between date_sub(l.event_date_local, interval 7 day)
                and date_sub(l.event_date_local, interval 1 day),
            w.relative_humidity_2m_mean_pct, null)) as prior_7d_relative_humidity_mean_pct,
        avg(if(w.weather_date between date_sub(l.event_date_local, interval 7 day)
                and date_sub(l.event_date_local, interval 1 day),
            w.soil_moisture_0_to_7cm_mean, null)) as prior_7d_soil_moisture_0_to_7cm_mean
    from {{ ref('calendar_event_locations') }} l
    cross join weather_extent x
    left join {{ source('quality', 'open_meteo_weather_daily_all') }} w
      on w.weather_location_id = l.weather_location_id
     and w.weather_date between date_sub(l.event_date_local, interval 14 day)
         and l.event_date_local
    where l.weather_eligible
    group by 1, 2, 3, 4
)
select *,
    case
        when event_date_local > max_weather_date then 'event_after_weather_snapshot'
        when event_day_rows = 1 then 'available'
        else 'missing_from_partial_cache'
    end as weather_coverage_status,
    event_day_rows = 1 as event_day_weather_available,
    prior_14d_days_available = 14 as complete_prior_14d_weather
from aggregated
