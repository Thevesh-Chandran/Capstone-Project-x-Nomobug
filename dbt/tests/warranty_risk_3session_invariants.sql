select case
    when outcome_window_end_date > observed_through then 'immature_outcome_window'
    when prediction_anchor_date < closed_date then 'anchor_before_sale'
    when completion_anchor_count != 1 then 'non_unique_completion_anchor'
    when premise_type != 'RESIDENTIAL' then 'non_residential_model_row'
    when package_sessions_recorded != 3 then 'non_3x_model_row'
    when warranty_signal_within_14d and not warranty_signal_within_30d
        then '14d_target_not_nested_in_30d'
    when warranty_signal_within_30d and warranty_signal_within_60d is false
        then '30d_target_not_nested_in_60d'
    when warranty_signal_within_60d and warranty_signal_within_90d is false
        then '60d_target_not_nested_in_90d'
    when team_events_prior_7d < team_events_before_anchor_same_day
        then 'same_day_workload_exceeds_7d_workload'
    when not environmental_context_available
        then 'missing_environmental_context'
    when elevation_m < -100 or elevation_m > 1000
        then 'implausible_elevation'
    when local_relief_500m_m < 0 or local_relief_500m_m > 1000
        then 'implausible_local_relief'
    when nearest_mapped_water_m < 0 or nearest_mapped_water_m > 2000
        then 'invalid_water_distance'
    when nearest_mapped_forest_m < 0 or nearest_mapped_forest_m > 2000
        then 'invalid_forest_distance'
    when mapped_water_features_2km < 0 or mapped_forest_features_2km < 0
        then 'invalid_environment_feature_count'
    when not hotosm_waterway_context_available
        then 'missing_hotosm_waterway_context'
    when hotosm_nearest_waterway_m < 0
      or hotosm_water_features_500m < 0
      or hotosm_water_features_1km < hotosm_water_features_500m
      or hotosm_water_features_2km < hotosm_water_features_1km
        then 'invalid_hotosm_waterway_context'
    when prior_team_warranty_rate_smoothed not between 0 and 1
      or prior_area_warranty_rate_smoothed not between 0 and 1
      or prior_pest_premise_warranty_rate_smoothed not between 0 and 1
      or prior_pest_premise_warranty_rate_90d_smoothed not between 0 and 1
        then 'invalid_smoothed_historical_rate'
    when rain_humidity_7d_interaction is null
      or rain_soil_moisture_interaction is null
        then 'missing_weather_interaction'
    else 'invalid_split_boundary'
end as failure
from {{ ref('warranty_risk_3session_dataset') }}
where outcome_window_end_date > observed_through
   or prediction_anchor_date < closed_date
   or completion_anchor_count != 1
   or premise_type != 'RESIDENTIAL'
   or package_sessions_recorded != 3
   or (warranty_signal_within_14d and not warranty_signal_within_30d)
   or (warranty_signal_within_30d and warranty_signal_within_60d is false)
   or (warranty_signal_within_60d and warranty_signal_within_90d is false)
   or team_events_prior_7d < team_events_before_anchor_same_day
   or not environmental_context_available
   or elevation_m < -100 or elevation_m > 1000
   or local_relief_500m_m < 0 or local_relief_500m_m > 1000
   or nearest_mapped_water_m < 0 or nearest_mapped_water_m > 2000
   or nearest_mapped_forest_m < 0 or nearest_mapped_forest_m > 2000
   or mapped_water_features_2km < 0 or mapped_forest_features_2km < 0
   or not hotosm_waterway_context_available
   or hotosm_nearest_waterway_m < 0
   or hotosm_water_features_500m < 0
   or hotosm_water_features_1km < hotosm_water_features_500m
   or hotosm_water_features_2km < hotosm_water_features_1km
   or prior_team_warranty_rate_smoothed not between 0 and 1
   or prior_area_warranty_rate_smoothed not between 0 and 1
   or prior_pest_premise_warranty_rate_smoothed not between 0 and 1
   or prior_pest_premise_warranty_rate_90d_smoothed not between 0 and 1
   or rain_humidity_7d_interaction is null
   or rain_soil_moisture_interaction is null
   or (evaluation_split = 'train_2024_2025' and prediction_anchor_date >= date '2026-01-01')
   or (evaluation_split = 'holdout_2026' and prediction_anchor_date < date '2026-01-01')
