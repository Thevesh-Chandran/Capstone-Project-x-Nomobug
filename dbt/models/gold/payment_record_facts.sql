{{ config(schema='gold', tags=['gold'], materialized='table') }}
-- One row per PAYMENTS entry. The underlying Sheets serial contains the year;
-- the displayed date does not. Owner says the legacy completion status is unused.
with date_cells as (
    select source_sheet_row, payment_date_display_raw, unformatted_type,
        case when unformatted_type = 'serial' then
            date_add(date '1899-12-30', interval cast(floor(safe_cast(unformatted_value as float64)) as int64) day)
        end as payment_date
    from {{ source('operational_bronze', 'payments_date_serials') }}
)
select
    p.payment_record_id,
    p.source_sheet_row,
    p.payment_date_raw,
    d.payment_date,
    d.unformatted_type as payment_date_cell_type,
    d.payment_date > current_date('Asia/Kuala_Lumpur') as payment_date_future,
    d.unformatted_type = 'text' or d.payment_date > current_date('Asia/Kuala_Lumpur') as payment_date_needs_review,
    p.amount_rm,
    p.amount_needs_review,
    p.reference_status,
    array_length(p.sales_references) as referenced_sale_count,
    p.snapshot_table
from {{ ref('payments') }} p
left join date_cells d using (source_sheet_row)
