{{ config(schema='gold', tags=['gold', 'dashboard', 'difficulty']) }}
-- Separate planning indicators. Warranty is excluded from the additional-visit
-- component. Refund evidence is package-level and cannot establish which visit
-- or team caused a refund. Composite weighting has not been validated.
with event_rows as (
    select
        f.*,
        coalesce(st_geohash(f.service_geography, 5), 'NO_LOCATION') as area_cell,
        s.pest_type_raw,
        s.package_type_raw,
        coalesce(r.linked_refund_signal, false) as linked_refund_signal
    from {{ ref('calendar_service_event_facts') }} f
    left join {{ ref('sales_package_facts') }} s using (sales_record_id)
    left join (
        select sales_record_id, true as linked_refund_signal
        from {{ ref('refund_record_facts') }}
        where sales_record_id is not null
        group by sales_record_id
    ) r using (sales_record_id)
    where f.event_date_local between date '2026-01-01' and date '2026-12-31'
), grouped as (
    select
        area_cell,
        calendar_name,
        nullif(trim(pest_type_raw), '') as pest_type,
        nullif(trim(package_type_raw), '') as package_type,
        count(*) as scheduled_event_rows,
        countif(warranty_claim_candidate) as warranty_claim_event_rows,
        countif(extra_visit_candidate and not warranty_claim_candidate) as extra_visit_signal_rows,
        countif(linked_refund_signal) as linked_refund_event_rows,
        count(distinct if(sales_record_id is not null, sales_record_id, null))
            as matched_sales_records
    from event_rows
    group by area_cell, calendar_name, pest_type, package_type
)
select
    area_cell,
    calendar_name,
    pest_type,
    package_type,
    scheduled_event_rows,
    matched_sales_records,
    warranty_claim_event_rows,
    extra_visit_signal_rows,
    linked_refund_event_rows,
    safe_divide(warranty_claim_event_rows, scheduled_event_rows)
        as warranty_signal_share,
    safe_divide(extra_visit_signal_rows, scheduled_event_rows)
        as extra_visit_signal_share,
    safe_divide(linked_refund_event_rows, scheduled_event_rows)
        as linked_refund_signal_share,
    cast(null as float64) as treatment_difficulty_proxy_0_100,
    scheduled_event_rows >= 5 as sufficient_volume_for_comparison,
    'separate_components_composite_pending_validation' as score_evidence
from grouped
