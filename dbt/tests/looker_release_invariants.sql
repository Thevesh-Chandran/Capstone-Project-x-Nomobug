select 'spatial_low_volume_exposed' as failure
from {{ ref('dashboard_spatial_area') }}
where scheduled_service_event_rows < 5
union all
select 'recurrence_non_signal_exposed'
from {{ ref('dashboard_recurrence_monthly') }}
where recorded_warranty_signal_rows <= 0
union all
select 'ml_status_not_explicit'
from {{ ref('dashboard_ml_evaluation') }}
where experiment_status != 'evaluated_weather_inclusive_not_causal_or_production_ready'
union all
select 'dbscan_cluster_below_minimum_size'
from {{ ref('dashboard_spatial_cluster_summary') }}
where distinct_service_properties < 3
union all
select 'weather_coverage_invalid'
from {{ ref('dashboard_weather_monthly') }}
where complete_prior_14d_weather_rows > scheduled_event_rows
   or complete_weather_coverage_share < 0
   or complete_weather_coverage_share > 1
