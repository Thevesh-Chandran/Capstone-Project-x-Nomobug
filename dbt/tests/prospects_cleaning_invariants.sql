-- Tests check consistency, not whether every source label is known.
select snapshot_row_id
from {{ ref('prospects_2026') }}
where
    (first_reply_date is not null and extract(year from first_reply_date) != 2026)
    or first_reply_needs_review != (first_reply_raw_trimmed is not null and first_reply_date is null)
    or customer_type_needs_review != (customer_type_label != '' and customer_type is null)
    or pest_needs_review != (pest_label != '' and pest_category is null)
    or status_needs_review != (status_label != '' and conversation_status is null)
    or pic_needs_review != (pic_label != '' and pic is null)
    or (pest_label in ('CST', 'N', 'WD', 'BEDBUGS') and not pest_needs_review)
    or (status_label in ('CLOSED', 'CLOOSED') and conversation_status is distinct from 'CLOSED')
    or remark_is_exact_won != (upper(trim(source_column_012)) = 'WON')
    or acquisition_needs_review != (acquisition_group = 'UNRESOLVED')
    or (acquisition_label = 'NA' and acquisition_group != 'UNKNOWN')
