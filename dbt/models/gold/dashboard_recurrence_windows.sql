{{ config(schema='gold', tags=['gold', 'dashboard', 'recurrence']) }}
-- One row per matched 2026 Calendar service-like event. The previous event is
-- partitioned by SALES package and exact normalized address text. Map cells
-- are not property identifiers. Missing addresses stay isolated per event.
-- Planned package sessions are retained but are not labelled recurrence unless
-- the later event has a warranty signal. Generic extra visits need review.
with descriptions as (
    select calendar_event_row,
        regexp_replace(regexp_replace(coalesce(description, ''),
            r'(?i)</?(?:p|div|li|br)\b[^>]*>', '\n'), r'<[^>]+>', '') as description_text
    from {{ source('calendar_bronze', 'events') }}
), addresses as (
    select calendar_event_row,
        {{ calendar_address_line('description_text') }} as address_text
    from descriptions
), eligible as (
    select
        f.*,
        case when nullif(trim(a.address_text), '') is not null then
            to_hex(sha256(upper(regexp_replace(trim(a.address_text), r'\s+', ' '))))
        else concat('UNRESOLVED_EVENT_', cast(f.calendar_event_row as string))
        end as property_group_key,
        nullif(trim(a.address_text), '') is not null as property_text_available
    from {{ ref('calendar_service_event_facts') }} f
    left join addresses a using (calendar_event_row)
    where f.sales_record_id is not null
      and f.event_date_local <= current_date('Asia/Kuala_Lumpur')
), sequenced as (
    select
        e.*,
        lag(e.calendar_event_row) over (
            partition by e.sales_record_id, e.property_group_key
            order by e.event_date_local, e.event_start_ts, e.calendar_event_row
        ) as previous_calendar_event_row,
        lag(e.event_date_local) over (
            partition by e.sales_record_id, e.property_group_key
            order by e.event_date_local, e.event_start_ts, e.calendar_event_row
        ) as previous_service_date,
        lag(e.event_category) over (
            partition by e.sales_record_id, e.property_group_key
            order by e.event_date_local, e.event_start_ts, e.calendar_event_row
        ) as previous_event_category
    from eligible e
), labelled as (
    select
        s.*,
        date_diff(s.event_date_local, s.previous_service_date, day)
            as days_since_previous_event,
        s.previous_service_date is not null as has_previous_event,
        coalesce(s.warranty_claim_candidate, false) as recurrence_signal_candidate
    from sequenced s
)
select
    calendar_event_row,
    sales_record_id,
    property_group_key,
    property_text_available,
    location_precision_tier,
    event_date_local,
    event_category,
    session_current,
    session_total,
    warranty_claim_candidate,
    warranty_claim_reason,
    extra_visit_candidate,
    previous_calendar_event_row,
    previous_service_date,
    previous_event_category,
    days_since_previous_event,
    has_previous_event,
    recurrence_signal_candidate,
    case
        when not recurrence_signal_candidate then 'no_confirmed_return_signal'
        when not property_text_available then 'property_needs_review'
        when not has_previous_event then 'no_previous_event'
        when days_since_previous_event between 0 and 7 then '0_7_days'
        when days_since_previous_event between 8 and 14 then '8_14_days'
        when days_since_previous_event between 15 and 30 then '15_30_days'
        when days_since_previous_event between 31 and 60 then '31_60_days'
        when days_since_previous_event >= 61 then '61_plus_days'
        else 'invalid_interval_review'
    end as recurrence_bucket,
    case
        when not recurrence_signal_candidate then 'no_confirmed_return_signal'
        when warranty_claim_candidate then coalesce(warranty_claim_reason, 'warranty_signal')
        when event_category = 'complimentary' then 'complimentary_visit'
        when extra_visit_candidate then 'extra_visit_signal'
        else 'manual_review'
    end as recurrence_reason,
    'calendar_event_interval_not_completed_treatment_or_unique_customer_proof'
        as denominator_evidence
from labelled
where event_date_local between date '2026-01-01' and date '2026-12-31'
