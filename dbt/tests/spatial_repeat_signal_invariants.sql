select s.calendar_event_row
from {{ ref('spatial_repeat_signal_events') }} s
join {{ ref('calendar_service_event_facts') }} e using (calendar_event_row)
where not e.warranty_claim_candidate
   or not e.heatmap_eligible
   or s.location_precision_tier not in ('precise_candidate', 'street_candidate')
   or s.outcome_evidence != 'scheduled_or_recorded_repeat_proxy_not_confirmed_reinfestation'
