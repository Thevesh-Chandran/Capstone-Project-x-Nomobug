{{ config(tags=['gold']) }}
select 'reviewed_programme_missing_or_duplicated' as failure
from (select count(*) as programme_rows
      from {{ ref('service_programme_warranty_windows') }}
      where programme_id='UPGRADE_0001')
where programme_rows != 1
union all
select 'programme_previous_category_uses_different_partition'
from {{ ref('dashboard_recurrence_windows') }} w
join {{ ref('calendar_programme_service_facts') }} f using(calendar_event_row)
where f.programme_id='UPGRADE_0001' and f.paid_programme_stage in (2,3)
  and w.previous_event_category is distinct from 'service'
union all
select 'programme_member_source_changed' as failure
from {{ ref('service_programme_memberships') }} m
left join {{ ref('sales_package_facts') }} s using(sales_record_id)
where s.sales_record_id is null or s.source_sheet_row != m.expected_source_sheet_row
   or s.package_sessions_recorded != m.expected_sessions
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
select 'reviewed_paid_visit_missing_or_multiply_matched'
from {{ ref('active_paid_programme_visit_overrides') }} o
left join {{ ref('calendar_programme_service_facts') }} f
    on f.programme_id = o.programme_id and f.paid_programme_stage = o.paid_programme_stage
   and f.owner_confirmed_paid_stage
group by o.event_identity_hash having count(f.calendar_event_row) != 1
union all
select 'upgrade_not_three_paid_stages_two_sales_640_rm_or_warranty'
from {{ ref('service_programme_warranty_windows') }}
where programme_id='UPGRADE_0001' and (
    effective_paid_sessions != 3 or source_sales_rows != 2 or recorded_programme_value_rm != 640
    or recorded_paid_visit_rows != 3 or reviewed_paid_stages != 3
    or recorded_warranty_start_date is distinct from date '2026-04-04'
    or recorded_warranty_end_date is distinct from date '2026-05-04'
    or not warranty_policy_eligible)
union all
select 'commercial_24_programme_incorrect'
from {{ ref('service_programme_warranty_windows') }}
where programme_id='CONTRACT_0002' and (
    effective_paid_sessions != 24 or source_sales_rows != 2
    or recorded_programme_value_rm != 3960
    or recorded_paid_visit_rows != (select count(*) from {{ ref('active_paid_programme_visit_overrides') }} where programme_id='CONTRACT_0002')
    or reviewed_paid_stages != (select count(*) from {{ ref('active_paid_programme_visit_overrides') }} where programme_id='CONTRACT_0002')
    or warranty_policy_eligible or warranty_policy_rule != 'NO_WARRANTY')
union all
select 'commercial_programme_pooled_earlier_separate_sale'
from {{ ref('service_programme_memberships') }}
where programme_id='CONTRACT_0002' and sales_record_id not in ('CUST1412','CUST1569')
