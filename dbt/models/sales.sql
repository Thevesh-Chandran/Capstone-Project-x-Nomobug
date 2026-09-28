{{ config(tags=['operational']) }}
with prepared as (
    select *,
        {{ sales_reference_array('source_column_007') }} as parsed_sales_ids,
        {{ rm_decimal('source_column_028') }} as sale_total_rm
    from {{ source('operational_bronze', 'sales') }}
)
select *,
    {{ sales_remaining_raw_aliases() }}
    '{{ source("operational_bronze", "sales").identifier }}' as snapshot_table,
    concat('{{ source("operational_bronze", "sales").identifier }}', ':', cast(source_sheet_row as string)) as sales_row_id,
    source_column_007 as customer_id_raw,
    case when array_length(parsed_sales_ids) = 1 then parsed_sales_ids[offset(0)] end as sales_record_id,
    trim(source_column_007) != '' as id_present_candidate,
    trim(source_column_007) != '' and array_length(parsed_sales_ids) != 1 as id_needs_review,
    trim(source_column_028) != '' and sale_total_rm is null as total_needs_review,
    regexp_contains(upper(source_column_008), r'\b(?:OLD|RETURNING)\b') as recorded_returning_client,
    source_column_008 as acquisition_relationship_raw,
    source_column_010 as phone_raw,
    source_column_004 as closed_date_raw,
    source_column_030 as deposit_invoice_raw,
    source_column_032 as balance_invoice_raw
-- CUSTOMER ID identifies a sale, NOT a person. Neither #VALUE! column is mapped yet.
from prepared
