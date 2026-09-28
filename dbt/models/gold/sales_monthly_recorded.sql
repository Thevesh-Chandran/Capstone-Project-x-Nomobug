{{ config(schema='gold', tags=['gold']) }}
-- Package face value by recorded close month, NOT earned revenue or cash.
-- A null month explicitly retains packages whose close date cannot be parsed.
select
    snapshot_table,
    date_trunc(closed_date, month) as closed_month,
    count(*) as package_rows,
    countif(include_in_sale_count and closed_date is not null
        and closed_date <= current_date('Asia/Kuala_Lumpur')) as countable_package_rows,
    sum(if(include_in_sale_count and closed_date is not null
        and closed_date <= current_date('Asia/Kuala_Lumpur'), sale_total_rm, null))
        as recorded_package_face_value_rm,
    countif(include_in_sale_count and sale_total_rm is null) as unparsed_or_blank_total_rows,
    countif(not include_in_sale_count) as excluded_disposition_rows,
    countif(closed_date is null) as undated_rows,
    countif(closed_date > current_date('Asia/Kuala_Lumpur')) as future_dated_rows,
    countif(closed_date_year_source in
        ('early_sequence_inferred', 'adjacent_timestamps_inferred')) as inferred_year_rows
from {{ ref('sales_package_facts') }}
group by snapshot_table, closed_month
