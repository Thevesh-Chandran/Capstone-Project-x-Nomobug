{{ config(tags=['gold']) }}
select 'refund_rows_not_preserved' as failure
from unnest([1])
where (select count(*) from {{ ref('refund_record_facts') }}) !=
      (select count(*) from {{ ref('refund') }})
union all
select 'warranty_claim_rows_not_preserved'
from unnest([1])
where (select count(*) from {{ ref('warranty_claim_record_facts') }}) !=
      (select count(*) from {{ ref('warranty_claim') }})
union all
select 'ambiguous_refund_amount_parsed'
from {{ ref('refund_record_facts') }}
where regexp_contains(lower(refund_amount_raw), r'\bor\b')
  and recorded_refund_amount_rm is not null
union all
select 'refund_exact_link_mismatch'
from {{ ref('refund_record_facts') }} r
join {{ ref('refund') }} src using (source_sheet_row)
where (r.sale_link_status = 'exact_sale_id') is distinct from
      coalesce(upper(trim(src.customer_id_raw)) = r.sales_record_id, false)
union all
select 'claim_exact_link_mismatch'
from {{ ref('warranty_claim_record_facts') }} w
join {{ ref('warranty_claim') }} src using (source_sheet_row)
where (w.sale_link_status = 'exact_sale_id') is distinct from
      coalesce(upper(trim(src.customer_id_raw)) = w.sales_record_id, false)
