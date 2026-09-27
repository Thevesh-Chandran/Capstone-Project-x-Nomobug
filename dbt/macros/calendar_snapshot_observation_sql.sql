{% macro calendar_snapshot_observation_sql() %}
{% set calendar_source = source('calendar_bronze', 'events') %}
-- Calendar appointments can be scheduled beyond extraction. Only snapshot
-- metadata establishes how far the API was read; the extraction day is partial.
with metadata_rows as (
    select json_value(option_value) as metadata_json
    from `{{ calendar_source.database }}.{{ calendar_source.schema }}.INFORMATION_SCHEMA.TABLE_OPTIONS`
    where table_name = '{{ calendar_source.identifier }}'
      and option_name = 'description'
), metadata as (
    select count(*) as metadata_row_count,
        max(json_value(metadata_json, '$.format_version')) as format_version,
        max(json_value(metadata_json, '$.snapshot_id')) as snapshot_id,
        max(json_value(metadata_json, '$.source_type')) as source_type,
        max(json_value(metadata_json, '$.timezone')) as source_timezone,
        max(json_value(metadata_json, '$.show_deleted')) as show_deleted,
        safe_cast(max(json_value(metadata_json, '$.window_start')) as date) as window_start,
        safe_cast(max(json_value(metadata_json, '$.window_end')) as date) as window_end,
        max(json_value(metadata_json, '$.extracted_at')) as extracted_at_raw,
        safe_cast(max(json_value(metadata_json, '$.extracted_at')) as timestamp) as extracted_at
    from metadata_rows
)
select case
    when metadata_row_count = 1
     and format_version = '1'
     and source_type = 'Google Calendar'
     and source_timezone = 'Asia/Kuala_Lumpur'
     and show_deleted = 'true'
     and concat('calendar_events_', snapshot_id) = '{{ calendar_source.identifier }}'
     and window_start is not null and window_end >= window_start
     and extracted_at is not null and extracted_at <= current_timestamp()
     and regexp_contains(extracted_at_raw, r'(Z|[+-]\d{2}:\d{2})$')
    then least(window_end,
        date_sub(date(extracted_at, 'Asia/Kuala_Lumpur'), interval 1 day),
        date_sub(current_date('Asia/Kuala_Lumpur'), interval 1 day))
    -- Missing, malformed or mismatched metadata produces no mature negatives.
    else cast(null as date)
end as observed_through
from metadata
{% endmacro %}
