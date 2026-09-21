{{ config(tags=['calendar', 'matching']) }}
-- One row per formal claim and linked Calendar service candidate.
-- Sheet dates remain raw claim details; event_date_local is the operational visit date.
select
    w.warranty_claim_record_id,
    upper(trim(w.customer_id_raw)) as sales_record_id,
    m.calendar_event_row,
    m.calendar_name,
    m.event_id,
    m.event_date_local as calendar_visit_date,
    m.start_raw as calendar_start_raw,
    e.session_current,
    e.session_total,
    e.event_category,
    e.extra_visit_candidate,
    m.match_status,
    w.claim_date_raw,
    w.complimentary_service_date_raw,
    w.warranty_claim_service_date_raw
from {{ ref('warranty_claim') }} w
join {{ ref('calendar_event_matches') }} m
  on m.matched_sales_record_id = upper(trim(w.customer_id_raw))
join {{ ref('calendar_events') }} e
  using (calendar_event_row)
where m.service_candidate
