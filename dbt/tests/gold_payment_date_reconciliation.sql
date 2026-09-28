{{ config(tags=['gold']) }}
select 'missing_date_sidecar' as failure
from {{ ref('payments') }} p
left join {{ source('operational_bronze', 'payments_date_serials') }} d using (source_sheet_row)
where d.source_sheet_row is null
union all
select 'duplicate_date_sidecar'
from {{ source('operational_bronze', 'payments_date_serials') }}
group by source_sheet_row
having count(*) != 1
union all
select 'display_date_changed'
from {{ ref('payment_record_facts') }} g
join {{ source('operational_bronze', 'payments_date_serials') }} d using (source_sheet_row)
where g.payment_date_raw is distinct from d.payment_date_display_raw
union all
select 'serial_not_dated'
from {{ ref('payment_record_facts') }}
where payment_date_cell_type = 'serial' and payment_date is null
