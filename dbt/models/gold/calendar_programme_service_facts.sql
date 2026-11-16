{{ config(schema='gold', tags=['gold'], materialized='table') }}
-- Corrected operational facts. Frozen historical/compiled model facts remain
-- separate. Source match/category are retained; paid visits use their funding sale.
select f.* except (sales_record_id, event_category, extra_visit_candidate),
    coalesce(o.funding_sales_record_id, f.sales_record_id) as sales_record_id,
    if(o.event_identity_hash is not null, 'service', f.event_category) as event_category,
    if(o.event_identity_hash is not null, false, f.extra_visit_candidate) as extra_visit_candidate,
    f.sales_record_id as source_matched_sales_record_id,
    f.event_category as source_event_category,
    coalesce(o.programme_id, m.programme_id, concat('SALE_', f.sales_record_id)) as programme_id,
    o.paid_programme_stage,
    p.effective_paid_sessions,
    p.warranty_policy_eligible as programme_warranty_policy_eligible,
    p.warranty_policy_rule as programme_warranty_policy_rule,
    o.event_identity_hash is not null as owner_confirmed_paid_stage
from {{ ref('calendar_service_event_facts') }} f
left join {{ ref('active_paid_programme_visit_overrides') }} o using (calendar_event_row)
left join {{ ref('service_programme_memberships') }} m
    on f.sales_record_id = m.sales_record_id
left join {{ ref('service_programme_facts') }} p
    on p.programme_id = coalesce(o.programme_id, m.programme_id, concat('SALE_', f.sales_record_id))
