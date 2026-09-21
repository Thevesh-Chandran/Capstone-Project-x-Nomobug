{% macro rm_decimal(expression) %}
case when regexp_contains(upper(trim({{ expression }})), r'^(?:RM\s*)?-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$')
    then safe_cast(replace(regexp_replace(upper(trim({{ expression }})), r'^RM\s*', ''), ',', '') as numeric) end
{% endmacro %}

{% macro sales_reference_array(expression) %}
case when regexp_contains(upper(trim({{ expression }})), r'^CUST\s*\d+(?:\s*[,/]\s*(?:CUST\s*)?\d+)*$')
    then array(
        select concat('CUST', regexp_replace(trim(part), r'^CUST\s*', ''))
        from unnest(split(regexp_replace(upper(trim({{ expression }})), r'\s*[,/]\s*', ','), ',')) part
    )
    else cast([] as array<string>) end
{% endmacro %}
