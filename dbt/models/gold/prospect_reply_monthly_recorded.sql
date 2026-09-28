{{ config(schema='gold', tags=['gold']) }}
-- Staff first-reply records from the 2026 tab; no customer deduplication or
-- cross-source conversion rate. Auto-filled follow-up dates are not used.
select
    snapshot_id,
    max(snapshot_extracted_at) as snapshot_extracted_at,
    date_trunc(first_reply_date, month) as first_reply_month,
    count(*) as prospect_candidate_rows,
    countif(conversation_status = 'OPEN') as recorded_open_rows,
    countif(conversation_status = 'CLOSED') as recorded_closed_rows,
    countif(remark_is_exact_won) as exact_won_remark_rows,
    countif(first_reply_date is null) as undated_first_reply_rows,
    countif(first_reply_date > current_date('Asia/Kuala_Lumpur')) as future_first_reply_rows,
    countif(acquisition_needs_review) as acquisition_review_rows
from {{ ref('prospects_2026') }}
where row_class = 'prospect_candidate'
group by snapshot_id, first_reply_month
