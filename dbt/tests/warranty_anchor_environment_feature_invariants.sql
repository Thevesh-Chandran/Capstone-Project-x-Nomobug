-- Fail on grain changes, future weather, incomplete-window values or broken
-- physical/count bounds. No source Calendar text or customer details are read.
{% set windows = [1, 3, 7, 14, 30] %}
with features as (
    select * from {{ ref('warranty_anchor_environment_features') }}
), invalid_rows as (
    select calendar_event_row,
        case
            when calendar_event_row is null then 'missing_event_row'
            when event_date_local is null then 'missing_anchor_date'
            when latest_weather_date_used >= event_date_local then 'future_weather'
            {% for days in windows %}
            when prior_{{ days }}d_weather_rows > {{ days }}
              or prior_{{ days }}d_weather_days_available > {{ days }}
                then 'duplicate_or_invalid_{{ days }}d_weather_grain'
            when complete_prior_{{ days }}d_weather
              and (prior_{{ days }}d_weather_rows != {{ days }}
                or prior_{{ days }}d_weather_days_available != {{ days }}
                or prior_{{ days }}d_precipitation_mm is null)
                then 'inconsistent_complete_{{ days }}d_window'
            when not complete_prior_{{ days }}d_weather
              and prior_{{ days }}d_precipitation_mm is not null
                then 'partial_{{ days }}d_precipitation'
            when prior_{{ days }}d_precipitation_mm < 0
                then 'negative_{{ days }}d_precipitation'
            {% endfor %}
            {% for days in [7, 14, 30] %}
            when prior_{{ days }}d_wet_days_1mm not between 0 and {{ days }}
              or (not complete_prior_{{ days }}d_weather
                  and prior_{{ days }}d_wet_days_1mm is not null)
                then 'invalid_{{ days }}d_wet_day_count'
            {% endfor %}
            {% for days in [7, 30] %}
            when prior_{{ days }}d_relative_humidity_mean_pct not between 0 and 100
              or prior_{{ days }}d_soil_moisture_0_to_7cm_mean not between 0 and 1
                then 'invalid_{{ days }}d_moisture_bounds'
            when not complete_prior_{{ days }}d_weather
              and (prior_{{ days }}d_temperature_mean_c is not null
                or prior_{{ days }}d_relative_humidity_mean_pct is not null
                or prior_{{ days }}d_soil_moisture_0_to_7cm_mean is not null)
                then 'partial_{{ days }}d_weather_mean'
            {% endfor %}
            when prior_7d_precipitation_mm < prior_3d_precipitation_mm
              or prior_14d_precipitation_mm < prior_7d_precipitation_mm
              or prior_30d_precipitation_mm < prior_14d_precipitation_mm
                then 'non_monotonic_rain_sums'
            when prior_14d_heavy_rain_days_10mm not between 0 and 14
              or prior_14d_heavy_rain_days_10mm > prior_14d_wet_days_1mm
                then 'invalid_heavy_rain_day_count'
            when prior_14d_max_daily_precipitation_mm < 0
              or prior_14d_max_daily_precipitation_mm > prior_14d_precipitation_mm
                then 'invalid_maximum_daily_precipitation'
            when days_since_last_rain_1mm_capped_30d not between 1 and 30
              or (not complete_prior_30d_weather
                  and days_since_last_rain_1mm_capped_30d is not null)
                then 'invalid_rain_recency'
            when prior_7d_temperature_max_c < prior_7d_temperature_mean_c
              or (not complete_prior_7d_weather and prior_7d_temperature_max_c is not null)
                then 'invalid_maximum_daily_mean_temperature'
            when not complete_prior_14d_weather
              and (prior_14d_heavy_rain_days_10mm is not null
                or prior_14d_max_daily_precipitation_mm is not null
                or prior_3d_vs_previous_11d_daily_rain_trend_mm is not null)
                then 'partial_14d_rain_summary'
        end as issue
    from features
)
select calendar_event_row, issue
from invalid_rows
where issue is not null
union all
select calendar_event_row, 'duplicate_event_row' as issue
from features
group by calendar_event_row
having count(*) != 1
