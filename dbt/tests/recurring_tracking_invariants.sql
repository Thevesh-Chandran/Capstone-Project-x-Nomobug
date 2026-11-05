{{ config(tags=['gold', 'recurring_tracking']) }}
-- Grain preservation and payment accounting checks, independently against facts.
select 'contract_rows_lost_or_multiplied' as issue
from unnest([1])
where (select count(*) from {{ ref('recurring_contract_payment_tracker') }})
    != (select count(*) from {{ ref('recurring_contract_candidates') }})
union all
select 'unconfirmed_reminders_enabled'
from unnest([1])
where exists (select 1 from {{ ref('recurring_contract_payment_tracker') }} where automatic_reminder_ready)
union all
select 'unconfirmed_instalment_amount_invented'
from unnest([1])
where exists (select 1 from {{ ref('recurring_payment_date_candidates') }} where agreed_instalment_amount_rm is not null)

union all
select 'invalid_active_reminder_schedule'
from unnest([1])
where exists (
    select 1 from {{ ref('recurring_contract_payment_tracker') }}
    where staff_reminder_schedule_ready and (
        sales_remaining_balance_rm is null or sales_remaining_balance_rm <= 0
        or lifecycle_review_required or sale_id_rows != 1
        or schedule_link_review_rows > 0 or invalid_reminder_date_rows > 0
        or next_scheduled_reminder_date is null
        or next_scheduled_reminder_date < tracker_as_of_date
        or recorded_balance_calculation_matches is not true
    )
)

union all
select 'reminder_workload_total_differs_from_eligible_source'
from unnest([1])
where (select coalesce(sum(scheduled_reminder_date_rows), 0)
    from {{ ref('dashboard_recurring_reminder_schedule') }}) != (
    select count(*) from {{ ref('recurring_payment_date_candidates') }} d
    join {{ ref('recurring_contract_payment_tracker') }} c using (sales_row_id)
    where c.staff_reminder_schedule_ready and d.source_link_unique
        and d.reminder_date >= c.tracker_as_of_date
)
