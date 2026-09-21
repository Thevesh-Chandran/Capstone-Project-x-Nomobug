{{ config(schema='gold', tags=['gold', 'dashboard', 'package_fit']) }}
-- Descriptive package-fit evidence, not a predictive upsell model. Payment
-- evidence means at least one linked PAYMENTS entry; amounts are not allocated
-- across combined payment references.
with payment_evidence as (
    select
        sales_record_id,
        count(distinct payment_record_id) as linked_payment_entry_rows
    from {{ ref('payment_sales_links') }}
    where sales_match_status = 'matched'
    group by sales_record_id
), event_summary as (
    select
        sales_record_id,
        count(*) as scheduled_event_rows,
        countif(warranty_claim_candidate) as warranty_claim_event_rows,
        countif(event_category = 'complimentary' and not warranty_claim_candidate)
            as generic_complimentary_event_rows
    from {{ ref('calendar_service_event_facts') }}
    where sales_record_id is not null
      and event_date_local between date '2026-01-01' and date '2026-12-31'
    group by sales_record_id
), packages as (
    select
        s.*,
        coalesce(p.linked_payment_entry_rows, 0) as linked_payment_entry_rows,
        coalesce(e.scheduled_event_rows, 0) as scheduled_event_rows,
        coalesce(e.warranty_claim_event_rows, 0) as warranty_claim_event_rows,
        coalesce(e.generic_complimentary_event_rows, 0)
            as generic_complimentary_event_rows
    from {{ ref('sales_package_facts') }} s
    left join payment_evidence p using (sales_record_id)
    left join event_summary e using (sales_record_id)
    where include_in_sale_count
      and closed_date between date '2026-01-01' and date '2026-12-31'
)
select
    nullif(trim(pest_type_raw), '') as pest_type,
    nullif(trim(package_type_raw), '') as package_type,
    nullif(trim(contract_type_raw), '') as contract_type,
    count(*) as package_rows,
    countif(linked_payment_entry_rows > 0) as packages_with_payment_evidence,
    sum(sale_total_rm) as recorded_package_face_value_rm,
    sum(linked_payment_entry_rows) as linked_payment_entry_rows,
    sum(scheduled_event_rows) as scheduled_event_rows,
    sum(warranty_claim_event_rows) as warranty_claim_event_rows,
    sum(generic_complimentary_event_rows) as generic_complimentary_event_rows,
    safe_divide(countif(linked_payment_entry_rows > 0), count(*))
        as payment_evidence_rate,
    safe_divide(sum(warranty_claim_event_rows), sum(scheduled_event_rows))
        as warranty_event_share,
    'descriptive_package_fit_not_rejected_offer_prediction_or_cash_allocation' as denominator_evidence
from packages
group by pest_type, package_type, contract_type
