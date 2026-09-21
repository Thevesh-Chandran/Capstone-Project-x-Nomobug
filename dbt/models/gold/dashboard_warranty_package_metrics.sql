{{ config(schema='gold', tags=['gold', 'dashboard']) }}
-- One row per matched SALES package with at least one confirmed Calendar
-- service-like entry. Customer IDs identify sales/packages, not people.
with package_events as (
    select
        sales_record_id,
        count(*) as scheduled_service_event_rows,
        countif(event_category = 'service') as normal_package_service_event_rows,
        countif(warranty_claim_candidate) as warranty_claim_event_rows,
        countif(event_category = 'complimentary' and not warranty_claim_candidate)
            as generic_complimentary_event_rows,
        countif(heatmap_eligible) as heatmap_eligible_event_rows,
        countif(warranty_claim_candidate and heatmap_eligible)
            as heatmap_eligible_warranty_claim_rows,
        countif(warranty_claim_candidate and complete_prior_14d_weather)
            as warranty_claims_with_complete_prior_14d_weather,
        min(event_date_local) as first_calendar_service_date,
        max(event_date_local) as last_calendar_service_date
    from {{ ref('calendar_service_event_facts') }}
    where sales_record_id is not null
      and event_date_local between date '2026-01-01' and date '2026-12-31'
    group by sales_record_id
)
select
    p.sales_record_id,
    s.closed_date,
    s.package_sessions_recorded,
    s.package_type_raw,
    s.contract_type_raw,
    s.sale_disposition,
    p.scheduled_service_event_rows,
    p.normal_package_service_event_rows,
    p.warranty_claim_event_rows,
    p.generic_complimentary_event_rows,
    p.heatmap_eligible_event_rows,
    p.heatmap_eligible_warranty_claim_rows,
    p.warranty_claims_with_complete_prior_14d_weather,
    p.first_calendar_service_date,
    p.last_calendar_service_date,
    p.warranty_claim_event_rows > 0 as has_warranty_claim_signal,
    safe_divide(p.warranty_claim_event_rows, p.scheduled_service_event_rows)
        as warranty_claim_event_share,
    safe_divide(
        p.heatmap_eligible_warranty_claim_rows,
        p.heatmap_eligible_event_rows
    ) as heatmap_warranty_claim_share,
    'matched_sales_package_denominator_not_unique_person_or_completed_treatment_count'
        as denominator_evidence
from package_events p
left join {{ ref('sales_package_facts') }} s using (sales_record_id)
