select 'recurrence_negative_interval' as failure
from {{ ref('dashboard_recurrence_windows') }}
where days_since_previous_event < 0

union all

select 'unvalidated_composite_exposed' as failure
from {{ ref('dashboard_treatment_difficulty') }}
where treatment_difficulty_proxy_0_100 is not null
   or warranty_claim_event_rows + extra_visit_signal_rows > scheduled_event_rows

union all

select 'package_fit_invalid_payment_share' as failure
from {{ ref('dashboard_package_fit_matrix') }}
where packages_with_payment_evidence > package_rows

union all

select 'scheduling_rows_do_not_reconcile' as failure
from unnest([1])
where (select sum(scheduled_event_rows) from {{ ref('dashboard_scheduling_capacity') }})
    != (select count(*) from {{ ref('calendar_service_event_facts') }}
        where event_date_local between date '2026-01-01' and date '2026-12-31')

union all

select 'refund_rows_do_not_reconcile' as failure
from unnest([1])
where (select sum(refund_source_rows) from {{ ref('dashboard_refund_monthly') }})
    != (select count(*) from {{ ref('refund_record_facts') }})
union all
select 'difficulty_join_expansion' as failure
from unnest([1])
where (select sum(scheduled_event_rows) from {{ ref('dashboard_treatment_difficulty') }})
    != (select count(*) from {{ ref('calendar_service_event_facts') }}
        where event_date_local between date '2026-01-01' and date '2026-12-31')
union all
select 'recurrence_without_property_or_signal' as failure
from {{ ref('dashboard_recurrence_windows') }}
where (not property_text_available and previous_calendar_event_row is not null)
   or (regexp_contains(recurrence_bucket, r'^\d') and not warranty_claim_candidate)
   or event_date_local > current_date('Asia/Kuala_Lumpur')
