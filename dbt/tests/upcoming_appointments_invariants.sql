select * from {{ ref('dashboard_upcoming_appointments') }}
where scheduled_event_rows <= 0 or service_date < current_date('Asia/Kuala_Lumpur')
    or service_date > date_add(current_date('Asia/Kuala_Lumpur'), interval 29 day)
    or extracted_at is null or calendar_name is null
