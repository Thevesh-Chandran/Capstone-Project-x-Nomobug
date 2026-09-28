{{ config(schema='gold', tags=['gold', 'dashboard', 'looker']) }}
-- The release runner supplies extraction timestamps from the validated
-- immutable Bronze manifest. These are source-snapshot times, not service
-- completion times or model-prediction times. No raw source content is shown.
{% set pinned_sources = [
    ('b2b', 'operational_bronze', 'b2b'),
    ('sales', 'operational_bronze', 'sales'),
    ('payments', 'operational_bronze', 'payments'),
    ('payments_date_serials', 'operational_bronze', 'payments_date_serials'),
    ('payment_link', 'operational_bronze', 'payment_link'),
    ('warranty_claim', 'operational_bronze', 'warranty_claim'),
    ('commercial_clients', 'operational_bronze', 'commercial_clients'),
    ('refund', 'operational_bronze', 'refund'),
    ('recurring_payments', 'operational_bronze', 'recurring_payments'),
    ('calendar', 'calendar_bronze', 'events'),
] %}
with pinned as (
    {% for name, source_name, table_name in pinned_sources %}
    select
        '{{ name }}' as source_name,
        '{{ source(source_name, table_name).identifier }}' as snapshot_table,
        safe_cast(nullif('{{ var("release_extracted_at_" ~ name, "") }}', '') as timestamp)
            as extracted_at_utc,
        nullif('{{ var("release_run_id", "") }}', '') as release_run_id
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
    union all
    select
        'prospects' as source_name,
        '{{ source("bronze", "prospects_2026_snapshot").identifier }}' as snapshot_table,
        safe_cast(nullif('{{ var("release_extracted_at_prospects", var("prospects_snapshot_extracted_at", "")) }}', '') as timestamp)
            as extracted_at_utc,
        nullif('{{ var("release_run_id", "") }}', '') as release_run_id
)
select
    source_name,
    snapshot_table,
    extracted_at_utc,
    release_run_id,
    timestamp_diff(current_timestamp(), extracted_at_utc, hour) as hours_since_extraction,
    'immutable Bronze extraction timestamp; published only after release checks' as freshness_evidence
from pinned
