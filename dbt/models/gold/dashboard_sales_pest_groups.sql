{{ config(schema='gold', tags=['gold', 'dashboard']) }}
-- Sales by recorded close month and standard pest group, for dashboard pest charts.
-- Groups the free-text Sales pest names (over 140 spellings) into 23 or so standard categories.
-- Package face value, NOT earned revenue or cash. Null month keeps undated packages.
select
    date_trunc(closed_date, month) as closed_month,
    {{ pest_group('pest_type_raw') }} as pest_group,
    countif(include_in_sale_count) as countable_package_rows,
    sum(if(include_in_sale_count, sale_total_rm, null)) as recorded_package_face_value_rm,
    countif(include_in_sale_count and sale_total_rm is null) as unparsed_or_blank_total_rows
from {{ ref('sales_package_facts') }}
where closed_date is null or closed_date <= current_date('Asia/Kuala_Lumpur')
group by closed_month, pest_group
