{{ config(schema='gold', tags=['gold'], materialized='table') }}
-- Programme grain is separate from sales/payments. Only owner-confirmed links
-- are pooled; each ordinary sale retains its own programme.
with members as (
    select s.*,
        coalesce(m.programme_id, concat('SALE_', s.sales_record_id)) as programme_id,
        coalesce(m.session_offset, 0) as session_offset
    from {{ ref('sales_package_facts') }} s
    left join {{ ref('service_programme_memberships') }} m using (sales_record_id)
), grouped as (
    select programme_id,
        count(*) as source_sales_rows,
        sum(package_sessions_recorded) as effective_paid_sessions,
        sum(sale_total_rm) as recorded_programme_value_rm,
        countif(sale_total_rm is null) as unknown_sale_value_rows,
        min(closed_date) as programme_first_sale_date,
        count(distinct premise_type) = 1 and min(premise_type) = 'RESIDENTIAL' as residential_programme,
        countif(not include_in_sale_count) > 0 as has_cancelled_sale
    from members group by programme_id
)
select *, residential_programme and not has_cancelled_sale
    and effective_paid_sessions in (3,4,6,12) as warranty_policy_eligible,
    case when has_cancelled_sale then 'REVIEW_CANCELLED_MEMBER'
         when not residential_programme or effective_paid_sessions = 1 then 'NO_WARRANTY'
         when effective_paid_sessions = 3 then 'POST_FINAL_SERVICE_30D'
         when effective_paid_sessions in (4,6,12) then 'FIRST_SERVICE_THROUGH_30D_AFTER_FINAL_UNLIMITED_CLAIMS'
         else 'REVIEW_UNDEFINED_POLICY' end as warranty_policy_rule
from grouped
