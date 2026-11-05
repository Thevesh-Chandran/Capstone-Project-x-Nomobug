{{ config(schema='gold', tags=['gold', 'dashboard', 'looker', 'decision_support']) }}
-- Already-inspected development evidence; means of fold metrics, not fresh accuracy.
select * from {{ ref('cp2_environment_comparison') }}
