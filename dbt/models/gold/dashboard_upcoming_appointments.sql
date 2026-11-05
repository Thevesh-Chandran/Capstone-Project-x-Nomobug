{{ config(schema='gold', tags=['gold', 'dashboard', 'scheduling']) }}
-- Separate future-booking snapshot: this is never an outcome/model source.
{% set snapshot = var('upcoming_calendar_snapshot_table', var('calendar_snapshot_table', 'calendar_events_78147d417f3d97d3c1d9ef0be59638fd7850e4195108e1fc7b879483c7f35b66')) %}
with parsed as (
    select *, upper(coalesce(summary, '')) as title,
        date(safe_cast(start_raw as timestamp), 'Asia/Kuala_Lumpur') as service_date,
        safe_cast(regexp_extract(summary, r'\b(\d{1,2})\s*/\s*\d{1,2}\b') as int64) as current_visit,
        safe_cast(regexp_extract(summary, r'\b\d{1,2}\s*/\s*(\d{1,2})\b') as int64) as total_visits
    from `{{ target.project }}.bronze.{{ snapshot }}`
), classified as (
    select p.*,
        {{ calendar_event_category('title', 'status', 'current_visit', 'total_visits') }} as category,
        a.event_identity_hash is not null as reviewed_placeholder
    from parsed p
    left join {{ ref('calendar_appointment_overrides') }} a
      on a.event_identity_hash = lower(to_hex(sha256(concat(p.calendar_id, '|', p.event_id))))
     and safe_cast(p.start_raw as timestamp) = safe_cast(a.expected_start_at_utc as timestamp)
     and safe_cast(p.end_raw as timestamp) = safe_cast(a.expected_end_at_utc as timestamp)
     and a.appointment_state = 'awaiting_client_date'
)
select service_date, calendar_name,
    count(*) as scheduled_event_rows,
    timestamp('{{ var("upcoming_calendar_extracted_at", "2026-09-01T00:00:00+00:00") }}') as extracted_at,
    'confirmed_calendar_bookings_not_completed_treatments_or_available_slots' as denominator_evidence
from classified
where status = 'confirmed' and not reviewed_placeholder
  and category in ('service', 'warranty', 'complimentary')
  and not regexp_contains(title, r'\b(?:HOLD|AWAITING\s+(?:CLIENT\s+)?DATE|PLACEHOLDER)\b')
  and service_date between current_date('Asia/Kuala_Lumpur')
      and date_add(current_date('Asia/Kuala_Lumpur'), interval 29 day)
group by service_date, calendar_name
