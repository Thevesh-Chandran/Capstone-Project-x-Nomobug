{{ config(tags=['analytics_ml']) }}
select anchor_event_row
from {{ ref('warranty_fixed_horizon_dataset') }}
where outcome_end_date != date_add(anchor_date, interval 30 day)
   or outcome_end_date > observed_through
   or warranty_signal_within_30d != (warranty_claim_count_30d > 0)
   or sales_record_id is null
   or service_number > package_sessions_recorded
union all
select anchor_event_row
from {{ ref('warranty_fixed_horizon_dataset') }}
group by anchor_event_row having count(*) != 1
