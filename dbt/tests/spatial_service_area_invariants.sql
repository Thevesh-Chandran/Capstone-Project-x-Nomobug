select area_cell
from {{ ref('spatial_service_area_metrics') }}
where repeat_signal_event_rows > scheduled_service_event_rows
   or repeat_signal_share < 0
   or repeat_signal_share > 1
   or sufficient_volume_for_comparison != (scheduled_service_event_rows >= 5)
