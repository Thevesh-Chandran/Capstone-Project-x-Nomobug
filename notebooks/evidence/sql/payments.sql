{{ config(tags=['operational']) }}
with prepared as (
    select *,
        {{ sales_reference_array('source_column_002') }} as sales_references,
        {{ rm_decimal('source_column_003') }} as amount_rm
    from {{ source('operational_bronze', 'payments') }}
)
select *,
    {{ payments_remaining_raw_aliases() }}
    '{{ source("operational_bronze", "payments").identifier }}' as snapshot_table,
    concat('{{ source("operational_bronze", "payments").identifier }}', ':', cast(source_sheet_row as string)) as payment_record_id,
    source_column_002 as sales_references_raw,
    source_column_001 as payment_date_raw,
    source_column_007 as completion_status_raw,
    trim(source_column_002) != '' as id_present_candidate,
    amount_rm is null as amount_needs_review,
    case
        when trim(source_column_002) = '' then 'missing'
        when array_length(sales_references) = 0 then 'unrecognized'
        when array_length(sales_references) != (select count(distinct id) from unnest(sales_references) id) then 'repeated_reference_review'
        when array_length(sales_references) > 1 then 'combined'
        else 'single'
    end as reference_status
-- Every raw row remains, including repeats, tests and placeholders. Not a cash KPI yet.
from prepared
