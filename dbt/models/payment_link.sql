{{ config(tags=['operational']) }}
select *,
    '{{ source("operational_bronze", "payment_link").identifier }}' as snapshot_table,
    concat('{{ source("operational_bronze", "payment_link").identifier }}', ':', cast(source_sheet_row as string)) as payment_link_record_id,
    source_column_001 as payment_link_date_raw,
    source_column_002 as phone_raw,
    source_column_003 as info_requested_raw,
    source_column_004 as invoice_shared_raw,
    source_column_005 as outcome_raw,
    source_column_006 as remarks_raw,
    nullif(upper(trim(source_column_005)), '') as payment_link_status,
    upper(trim(source_column_005)) = 'WON' as payment_link_success_flag
from {{ source('operational_bronze', 'payment_link') }}
