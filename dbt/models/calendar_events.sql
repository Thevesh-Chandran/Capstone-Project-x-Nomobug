{{ config(tags=['calendar']) }}
with raw_events as (
    select *,
        upper(coalesce(summary, '')) as summary_upper,
        safe_cast(regexp_extract(summary, r'\b(\d{1,2})\s*/\s*\d{1,2}\b') as int64) as session_current,
        safe_cast(regexp_extract(summary, r'\b\d{1,2}\s*/\s*(\d{1,2})\b') as int64) as session_total
    from {{ source('calendar_bronze', 'events') }}
), classified as (
    select *,
        case
            when upper(status) = 'CANCELLED' then 'cancelled'
            -- Administrative reminders can mention warranty terms without
            -- representing a customer visit. Keep them out of service,
            -- geospatial, weather, and ML grains while retaining the raw row.
            when regexp_contains(
                summary_upper,
                r'\b(?:CHECK|REVIEW|CALCULATE)\b.*\bCONVERSION\s+RATE\b'
            ) then 'administrative'
            -- A sequence beyond the purchased package (for example 4/3 or
            -- 5/3) is how the team records a warranty/claim visit within the
            -- package's warranty window. Keep this ahead of the generic
            -- complimentary/extra wording so it is counted as a warranty
            -- claim even when the title says "complimentary".
            when session_current > session_total then 'warranty'
            when regexp_contains(summary_upper, r'WARRANTY|CLAIM|CALLBACK') then 'warranty'
            when regexp_contains(summary_upper, r'EXTRA|COMPLIMENTARY|FOLLOW[- ]?UP') then 'complimentary'
            when regexp_contains(summary_upper, r'CONSULTATION|INSPECTION') then 'consultation'
            when regexp_contains(summary_upper, r'\b\d{1,2}\s*/\s*\d{1,2}\b') then 'service'
            else 'other'
        end as event_category
    from raw_events
)
select
    calendar_event_row,
    calendar_name,
    calendar_id,
    event_id,
    ical_uid,
    status,
    event_type,
    start_raw,
    end_raw,
    safe_cast(start_raw as timestamp) as event_start_ts,
    safe_cast(end_raw as timestamp) as event_end_ts,
    date(safe_cast(start_raw as timestamp), 'Asia/Kuala_Lumpur') as event_date_local,
    is_all_day,
    created_raw,
    updated_raw,
    recurring_event_id,
    case
        when regexp_contains(summary_upper, r'TERMITE|ANAI[- ]?ANAI') then 'TERMITE'
        when regexp_contains(summary_upper, r'COCKROACH|LIPAS') then 'COCKROACH'
        when regexp_contains(summary_upper, r'BED\s*BUG|PEPIJAT') then 'BED_BUG'
        when regexp_contains(summary_upper, r'MOSQUITO|NYAMUK') then 'MOSQUITO'
        when regexp_contains(summary_upper, r'RAT|RODENT|TIKUS') then 'RODENT'
        when regexp_contains(summary_upper, r'ANT|SEMUT') then 'ANT'
        when regexp_contains(summary_upper, r'FLY|FLIES|LALAT') then 'FLY'
        else 'UNSPECIFIED'
    end as calendar_pest_text_category,
    case
        when regexp_contains(summary_upper, r'FOG|MIST') then 'FOGGING_OR_MISTING'
        when regexp_contains(summary_upper, r'GEL|BAIT') then 'GEL_OR_BAIT'
        when regexp_contains(summary_upper, r'SPRAY') then 'SPRAY'
        when regexp_contains(summary_upper, r'INSPECTION|CONSULTATION') then 'INSPECTION'
        else 'UNSPECIFIED'
    end as calendar_service_method_category,
    session_current,
    session_total,
    session_current > session_total as sequence_over_package,
    event_category,
    status = 'confirmed' and (
        coalesce(session_current > session_total, false)
        or coalesce(regexp_contains(summary_upper, r'WARRANTY|CLAIM|CALLBACK'), false)
    ) as warranty_claim_candidate,
    case
        when status = 'confirmed' and session_current > session_total then 'post_package_sequence'
        when status = 'confirmed' and regexp_contains(summary_upper, r'WARRANTY|CLAIM|CALLBACK') then 'explicit_warranty_label'
        else null
    end as warranty_claim_reason,
    status = 'confirmed' and event_category in ('service', 'warranty', 'extra_visit_candidate', 'complimentary') as service_candidate,
    status = 'confirmed' and (
        event_category in ('warranty', 'extra_visit_candidate', 'complimentary')
        or regexp_contains(summary_upper, r'EXTRA|COMPLIMENTARY|WARRANTY|CLAIM|CALLBACK')
    ) as extra_visit_candidate
from classified
