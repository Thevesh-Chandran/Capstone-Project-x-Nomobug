{{ config(tags=['operational']) }}
{% for model, source_name, width in [('b2b_follow_up', 'b2b', 25), ('sales', 'sales', 43), ('payments', 'payments', 12)] %}
select '{{ model }}' as model_name, coalesce(b.source_sheet_row, s.source_sheet_row) as row_number
from (
    select source_sheet_row, to_json_string([
    {% for n in range(1, width + 1) %}source_column_{{ '%03d' | format(n) }}{{ ',' if not loop.last }}{% endfor %}
    ]) as raw_values from {{ source('operational_bronze', source_name) }}
) b full outer join (
    select source_sheet_row, to_json_string([
    {% for n in range(1, width + 1) %}source_column_{{ '%03d' | format(n) }}{{ ',' if not loop.last }}{% endfor %}
    ]) as raw_values from {{ ref(model) }}
) s using (source_sheet_row)
where b.raw_values is distinct from s.raw_values
{{ 'union all' if not loop.last }}
{% endfor %}
