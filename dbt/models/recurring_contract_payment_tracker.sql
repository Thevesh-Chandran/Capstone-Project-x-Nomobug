{{ config(tags=['gold', 'recurring_tracking']) }}
-- Restricted one-row-per-SALES-contract tracker, including recorded-paid history.
with dates as (
    select sales_row_id,
        count(*) as candidate_schedule_cells,
        countif(reminder_date is not null) as parseable_candidate_dates,
        min(if(reminder_date >= current_date('Asia/Kuala_Lumpur'),
            reminder_date, null)) as next_scheduled_reminder_date,
        countif(reminder_date < current_date('Asia/Kuala_Lumpur'))
            as elapsed_reminder_date_rows,
        max(if(reminder_date < current_date('Asia/Kuala_Lumpur'), reminder_date, null)) as last_elapsed_reminder_date,
        countif(reminder_date is null) as invalid_reminder_date_rows,
        countif(not source_link_unique) as schedule_link_review_rows
    from {{ ref('recurring_payment_date_candidates') }} group by sales_row_id
)
select c.*,
    c.sales_deposit_recorded_rm + c.sales_balance_paid_recorded_rm
        as sales_total_recorded_paid_rm,
    abs(c.sale_total_rm - c.sales_deposit_recorded_rm
        - c.sales_balance_paid_recorded_rm - c.sales_remaining_balance_rm) <= 0.01
        as recorded_balance_calculation_matches,
    'SALES_RECORDED_AMOUNTS; PAYMENT_DATES_NOT_AVAILABLE' as payment_evidence,
    coalesce(d.candidate_schedule_cells, 0) as candidate_schedule_cells,
    coalesce(d.parseable_candidate_dates, 0) as parseable_candidate_dates,
    if(c.sales_remaining_balance_rm > 0, d.next_scheduled_reminder_date, null) as next_scheduled_reminder_date,
    d.last_elapsed_reminder_date,
    coalesce(d.invalid_reminder_date_rows, 0) as invalid_reminder_date_rows,
    c.sales_remaining_balance_rm > 0 and c.sale_id_rows = 1
        and not c.lifecycle_review_required
        and coalesce(d.schedule_link_review_rows, 0) = 0
        and coalesce(d.invalid_reminder_date_rows, 0) = 0
        and d.next_scheduled_reminder_date is not null
        and abs(c.sale_total_rm - c.sales_deposit_recorded_rm
            - c.sales_balance_paid_recorded_rm - c.sales_remaining_balance_rm) <= 0.01
        as staff_reminder_schedule_ready,
    coalesce(d.elapsed_reminder_date_rows, 0) as elapsed_reminder_date_rows,
    coalesce(d.schedule_link_review_rows, 0) as schedule_link_review_rows,
    current_date('Asia/Kuala_Lumpur') as tracker_as_of_date,
    false as automatic_reminder_ready,
    'USE_SOURCE_REMINDER_DATES_AND_SALES_CUMULATIVE_PAID; DELIVERY_STATUS_UNKNOWN'
        as next_action
from {{ ref('recurring_contract_candidates') }} c
left join dates d using (sales_row_id)
