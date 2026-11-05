{{ config(schema='gold', tags=['gold', 'dashboard', 'looker', 'decision_support']) }}
-- Aggregate management action list. No contacts, customer IDs or individual risk.
-- Rows have different units/populations; never total this table's count or amount.
with freshness as (
    select source_name, extracted_at_utc from {{ ref('dashboard_source_freshness') }}
), reminder_freshness as (
    select if(count(*) = 2 and count(extracted_at_utc) = 2, min(extracted_at_utc), null) as extracted_at_utc
    from freshness where source_name in ('sales', 'recurring_payments')
), items as (
    select 'Payment reminders' as category, r.reminder_date as action_date,
        r.billing_arrangement as context,
        cast(r.scheduled_reminder_date_rows as int64) as item_count,
        cast(null as numeric) as amount_rm, 'scheduled reminder entries' as unit,
        'Check the private contract register and current SALES balance before sending the scheduled reminder.' as next_action,
        'Reminder date is not proof of an unpaid instalment or a message sent.' as meaning,
        'dashboard_recurring_reminder_schedule' as source_view,
        f.extracted_at_utc as source_updated_at
    from {{ ref('dashboard_recurring_reminder_schedule') }} r cross join reminder_freshness f
    where r.reminder_date >= current_date('Asia/Kuala_Lumpur')
      and r.reminder_date < date_add(current_date('Asia/Kuala_Lumpur'), interval 7 day)
    union all
    select 'Upcoming visits', s.service_date, s.calendar_name,
        s.scheduled_event_rows, cast(null as numeric), 'scheduled Calendar visits',
        'Review the Calendar for booking changes and confirm the planned allocation.',
        'Bookings are not treatment completion or confirmed technician capacity.',
        'dashboard_upcoming_appointments', s.extracted_at
    from {{ ref('dashboard_upcoming_appointments') }} s
    where s.service_date >= current_date('Asia/Kuala_Lumpur')
      and s.service_date < date_add(current_date('Asia/Kuala_Lumpur'), interval 7 day)
    union all
    select 'Recorded contract balances', current_date('Asia/Kuala_Lumpur'), r.billing_arrangement,
        r.positive_recorded_balance_rows, r.positive_recorded_remaining_balance_rm,
        'contracts with a positive recorded balance',
        'Review SALES deposit and balance-paid entries alongside the contract reminder schedule.',
        'Remaining contract balances are not overdue amounts; PAYMENTS is excluded.',
        'dashboard_recurring_payment_quality', f.extracted_at_utc
    from {{ ref('dashboard_recurring_payment_quality') }} r
    left join freshness f on f.source_name = 'sales'
    where r.positive_recorded_balance_rows > 0
    union all
    select 'Missing reminder schedule', current_date('Asia/Kuala_Lumpur'), r.billing_arrangement,
        r.contracts_without_source_schedule, cast(null as numeric), 'contracts without reminder dates',
        'Check the actual contract terms and add verified reminder dates in the source sheet.',
        'No reminder dates are inferred from a monthly or quarterly label.',
        'dashboard_recurring_payment_quality', f.extracted_at_utc
    from {{ ref('dashboard_recurring_payment_quality') }} r cross join reminder_freshness f
    where r.contracts_without_source_schedule > 0
    union all
    select 'Source records to review', current_date('Asia/Kuala_Lumpur'),
        concat(q.source_name, ': ', replace(q.issue_code, '_', ' ')),
        q.affected_rows, cast(null as numeric), 'source rows carrying this flag',
        'Inspect the flagged source records; retain legitimate combined entries and documented exceptions.',
        'Flags may overlap and are review prompts, not a count of unique errors.',
        'dashboard_data_quality', f.extracted_at_utc
    from {{ ref('dashboard_data_quality') }} q
    left join freshness f on f.source_name = if(q.source_name = 'prospects_2026', 'prospects', q.source_name)
    where q.affected_rows > 0
)
select *, current_date('Asia/Kuala_Lumpur') as as_of_date,
    case when source_updated_at is null then 'Freshness unknown - verify source'
         when timestamp_diff(current_timestamp(), source_updated_at, hour) > 36
            then 'Source older than 36 hours - verify'
         else 'Source within 36 hours' end as freshness_status,
    'Counts and amounts have different grains; do not sum across categories.' as aggregation_note
from items
