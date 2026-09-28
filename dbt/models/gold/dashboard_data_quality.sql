{{ config(schema='gold', tags=['gold', 'dashboard', 'looker']) }}
-- Aggregate issue counts only. A row is one issue/one source denominator;
-- issue populations may overlap and must never be added across issue codes.
select
    source_name,
    issue_code,
    affected_rows,
    source_rows,
    safe_divide(affected_rows, source_rows) as affected_share,
    current_date('Asia/Kuala_Lumpur') as reviewed_date,
    'issue_counts_overlap; use each source denominator separately' as denominator_evidence
from {{ ref('recorded_activity_quality') }}
