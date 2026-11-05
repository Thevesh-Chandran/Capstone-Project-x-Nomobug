{{ config(tags=['gold', 'recurring_tracking']) }}
-- Restricted sale-grain register. Do not restrict to the positive-balance tab.
with classified as (
    select s.*,
        upper(trim(billing_arrangement_raw)) as billing_arrangement,
        regexp_contains(
            concat(coalesce(customer_name_raw, ''), ' ', coalesce(remark_raw, '')),
            r'(?i)\b(?:payment|payments|pay)\s+(?:after|before)\s+(?:each|every)|\bevery\s+\d+\s+(?:services?|months?|treatments?)\b|\b(?:payment|payments|pay)\s+every\s+month\b|\b\d+\s*x\s*payments?\b'
        ) as custom_payment_note,
        regexp_contains(concat(coalesce(customer_name_raw, ''), ' ',
            coalesce(contract_type_raw, ''), ' ', coalesce(remark_raw, '')),
            r'(?i)\b(?:cancelled|canceled|refunded|hold)\b') as lifecycle_review_required,
        count(*) over (partition by sales_record_id) as sale_id_rows
    from {{ ref('sales') }} s
    where sales_record_id is not null
)
select
    sales_row_id, sales_record_id, source_sheet_row, snapshot_table,
    customer_name_raw, billing_arrangement, contract_type_raw,
    first_session_date_raw, sale_total_rm,
    if(trim(deposit_paid_raw) = '', cast(0 as numeric),
        {{ rm_decimal('deposit_paid_raw') }}) as sales_deposit_recorded_rm,
    if(trim(balance_paid_raw) = '', cast(0 as numeric),
        {{ rm_decimal('balance_paid_raw') }}) as sales_balance_paid_recorded_rm,
    {{ rm_decimal('unmapped_ag_raw') }} as sales_remaining_balance_rm,
    billing_arrangement in ('MONTHLY', 'QUARTERLY', 'EVERY 4 MONTHS',
        'AFTER EACH TREATMENT') as explicit_recurring_arrangement,
    custom_payment_note, lifecycle_review_required, sale_id_rows,
    regexp_contains(concat(coalesce(customer_name_raw, ''), ' ', coalesce(remark_raw, '')),
        r'(?i)\bRM\s*\d[\d,.]*\s*(?:before|after)\s+(?:each|every)|\bpayment\s*[-:]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)')
        as specific_payment_terms_note,
    'OWNER_DEFINED_REMINDER_SCHEDULE' as schedule_confirmation_status
from classified
where billing_arrangement in ('MONTHLY', 'QUARTERLY', 'EVERY 4 MONTHS',
    'AFTER EACH TREATMENT') or custom_payment_note
