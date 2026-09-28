{{ config(schema='gold', tags=['gold', 'dashboard', 'looker']) }}
-- Aggregate-only metrics from the frozen late-August v5 holdout. No customer,
-- service, or prediction row is exposed. Regenerate the seed from the committed
-- evaluation JSON with scripts/generate_dashboard_ml_seed.py before publishing.
select
    timestamp '2026-09-27 13:45:56.893403+00' as run_utc,
    case model_role
        when 'reference' then 'Corrected reference ExtraTrees depth 6'
        when 'selected_ap' then 'Selected v5 ExtraTrees depth 10'
    end as model_name,
    model_role,
    metric_name,
    cast(metric_value as float64) as metric_value,
    5333 as training_rows,
    100 as holdout_rows,
    492 as training_positive_rows,
    5 as holdout_positive_rows,
    'recorded corrective Calendar callback within days 1-30 after a paid service' as target_definition,
    'immediately after the paid service ends' as prediction_time_definition,
    'Calendar evidence; scheduled visits do not prove biological recurrence or completion' as label_evidence,
    'later 15-27 August 2026 services; training outcomes completed by 14 August' as split_definition,
    'frozen v5 operational, history, location and weather features' as feature_set_definition,
    '100 services; 5 callback-positive service windows' as evaluation_cohort,
    'retrospective_later_services_not_online_or_production_ready' as experiment_status
from {{ ref('cp2_v5_holdout_metrics') }}
