{{ config(tags=['operational']) }}
select *,
    '{{ source("operational_bronze", "warranty_claim").identifier }}' as snapshot_table,
    concat('{{ source("operational_bronze", "warranty_claim").identifier }}', ':', cast(source_sheet_row as string)) as warranty_claim_record_id,
    source_column_001 as claim_date_raw,
    source_column_002 as customer_id_raw,
    source_column_003 as purchase_date_raw,
    source_column_004 as warranty_end_date_raw,
    source_column_005 as complimentary_service_date_raw,
    source_column_006 as warranty_claim_service_date_raw,
    source_column_007 as refund_date_raw,
    source_column_008 as service_technician_1_raw,
    source_column_009 as service_technician_2_raw,
    source_column_010 as service_technician_3_raw,
    source_column_011 as service_technician_4_raw,
    source_column_012 as service_technician_5_raw,
    source_column_013 as service_technician_6_raw,
    source_column_014 as service_technician_7_raw
from {{ source('operational_bronze', 'warranty_claim') }}
