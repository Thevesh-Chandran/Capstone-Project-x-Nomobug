{{ config(schema='gold', tags=['gold', 'dashboard', 'looker', 'recurring_tracking']) }}
-- Aggregate operational reminder workload, not payment due dates or sent messages.
select d.reminder_date, c.billing_arrangement, c.tracker_as_of_date,
    count(*) as scheduled_reminder_date_rows,
    count(distinct c.sales_row_id) as scheduled_contract_rows
from {{ ref('recurring_payment_date_candidates') }} d
join {{ ref('recurring_contract_payment_tracker') }} c using (sales_row_id)
where c.staff_reminder_schedule_ready
    and d.source_link_unique
    and d.reminder_date >= c.tracker_as_of_date
group by d.reminder_date, c.billing_arrangement, c.tracker_as_of_date
