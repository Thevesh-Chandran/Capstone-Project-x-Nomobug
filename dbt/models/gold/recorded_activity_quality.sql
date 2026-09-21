{{ config(schema='gold', tags=['gold']) }}
-- A small issue-count mart. Each issue has its own denominator and may overlap
-- other issues; never sum affected_rows across issue types.
with sales as (
    select count(*) as n,
        countif(not include_in_sale_count) as excluded,
        countif(closed_date is null) as undated,
        countif(include_in_sale_count and sale_total_rm is null) as missing_total,
        countif(closed_date_year_source in
            ('early_sequence_inferred', 'adjacent_timestamps_inferred')) as inferred_year
    from {{ ref('sales_package_facts') }}
), payments as (
    select count(*) as n,
        countif(payment_date is null) as undated,
        countif(payment_date_cell_type = 'text') as text_date,
        countif(payment_date > current_date('Asia/Kuala_Lumpur')) as future_date,
        countif(amount_rm is null) as missing_amount,
        countif(reference_status = 'combined') as combined_ref,
        countif(reference_status in ('missing', 'unrecognized',
            'repeated_reference_review')) as bad_ref
    from {{ ref('payment_record_facts') }}
), prospects as (
    select count(*) as n,
        countif(first_reply_date is null) as undated,
        countif(acquisition_needs_review) as acquisition_review,
        countif(status_needs_review) as status_review
    from {{ ref('prospects_2026') }}
    where row_class = 'prospect_candidate'
)
select 'sales' as source_name, issue_code, affected_rows, n as source_rows
from sales, unnest([
    struct('excluded_disposition' as issue_code, excluded as affected_rows),
    struct('undated_close' as issue_code, undated as affected_rows),
    struct('unparsed_or_blank_total' as issue_code, missing_total as affected_rows),
    struct('inferred_close_year' as issue_code, inferred_year as affected_rows)
])
union all
select 'payments', issue_code, affected_rows, n
from payments, unnest([
    struct('undated_payment' as issue_code, undated as affected_rows),
    struct('text_date' as issue_code, text_date as affected_rows),
    struct('future_date' as issue_code, future_date as affected_rows),
    struct('unparsed_or_blank_amount' as issue_code, missing_amount as affected_rows),
    struct('combined_reference' as issue_code, combined_ref as affected_rows),
    struct('reference_needs_review' as issue_code, bad_ref as affected_rows)
])
union all
select 'prospects_2026', issue_code, affected_rows, n
from prospects, unnest([
    struct('undated_first_reply' as issue_code, undated as affected_rows),
    struct('acquisition_needs_review' as issue_code, acquisition_review as affected_rows),
    struct('status_needs_review' as issue_code, status_review as affected_rows)
])
