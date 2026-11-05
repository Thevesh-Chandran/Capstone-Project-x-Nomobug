{{ config(schema='gold', tags=['gold', 'dashboard', 'looker', 'decision_support']) }}
-- One row per rule on the SAME fixed retrospective cohort. Never sum cohort sizes.
select * from {{ ref('cp2_review_capacity') }}
