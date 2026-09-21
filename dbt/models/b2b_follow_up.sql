{{ config(tags=['operational']) }}
select *,
    {{ b2b_remaining_raw_aliases() }}
    '{{ source("operational_bronze", "b2b").identifier }}' as snapshot_table,
    concat('{{ source("operational_bronze", "b2b").identifier }}', ':', cast(source_sheet_row as string)) as b2b_record_id,
    trim(source_column_003) != '' as phone_present_candidate,
    source_column_003 as phone_raw,
    source_column_005 as business_name_raw,
    nullif(upper(trim(source_column_007)), '') as status_label,
    source_column_001 as engage_date_raw,
    source_column_014 as closing_date_raw,
    source_column_015 as appointment_date_raw
-- No completion or sale inference from status or automatic dates.
from {{ source('operational_bronze', 'b2b') }}
