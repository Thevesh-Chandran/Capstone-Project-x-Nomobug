select case
    when package_sessions_recorded not in (4, 6, 12) then 'ineligible_package'
    when service_number not between 1 and package_sessions_recorded then 'invalid_service_number'
    when coverage_interval_end < coverage_interval_start then 'negative_interval'
    when coverage_interval_end > observed_through then 'immature_interval'
    when exposure_days != date_diff(coverage_interval_end, coverage_interval_start, day) + 1
        then 'invalid_exposure_days'
    when warranty_claim_count_in_interval < warranty_claim_days_in_interval
        then 'claim_days_exceed_claim_events'
    when any_warranty_claim_in_interval != (warranty_claim_count_in_interval > 0)
        then 'binary_count_mismatch'
    else 'overlapping_intervals'
end as failure
from {{ ref('warranty_coverage_service_episodes') }} a
where package_sessions_recorded not in (4, 6, 12)
   or service_number not between 1 and package_sessions_recorded
   or coverage_interval_end < coverage_interval_start
   or coverage_interval_end > observed_through
   or exposure_days != date_diff(coverage_interval_end, coverage_interval_start, day) + 1
   or warranty_claim_count_in_interval < warranty_claim_days_in_interval
   or any_warranty_claim_in_interval != (warranty_claim_count_in_interval > 0)
   or exists (
       select 1
       from {{ ref('warranty_coverage_service_episodes') }} b
       where b.sales_record_id = a.sales_record_id
         and b.service_anchor_event_row != a.service_anchor_event_row
         and a.coverage_interval_start <= b.coverage_interval_end
         and b.coverage_interval_start <= a.coverage_interval_end
   )
