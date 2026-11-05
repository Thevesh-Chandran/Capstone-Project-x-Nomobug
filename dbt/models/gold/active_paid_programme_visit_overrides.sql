{{ config(schema='gold', tags=['gold']) }}
-- Future reviewed bookings are retained in the seed, but are not historical visits.
select * from {{ ref('paid_programme_visit_overrides') }}
where cast(expected_event_date as date) <=
{% if var('release_extracted_at_calendar', none) %}
    date(timestamp('{{ var("release_extracted_at_calendar") }}'), 'Asia/Kuala_Lumpur')
{% else %}
    current_date('Asia/Kuala_Lumpur')
{% endif %}
