{{ config(schema='gold', tags=['gold']) }}
-- One formal WARRANTY CLAIM sheet row, not a Calendar treatment count.
-- Calendar visit dates remain authoritative for scheduled/recorded services.
with source_claims as (
    select w.*,
        coalesce(
            safe.parse_date('%d %b %Y', trim(w.claim_date_raw)),
            safe.parse_date('%d %B %Y', trim(w.claim_date_raw))
        ) as recorded_claim_date
    from {{ ref('warranty_claim') }} w
)
select
    w.warranty_claim_record_id,
    w.source_sheet_row,
    w.snapshot_table,
    s.sales_record_id,
    case when s.sales_record_id is not null then 'exact_sale_id'
         else 'unmatched_source_id' end as sale_link_status,
    w.claim_date_raw,
    w.recorded_claim_date,
    w.recorded_claim_date is null as claim_date_needs_review,
    case
        when upper(trim(w.refund_date_raw)) = 'YES' then 'recorded_yes'
        when upper(trim(w.refund_date_raw)) = 'NO' then 'recorded_no'
        when coalesce(
            safe.parse_date('%d %b %Y', trim(w.refund_date_raw)),
            safe.parse_date('%d %B %Y', trim(w.refund_date_raw))
        ) is not null then 'date_text_recorded'
        else 'other_needs_review'
    end as source_refund_indicator
from source_claims w
left join {{ ref('sales_package_facts') }} s
    on upper(trim(w.customer_id_raw)) = s.sales_record_id
