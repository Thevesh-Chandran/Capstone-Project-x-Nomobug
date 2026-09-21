{{ config(schema='gold', tags=['gold', 'spatial']) }}
-- Geohash precision 5 is an area aggregation (roughly several kilometres in
-- Malaysia), not a claimed pest radius. Counts are scheduled/recorded entries.
with eligible as (
    select
        st_geohash(service_geography, 5) as area_cell,
        calendar_event_row,
        sales_record_id,
        service_geography,
        extra_visit_candidate,
        sequence_over_package,
        warranty_claim_candidate,
        event_category
    from {{ ref('calendar_service_event_facts') }}
    where heatmap_eligible
      and event_date_local between date '2026-01-01' and date '2026-12-31'
), metrics as (
    select
        area_cell,
        st_centroid(st_union_agg(service_geography)) as observed_event_centroid,
        count(*) as scheduled_service_event_rows,
        count(distinct sales_record_id) as matched_sales_records,
        countif(warranty_claim_candidate) as repeat_signal_event_rows,
        countif(event_category = 'warranty') as warranty_label_event_rows,
        countif(sequence_over_package) as over_sequence_event_rows
    from eligible
    group by area_cell
)
select *,
    safe_divide(repeat_signal_event_rows, scheduled_service_event_rows) as repeat_signal_share,
    scheduled_service_event_rows >= 5 as sufficient_volume_for_comparison,
    'scheduled_event_denominator_not_completed_treatment_count' as denominator_evidence
from metrics
