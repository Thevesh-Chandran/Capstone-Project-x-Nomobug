{{ config(tags=['gold']) }}
select 'sales_package_count' as failure
from unnest([1])
where (select count(*) from {{ ref('sales_package_facts') }}) !=
      (select count(*) from {{ ref('sales') }} where sales_record_id is not null)
union all
select 'payment_record_count'
from unnest([1])
where (select count(*) from {{ ref('payment_record_facts') }}) !=
      (select count(*) from {{ ref('payments') }})
union all
select 'calendar_service_event_count'
from unnest([1])
where (select count(*) from {{ ref('calendar_service_event_facts') }}) !=
      (select count(*) from {{ ref('calendar_events') }} where service_candidate)
union all
select 'calendar_match_preserved'
from {{ ref('calendar_service_event_facts') }} g
join {{ ref('calendar_event_matches') }} m using (calendar_event_row)
where g.sales_record_id is distinct from m.matched_sales_record_id
union all
select 'sale_override_mismatch'
from {{ ref('sales_package_facts') }} s
join {{ ref('sale_disposition_overrides') }} o using (sales_record_id)
where s.sale_disposition != o.disposition or s.include_in_sale_count
union all
select 'unexpected_sale_exclusion'
from {{ ref('sales_package_facts') }} s
left join {{ ref('sale_disposition_overrides') }} o using (sales_record_id)
where not s.include_in_sale_count and o.sales_record_id is null
