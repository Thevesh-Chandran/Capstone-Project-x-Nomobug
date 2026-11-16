{{ config(tags=['gold']) }}
select 'reviewed_programme_missing_or_duplicated' as failure
from (select count(*) as programme_rows
      from {{ ref('service_programme_warranty_windows') }}
      where programme_id='UPGRADE_0001')
where programme_rows != 1
union all
select 'programme_member_source_changed' as failure
from {{ ref('service_programme_memberships') }} m
left join {{ ref('sales_package_facts') }} s using(sales_record_id)
where s.sales_record_id is null or s.source_sheet_row != m.expected_source_sheet_row
   or s.package_sessions_recorded is distinct from m.expected_sessions
   or s.sale_total_rm is distinct from cast(m.expected_sale_total_rm as numeric)
   or not s.include_in_sale_count or s.premise_type is distinct from m.expected_premise_type
union all
select 'duplicate_programme_member'
from {{ ref('service_programme_memberships') }} group by sales_record_id having count(*) != 1
union all
select 'invalid_paid_stage_funding'
from {{ ref('active_paid_programme_visit_overrides') }} o
left join {{ ref('service_programme_memberships') }} m
    on o.funding_sales_record_id=m.sales_record_id and o.programme_id=m.programme_id
where m.sales_record_id is null or o.paid_programme_stage <= m.session_offset
   or o.paid_programme_stage > m.session_offset+m.expected_sessions
union all
select 'duplicate_paid_programme_stage'
from {{ ref('active_paid_programme_visit_overrides') }}
group by programme_id, paid_programme_stage having count(*) != 1
union all
select 'one_event_assigned_to_multiple_paid_stages'
from {{ ref('active_paid_programme_visit_overrides') }}
where calendar_event_row is not null
group by calendar_event_row having count(*) != 1
union all
select 'resolved_paid_visit_not_applied'
from {{ ref('active_paid_programme_visit_overrides') }} o
left join {{ ref('calendar_programme_service_facts') }} f
    on f.calendar_event_row = o.calendar_event_row
   and f.programme_id = o.programme_id
   and f.paid_programme_stage = o.paid_programme_stage
   and f.owner_confirmed_paid_stage and f.event_category = 'service'
where o.calendar_event_row is not null and f.calendar_event_row is null
union all
select 'upgrade_sales_or_warranty_policy_incorrect'
from {{ ref('service_programme_warranty_windows') }}
where programme_id='UPGRADE_0001' and (
    effective_paid_sessions != 3 or source_sales_rows != 2 or recorded_programme_value_rm != 640
    or not warranty_policy_eligible)
union all
select 'commercial_24_programme_incorrect'
from {{ ref('service_programme_warranty_windows') }}
where programme_id='CONTRACT_0002' and (
    effective_paid_sessions != 24 or source_sales_rows != 2
    or recorded_programme_value_rm != 3960
    or warranty_policy_eligible or warranty_policy_rule != 'NO_WARRANTY')
union all
select 'commercial_programme_pooled_earlier_separate_sale'
from {{ ref('service_programme_memberships') }}
where programme_id='CONTRACT_0002' and sales_record_id not in ('CUST1412','CUST1569')
