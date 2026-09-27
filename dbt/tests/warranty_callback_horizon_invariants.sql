{{ config(tags=['analytics_ml']) }}
select anchor_event_row
from {{ ref('warranty_callback_fixed_horizon_dataset') }} a
join {{ ref('calendar_events') }} e on e.calendar_event_row = a.anchor_event_row
where outcome_end_date != date_add(anchor_date, interval 30 day)
   or outcome_end_date > observed_through
   or warranty_signal_within_30d != (warranty_claim_count_30d > 0)
   or e.event_category != 'service'
   or e.warranty_label_uncertain
   or sales_record_id is null
union all
select anchor_event_row
from {{ ref('warranty_callback_fixed_horizon_dataset') }}
group by anchor_event_row having count(*) != 1
