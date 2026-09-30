{{ config(tags=['calendar', 'gold']) }}
-- Sequence overrun denotes warranty unless an audited exception, administrative
-- reminder or consultation proves the entry represents a different activity.
select calendar_event_row
from {{ ref('calendar_events') }}
where status = 'confirmed' and sequence_over_package
  and warranty_label_review_status = 'Not reviewed'
  and event_category not in ('consultation', 'administrative', 'cancelled') and (
    event_category != 'warranty'
    or not warranty_claim_candidate
)
union all
select calendar_event_row
from {{ ref('calendar_events') }}
where warranty_claim_candidate and warranty_claim_reason is null
