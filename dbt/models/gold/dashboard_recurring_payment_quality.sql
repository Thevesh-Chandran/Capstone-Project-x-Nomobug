{{ config(schema='gold', tags=['gold', 'dashboard', 'looker', 'recurring_tracking']) }}
-- Aggregates only. No names, sale IDs, contacts, or individual reminder/payment dates.
select
    billing_arrangement,
    tracker_as_of_date,
    count(*) as candidate_contract_rows,
    countif(explicit_recurring_arrangement) as explicitly_labelled_contract_rows,
    countif(custom_payment_note) as custom_payment_note_rows,
    countif(sales_remaining_balance_rm > 0) as positive_recorded_balance_rows,
    countif(sales_remaining_balance_rm <= 0) as nonpositive_recorded_balance_rows,
    countif(sales_remaining_balance_rm is null) as balance_review_rows,
    sum(sale_total_rm) as recorded_contract_value_rm,
    sum(if(sales_remaining_balance_rm > 0, sales_remaining_balance_rm, 0))
        as positive_recorded_remaining_balance_rm,
    countif(sale_total_rm is null) as contract_value_review_rows,
    countif(staff_reminder_schedule_ready) as contracts_with_future_reminder_schedule,
    sum(sales_deposit_recorded_rm) as sales_recorded_deposits_rm,
    sum(sales_balance_paid_recorded_rm) as sales_recorded_balance_paid_rm,
    sum(sales_total_recorded_paid_rm) as sales_total_recorded_paid_rm,
    countif(sales_total_recorded_paid_rm is null) as recorded_paid_amount_review_rows,
    countif(candidate_schedule_cells = 0) as contracts_without_source_schedule,
    countif(lifecycle_review_required) as lifecycle_review_rows,
    countif(specific_payment_terms_note) as specific_terms_note_rows,
    countif(recorded_balance_calculation_matches) as balance_calculation_match_rows,
    countif(recorded_balance_calculation_matches is not true) as balance_calculation_review_rows,
    countif(staff_reminder_schedule_ready and next_scheduled_reminder_date between tracker_as_of_date
        and date_add(tracker_as_of_date, interval 7 day))
        as contracts_with_scheduled_reminders_next_7_days,
    countif(invalid_reminder_date_rows > 0 or schedule_link_review_rows > 0) as reminder_schedule_review_rows,
    'SOURCE_REMINDER_SCHEDULE; ELAPSED_DATES_NOT_OVERDUE_OR_DELIVERY_EVIDENCE'
        as interpretation
from {{ ref('recurring_contract_payment_tracker') }}
group by billing_arrangement, tracker_as_of_date
