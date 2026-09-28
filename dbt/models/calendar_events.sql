{{ config(tags=['calendar']) }}
with raw_events as (
    select *,
        upper(coalesce(summary, '')) as summary_upper,
        safe_cast(regexp_extract(summary, r'\b(\d{1,2})\s*/\s*\d{1,2}\b') as int64) as session_current,
        safe_cast(regexp_extract(summary, r'\b\d{1,2}\s*/\s*(\d{1,2})\b') as int64) as session_total
    from {{ source('calendar_bronze', 'events') }}
), classified as (
    select *,
        {{ calendar_event_category('summary_upper', 'status', 'session_current', 'session_total') }}
            as rule_event_category,
        {{ calendar_event_category('summary_upper', 'status', 'session_current', 'session_total', false) }}
            as non_claim_event_category
    from raw_events
), reviewed as (
    select c.*,
        r.review_id as warranty_label_review_id,
        r.review_label as warranty_label_review_status,
        r.reviewed_at as warranty_label_reviewed_at,
        case
            -- Cancellation/admin rules still control operational eligibility.
            when c.rule_event_category in ('cancelled', 'administrative') then c.rule_event_category
            when r.review_label = 'Confirmed warranty claim' then 'warranty'
            when r.review_label = 'Not a warranty claim' then c.non_claim_event_category
            when r.review_label = 'Unclear' then 'label_unresolved'
            else c.rule_event_category
        end as event_category
    from classified c
    left join {{ ref('calendar_warranty_review_overrides') }} r
      on r.event_identity_hash = to_hex(sha256(concat(c.calendar_id, '|', c.event_id)))
     and r.event_id = c.event_id
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
    warranty_label_review_id,
    coalesce(warranty_label_review_status, 'Not reviewed') as warranty_label_review_status,
    warranty_label_reviewed_at,
    coalesce(warranty_label_review_status = 'Unclear', false) as warranty_label_uncertain,
    if(warranty_label_review_id is null, 'calendar_title_rule', 'manual_review_2026_09_27')
        as warranty_label_provenance,
    -- Unresolved reviews deliberately produce NULL, never a negative label.
    case
        when warranty_label_review_status = 'Unclear' then cast(null as bool)
        else status = 'confirmed' and event_category = 'warranty'
    end as warranty_claim_candidate,
    case
        when status = 'confirmed' and event_category = 'warranty'
             and warranty_label_review_status = 'Confirmed warranty claim' then 'manual_review_confirmed_claim'
        when status = 'confirmed' and event_category = 'warranty'
             and session_current > session_total then 'post_package_sequence'
        when status = 'confirmed' and event_category = 'warranty' then 'explicit_warranty_label'
        else null
    end as warranty_claim_reason,
    status = 'confirmed' and event_category in ('service', 'warranty', 'extra_visit_candidate', 'complimentary') as service_candidate,
    status = 'confirmed'
        and event_category in ('warranty', 'extra_visit_candidate', 'complimentary')
        as extra_visit_candidate
from reviewed
