{{ config(schema='gold', tags=['gold']) }}
-- Scheduled/recorded dates, never proof of treatment attendance. A delayed 3x
-- schedule is still eligible; there is no fourteen-day completion requirement.
with visits as (
    select programme_id,
        countif(event_category = 'service') as recorded_paid_visit_rows,
        min(if(event_category = 'service', event_date_local, null)) as first_paid_service_date,
        max(if(event_category = 'service', event_date_local, null)) as last_paid_service_date,
        count(distinct if(owner_confirmed_paid_stage, paid_programme_stage, null)) as reviewed_paid_stages
    from {{ ref('calendar_programme_service_facts') }}
    group by programme_id
)
select p.*, v.* except(programme_id),
    case when not p.warranty_policy_eligible then null
         when p.effective_paid_sessions = 3 and v.recorded_paid_visit_rows = 3
            then v.last_paid_service_date
         when p.effective_paid_sessions in (4,6,12) then v.first_paid_service_date
    end as recorded_warranty_start_date,
    case when p.warranty_policy_eligible
              and v.recorded_paid_visit_rows = p.effective_paid_sessions
         then date_add(v.last_paid_service_date, interval 30 day)
    end as recorded_warranty_end_date,
    'scheduled_recorded_dates_not_proof_of_completed_treatment' as completion_evidence
from {{ ref('service_programme_facts') }} p left join visits v using(programme_id)
