{{ config(tags=['operational']) }}
with sales_lookup as (
    select sales_record_id, count(*) as sales_rows
    from {{ ref('sales') }} where sales_record_id is not null group by sales_record_id
), links as (
    select distinct p.payment_record_id, sales_record_id, p.reference_status
    from {{ ref('payments') }} p, unnest(p.sales_references) sales_record_id
)
select links.*,
    case when s.sales_rows = 1 then 'matched'
         when s.sales_rows is null then 'missing' else 'ambiguous' end as sales_match_status,
    cast(null as numeric) as allocated_amount_rm
-- Payment amount intentionally absent. Never sum money through this bridge.
from links left join sales_lookup s using (sales_record_id)
