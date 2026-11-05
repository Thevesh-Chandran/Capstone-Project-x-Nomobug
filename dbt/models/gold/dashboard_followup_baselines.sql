{{ config(schema='gold', tags=['gold', 'dashboard', 'looker', 'decision_support']) }}
-- Grain is fold x rule. Compare equal review budgets within each fold.
-- Fractions must be calculated from summed counts when combining folds.
select * from {{ ref('cp2_followup_baselines') }}
