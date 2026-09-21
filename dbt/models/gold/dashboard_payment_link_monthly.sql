{{ config(schema='gold', tags=['gold', 'dashboard', 'funnel']) }}
-- Descriptive PAYMENT LINK source-record summary. A recorded WON annotation is
-- a source outcome. The unused status field belongs to PAYMENTS. PAYMENT LINK
-- WON remains meaningful; conversion requires reconciled sales and denominators.
with parsed as (
    select
        p.*,
        coalesce(
            safe.parse_date('%d-%b-%Y', trim(payment_link_date_raw)),
            safe.parse_date('%d %b %Y', trim(payment_link_date_raw)),
            safe.parse_date('%Y-%m-%d', trim(payment_link_date_raw))
        ) as parsed_link_date
    from {{ ref('payment_link') }} p
)
select
    date_trunc(parsed_link_date, month) as payment_link_month,
    count(*) as payment_link_source_rows,
    countif(payment_link_success_flag) as recorded_won_rows,
    countif(payment_link_status is null) as missing_status_rows,
    countif(parsed_link_date is null) as date_review_rows,
    countif(nullif(trim(outcome_raw), '') is not null) as outcome_text_rows,
    'payment_link_source_record_denominator_not_unique_customer_or_conversion_proof'
        as denominator_evidence
from parsed
group by payment_link_month
