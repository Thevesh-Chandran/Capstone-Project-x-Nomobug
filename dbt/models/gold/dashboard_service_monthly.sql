{{ config(schema='gold', tags=['gold', 'dashboard']) }}
-- Dashboard-facing monthly service activity. Counts are scheduled/recorded
-- Calendar entries, not proof of completed treatments or unique customers.
-- Warranty claims include explicit Warranty/Claim/Callback labels and
-- post-package sequences such as 4/3 and 5/3.
select
    date_trunc(event_date_local, month) as service_month,
    count(*) as scheduled_service_event_rows,
    countif(event_category = 'service') as normal_package_service_event_rows,
    countif(warranty_claim_candidate) as warranty_claim_event_rows,
    countif(event_category = 'complimentary' and not warranty_claim_candidate)
        as generic_complimentary_event_rows,
    countif(sales_record_id is not null) as matched_sales_event_rows,
    countif(sales_record_id is null) as unmatched_sales_event_rows,
    countif(heatmap_eligible) as heatmap_eligible_event_rows,
    countif(warranty_claim_candidate and heatmap_eligible)
        as heatmap_eligible_warranty_claim_rows,
    countif(warranty_claim_candidate and complete_prior_14d_weather)
        as warranty_claims_with_complete_prior_14d_weather,
    safe_divide(
        countif(warranty_claim_candidate),
        count(*)
    ) as warranty_claim_event_share,
    safe_divide(
        countif(warranty_claim_candidate and heatmap_eligible),
        countif(heatmap_eligible)
    ) as heatmap_warranty_claim_share,
    'scheduled_calendar_event_denominator_not_unique_customer_or_completed_treatment_count'
        as denominator_evidence
from {{ ref('calendar_service_event_facts') }}
where event_date_local between date '2026-01-01' and date '2026-12-31'
group by service_month
