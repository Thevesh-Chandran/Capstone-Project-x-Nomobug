{{ config(schema='gold', tags=['gold'], materialized='table') }}
-- Match reviewed visits by Calendar identity, including a verified transfer
-- that keeps the same non-recurring iCalUID. Require one eligible match.
with eligible as (
    select e.calendar_event_row, f.sales_record_id,
        f.session_current, f.session_total,
        lower(to_hex(sha256(concat(e.calendar_id, '|', e.event_id)))) as event_identity_hash,
        if(e.recurring_event_id is null and nullif(e.ical_uid, '') is not null,
           lower(to_hex(sha256(e.ical_uid))), null) as ical_uid_hash
    from {{ ref('calendar_service_event_facts') }} f
    join {{ ref('calendar_events') }} e using (calendar_event_row)
    where f.warranty_claim_candidate is false
      and f.event_date_local is not null
), matches as (
    select o.event_identity_hash, count(*) as candidate_count,
        min(e.calendar_event_row) as candidate_event_row
    from {{ ref('paid_programme_visit_overrides') }} o
    join eligible e on (e.event_identity_hash = o.event_identity_hash
                        or e.ical_uid_hash = o.ical_uid_hash)
        and e.sales_record_id = o.expected_matched_sales_record_id
        and e.session_current = o.expected_session_current
        and e.session_total = o.expected_session_total
    group by o.event_identity_hash
)
select o.*, coalesce(m.candidate_count, 0) as candidate_count,
    if(m.candidate_count = 1, m.candidate_event_row, null) as calendar_event_row
from {{ ref('paid_programme_visit_overrides') }} o
left join matches m using (event_identity_hash)
