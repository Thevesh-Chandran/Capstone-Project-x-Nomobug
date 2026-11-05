{{ config(tags=['calendar', 'gold']) }}
-- Registry uniqueness prevents source row expansion. Expired reviews are retained
-- for audit; they must not classify the moved appointment as a placeholder.
select 'duplicate_appointment_review' as failure
from {{ ref('calendar_appointment_overrides') }}
group by event_identity_hash
having count(*) != 1
union all
select 'invalid_appointment_review'
from {{ ref('calendar_appointment_overrides') }}
where not regexp_contains(event_identity_hash, r'^[a-f0-9]{64}$')
   or appointment_state != 'awaiting_client_date'
   or reason_code != 'owner_confirmed_temporary_slot'
   or safe_cast(expected_start_at_utc as timestamp) is null
   or safe_cast(expected_end_at_utc as timestamp) is null
   or safe_cast(expected_start_at_utc as timestamp) > safe_cast(expected_end_at_utc as timestamp)
union all
select 'unreviewed_or_moved_event_marked_placeholder'
from {{ ref('calendar_events') }} e
where e.event_category = 'placeholder' and not exists (
    select 1 from {{ ref('calendar_appointment_overrides') }} a
    where a.event_identity_hash = lower(to_hex(sha256(concat(e.calendar_id, '|', e.event_id))))
      and e.event_start_ts = safe_cast(a.expected_start_at_utc as timestamp)
      and e.event_end_ts = safe_cast(a.expected_end_at_utc as timestamp)
)
union all
select 'placeholder_counted_as_service_or_claim'
from {{ ref('calendar_events') }}
where event_category = 'placeholder' and (service_candidate or warranty_claim_candidate)
