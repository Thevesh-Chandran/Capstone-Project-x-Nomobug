{{ config(schema='gold', tags=['gold']) }}
-- Recorded PAYMENTS entries, NOT confirmed cash or per-sale allocation.
-- Combined references remain one row. A null month keeps undated entries visible.
select
    snapshot_table,
    date_trunc(payment_date, month) as payment_month,
    count(*) as payment_rows,
    countif(payment_date is not null and
        payment_date <= current_date('Asia/Kuala_Lumpur')) as dated_nonfuture_rows,
    sum(if(payment_date is not null and
        payment_date <= current_date('Asia/Kuala_Lumpur'), amount_rm, null))
        as recorded_payment_entry_amount_rm,
    countif(amount_rm is null) as unparsed_or_blank_amount_rows,
    countif(payment_date_cell_type = 'text') as text_date_review_rows,
    countif(payment_date is null) as undated_rows,
    countif(payment_date > current_date('Asia/Kuala_Lumpur')) as future_dated_rows,
    countif(reference_status = 'combined') as combined_reference_rows,
    countif(reference_status in ('missing', 'unrecognized',
        'repeated_reference_review')) as reference_review_rows
from {{ ref('payment_record_facts') }}
group by snapshot_table, payment_month
