{{ config(schema='gold', tags=['gold', 'dashboard', 'looker']) }}
-- Latest aggregate held-out experiment metrics only. Individual package scores
-- are intentionally excluded from the dashboard release layer.
select
    run_utc,
    model_name,
    metric_name,
    metric_value,
    training_rows,
    holdout_rows,
    training_positive_rows,
    holdout_positive_rows,
    target_definition,
    prediction_time_definition,
    label_evidence,
    split_definition,
    feature_set_definition,
    evaluation_cohort,
    experiment_status
from {{ source('analytics_ml_outputs', 'warranty_risk_3session_run_metrics') }}
where run_utc = (
    select max(run_utc)
    from {{ source('analytics_ml_outputs', 'warranty_risk_3session_run_metrics') }}
)
