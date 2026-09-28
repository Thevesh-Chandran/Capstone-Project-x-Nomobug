{{ config(schema='gold', tags=['gold', 'dashboard', 'refund']) }}
-- Monthly REFUND source-record summary. A COMPLETE annotation is not proof
-- that money was transferred; unresolved dates and amounts remain visible.
with parsed as (
    select
        r.*,
        coalesce(
            safe.parse_date('%d %b %Y', trim(refund_date_raw)),
            safe.parse_date('%d %B %Y', trim(refund_date_raw))
        ) as parsed_refund_date
    from {{ ref('refund_record_facts') }} r
)
select
    date_trunc(parsed_refund_date, month) as refund_month,
    count(*) as refund_source_rows,
    countif(sale_link_status = 'exact_sale_id') as linked_refund_rows,
    countif(sale_link_status = 'unmatched_source_id') as unmatched_refund_rows,
    countif(recorded_refund_status = 'recorded_complete') as recorded_complete_rows,
    countif(recorded_refund_status != 'recorded_complete') as status_review_rows,
    countif(refund_amount_needs_review) as amount_review_rows,
    countif(parsed_refund_date is null) as date_review_rows,
    sum(recorded_refund_amount_rm) as recorded_refund_amount_rm,
    'refund_source_record_denominator_not_cash_settlement_proof' as denominator_evidence
from parsed
group by refund_month
