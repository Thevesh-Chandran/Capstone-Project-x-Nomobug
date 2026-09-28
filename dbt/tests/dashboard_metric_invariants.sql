{{ config(tags=['gold', 'dashboard']) }}
select cast(service_month as string) as record_key
from {{ ref('dashboard_service_monthly') }}
where warranty_claim_event_rows > scheduled_service_event_rows
   or generic_complimentary_event_rows > scheduled_service_event_rows
   or warranty_claim_event_share < 0
   or warranty_claim_event_share > 1
   or heatmap_warranty_claim_share < 0
   or heatmap_warranty_claim_share > 1
union all
select sales_record_id
from {{ ref('dashboard_warranty_package_metrics') }}
where warranty_claim_event_rows > scheduled_service_event_rows
   or generic_complimentary_event_rows > scheduled_service_event_rows
   or has_warranty_claim_signal != (warranty_claim_event_rows > 0)
   or warranty_claim_event_share < 0
   or warranty_claim_event_share > 1
   or heatmap_warranty_claim_share < 0
   or heatmap_warranty_claim_share > 1
