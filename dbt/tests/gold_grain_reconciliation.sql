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
select 'sale_override_mismatch'
from {{ ref('sales_package_facts') }} s
join {{ ref('sale_disposition_overrides') }} o using (sales_record_id)
where s.sale_disposition != o.disposition or s.include_in_sale_count
union all
select 'unexpected_sale_exclusion'
from {{ ref('sales_package_facts') }} s
left join {{ ref('sale_disposition_overrides') }} o using (sales_record_id)
where not s.include_in_sale_count and o.sales_record_id is null
