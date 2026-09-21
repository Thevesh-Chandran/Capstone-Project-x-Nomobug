{{ config(tags=['calendar', 'gold']) }}
-- A sequence beyond the purchased package (for example 4/3 or 5/3) is a
-- warranty/claim visit, even when the title uses "complimentary".
select calendar_event_row
from {{ ref('calendar_events') }}
where status = 'confirmed' and sequence_over_package and (
    event_category != 'warranty'
    or not warranty_claim_candidate
)
union all
select calendar_event_row
from {{ ref('calendar_events') }}
where warranty_claim_candidate and warranty_claim_reason is null
