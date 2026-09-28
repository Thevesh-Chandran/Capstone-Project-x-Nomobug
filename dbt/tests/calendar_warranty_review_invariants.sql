{{ config(tags=['calendar']) }}
-- Every reviewed snapshot row must still identify the same event. A changed
-- snapshot must fail this check instead of moving a decision onto another row.
select 'review_event_identity' as check_name, r.calendar_event_row
from {{ ref('calendar_warranty_review_overrides') }} r
left join {{ ref('calendar_events') }} e
  on to_hex(sha256(concat(e.calendar_id, '|', e.event_id))) = r.event_identity_hash
 and e.event_id = r.event_id
where e.calendar_event_row is null or e.warranty_label_review_id is distinct from r.review_id
union all
select 'reviewed_positive', calendar_event_row
from {{ ref('calendar_events') }}
where status = 'confirmed' and warranty_label_review_status = 'Confirmed warranty claim'
  and (warranty_claim_candidate is distinct from true or event_category != 'warranty'
       or warranty_claim_reason != 'manual_review_confirmed_claim')
union all
select 'reviewed_negative', calendar_event_row
from {{ ref('calendar_events') }}
where warranty_label_review_status = 'Not a warranty claim'
  and (warranty_claim_candidate is distinct from false or event_category = 'warranty')
union all
select 'unclear_is_not_negative', calendar_event_row
from {{ ref('calendar_events') }}
where warranty_label_review_status = 'Unclear'
  and (warranty_claim_candidate is not null or not warranty_label_uncertain
       or warranty_claim_reason is not null or service_candidate or extra_visit_candidate)
union all
select 'resolved_is_not_unclear', calendar_event_row
from {{ ref('calendar_events') }}
where warranty_label_review_status != 'Unclear' and warranty_label_uncertain
union all
select 'non_service_cannot_be_claim', calendar_event_row
from {{ ref('calendar_events') }}
where event_category in ('cancelled', 'administrative', 'consultation') and warranty_claim_candidate
