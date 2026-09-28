{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set release_prefix = var('release_schema_prefix', '') -%}
    {%- if custom_schema_name is none -%}
        {{ release_prefix ~ target.schema }}
    {%- else -%}
        {{ release_prefix ~ (custom_schema_name | trim) }}
    {%- endif -%}
{%- endmacro %}
