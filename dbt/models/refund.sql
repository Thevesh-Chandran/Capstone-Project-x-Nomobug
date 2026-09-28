{{ config(tags=['operational']) }}
select * except (source_column_008, source_column_009),
    '{{ source("operational_bronze", "refund").identifier }}' as snapshot_table,
    concat('{{ source("operational_bronze", "refund").identifier }}', ':', cast(source_sheet_row as string)) as refund_record_id,
    source_column_001 as refund_date_raw,
    source_column_002 as customer_id_raw,
    source_column_003 as customer_name_raw,
    source_column_004 as phone_raw,
    source_column_005 as purchase_date_raw,
    source_column_006 as refund_reason_raw,
    source_column_007 as refund_amount_raw,
    source_column_010 as refund_status_raw,
    upper(trim(source_column_010)) as refund_status
from {{ source('operational_bronze', 'refund') }}
