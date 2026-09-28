-- Any missing/extra row or changed raw value fails this test.
with bronze as (
    select source_sheet_row,
        to_json_string([
            {% for n in range(1, 25) %}
            source_column_{{ '%03d' | format(n) }}{{ ',' if not loop.last }}
            {% endfor %}
        ]) as raw_values
    from {{ source('bronze', 'prospects_2026_snapshot') }}
), silver as (
    select source_sheet_row,
        to_json_string([
            {% for n in range(1, 25) %}
            source_column_{{ '%03d' | format(n) }}{{ ',' if not loop.last }}
            {% endfor %}
        ]) as raw_values
    from {{ ref('prospects_2026') }}
)
select coalesce(b.source_sheet_row, s.source_sheet_row) as source_sheet_row
from bronze b full outer join silver s using (source_sheet_row)
where b.raw_values is distinct from s.raw_values
