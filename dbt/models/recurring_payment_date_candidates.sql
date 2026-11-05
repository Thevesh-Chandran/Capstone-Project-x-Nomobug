{{ config(tags=['gold', 'recurring_tracking']) }}
-- Owner-defined staff reminder dates. Elapsed/green dates are not payment or delivery evidence.
with schedule_rows as (
    select r.*,
        {{ sales_reference_array('customer_id_raw') }} as sale_ids,
        count(*) over (partition by upper(trim(customer_id_raw))) as reference_rows
    from {{ ref('recurring_payments') }} r
), schedule_cells as (
    select r.recurring_payment_record_id,
        r.sale_ids[safe_offset(0)] as sales_record_id,
        r.reference_rows,
        cell.instalment_number, cell.date_raw,
        safe.parse_date('%d-%b-%Y', trim(cell.date_raw)) as reminder_date
    from schedule_rows r,
    unnest([
        struct(2 as instalment_number, source_column_023 as date_raw),
        struct(3, source_column_024), struct(4, source_column_025),
        struct(5, source_column_026), struct(6, source_column_027),
        struct(7, source_column_028), struct(8, source_column_029),
        struct(9, source_column_030), struct(10, source_column_031),
        struct(11, source_column_032), struct(12, source_column_033)
    ]) cell
    where array_length(r.sale_ids) = 1 and nullif(trim(cell.date_raw), '') is not null
)
select
    c.sales_row_id, c.sales_record_id, c.billing_arrangement,
    s.recurring_payment_record_id, s.instalment_number, s.date_raw,
    s.reminder_date,
    s.reference_rows = 1 and c.sale_id_rows = 1 as source_link_unique,
    cast(null as numeric) as agreed_instalment_amount_rm,
    s.reminder_date is null or s.reference_rows != 1 or c.sale_id_rows != 1 as schedule_review_required,
    c.lifecycle_review_required,
    'OWNER_DEFINED_REMINDER_DATE; GREEN_MEANS_DATE_PASSED_ONLY' as date_evidence
from {{ ref('recurring_contract_candidates') }} c
join schedule_cells s using (sales_record_id)
