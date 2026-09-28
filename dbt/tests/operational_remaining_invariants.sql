{{ config(tags=['operational']) }}
select 'payment_link_row_count' as check_name from unnest([1])
where (select count(*) from {{ source('operational_bronze', 'payment_link') }}) != (select count(*) from {{ ref('payment_link') }})
union all
select 'warranty_claim_row_count' from unnest([1])
where (select count(*) from {{ source('operational_bronze', 'warranty_claim') }}) != (select count(*) from {{ ref('warranty_claim') }})
union all
select 'commercial_clients_row_count' from unnest([1])
where (select count(*) from {{ source('operational_bronze', 'commercial_clients') }}) != (select count(*) from {{ ref('commercial_clients') }})
union all
select 'refund_row_count' from unnest([1])
where (select count(*) from {{ source('operational_bronze', 'refund') }}) != (select count(*) from {{ ref('refund') }})
union all
select 'recurring_payments_row_count' from unnest([1])
where (select count(*) from {{ source('operational_bronze', 'recurring_payments') }}) != (select count(*) from {{ ref('recurring_payments') }})
union all
select 'payment_link_record_id_unique'
from {{ ref('payment_link') }}
group by payment_link_record_id
having count(*) != 1
union all
select 'warranty_claim_record_id_unique'
from {{ ref('warranty_claim') }}
group by warranty_claim_record_id
having count(*) != 1
union all
select 'commercial_client_record_id_unique'
from {{ ref('commercial_clients') }}
group by commercial_client_record_id
having count(*) != 1
union all
select 'refund_record_id_unique'
from {{ ref('refund') }}
group by refund_record_id
having count(*) != 1
union all
select 'recurring_payment_record_id_unique'
from {{ ref('recurring_payments') }}
group by recurring_payment_record_id
having count(*) != 1
