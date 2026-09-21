{{ config(schema='gold', tags=['gold']) }}
-- One row per REFUND sheet entry. This does not prove money was returned.
-- Contact and bank fields are intentionally not projected.
with source_refunds as (
    select r.*,
        {{ rm_decimal('r.refund_amount_raw') }} as parsed_refund_amount_rm,
        case
            when regexp_contains(trim(r.refund_date_raw), r'^\d{1,2} [A-Za-z]+$')
                then 'day_month_no_year'
            when regexp_contains(upper(trim(r.refund_date_raw)), r'^RM\s*\d')
                then 'amount_like_in_date_cell'
            else 'unrecognized'
        end as refund_date_shape
    from {{ ref('refund') }} r
)
select
    r.refund_record_id,
    r.source_sheet_row,
    r.snapshot_table,
    s.sales_record_id,
    case when s.sales_record_id is not null then 'exact_sale_id'
         else 'unmatched_source_id' end as sale_link_status,
    r.refund_date_raw,
    r.refund_date_shape,
    r.refund_amount_raw,
    r.parsed_refund_amount_rm as recorded_refund_amount_rm,
    r.parsed_refund_amount_rm is null as refund_amount_needs_review,
    case when r.refund_status = 'COMPLETE' then 'recorded_complete'
         when r.refund_status = '' then 'not_recorded'
         else 'other_status_needs_review' end as recorded_refund_status
from source_refunds r
left join {{ ref('sales_package_facts') }} s
    on upper(trim(r.customer_id_raw)) = s.sales_record_id
