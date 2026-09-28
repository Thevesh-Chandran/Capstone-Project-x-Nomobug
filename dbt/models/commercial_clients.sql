{{ config(tags=['operational']) }}
select *,
    '{{ source("operational_bronze", "commercial_clients").identifier }}' as snapshot_table,
    concat('{{ source("operational_bronze", "commercial_clients").identifier }}', ':', cast(source_sheet_row as string)) as commercial_client_record_id,
    source_column_006 as customer_id_raw,
    source_column_003 as closed_date_raw,
    source_column_004 as first_contact_date_raw,
    source_column_013 as total_sessions_raw,
    source_column_014 as done_sessions_raw,
    source_column_015 as balance_sessions_raw,
    source_column_016 as first_session_date_raw,
    source_column_017 as second_session_date_raw,
    source_column_018 as third_session_date_raw,
    source_column_026 as sale_total_raw,
    source_column_027 as deposit_paid_raw,
    source_column_029 as balance_paid_raw
from {{ source('operational_bronze', 'commercial_clients') }}
