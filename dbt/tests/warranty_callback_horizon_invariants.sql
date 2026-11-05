{{ config(tags=['analytics_ml']) }}
-- Intrinsic checks are valid for both archived research and future rebuilds.
-- Calendar row numbers are local to a source snapshot, so an archived anchor
-- must never be joined to today's Silver by its row number. Source-category
-- and outcome checks use scripts.audit_callback_evidence with a pinned epoch.
select anchor_event_row
from {{ ref('warranty_callback_fixed_horizon_dataset') }} a
where outcome_end_date != date_add(anchor_date, interval 30 day)
   or outcome_end_date > observed_through
   or warranty_signal_within_30d != (warranty_claim_count_30d > 0)
   or sales_record_id is null
   or anchor_event_row is null
   or anchor_date is null
   or outcome_end_date is null
   or observed_through is null
   or warranty_signal_within_30d is null
   or warranty_claim_count_30d is null
   or warranty_claim_count_30d < 0
union all
select anchor_event_row
from {{ ref('warranty_callback_fixed_horizon_dataset') }}
group by anchor_event_row having count(*) != 1
union all
select min(anchor_event_row) as anchor_event_row
from {{ ref('warranty_callback_fixed_horizon_dataset') }}
group by population, sales_record_id, anchor_date having count(*) != 1
