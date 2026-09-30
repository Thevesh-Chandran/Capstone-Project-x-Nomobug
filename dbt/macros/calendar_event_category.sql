{% macro calendar_warranty_keyword_signal(summary_upper) -%}
-- A title saying "NO WARRANTY" describes entitlement, not a claim. Remove
-- only that phrase so an independent "CALLBACK" or "CLAIM" still survives.
regexp_contains(
    regexp_replace({{ summary_upper }}, r'\b(?:NO|WITHOUT)\s+WARRANTY\b', ''),
    r'\b(?:WARRANTY|CLAIMS?|CALLBACK)\b'
)
{%- endmacro %}

{% macro calendar_event_category(summary_upper, status, session_current, session_total, include_warranty=true) -%}
case
    when upper({{ status }}) = 'CANCELLED'
      or regexp_contains({{ summary_upper }}, r'^\s*CANCEL(?:L)?ED\b') then 'cancelled'
    when regexp_contains({{ summary_upper }},
        r'\b(?:CHECK|REVIEW|CALCULATE)\b.*\bCONVERSION\s+RATE\b') then 'administrative'
    {% if include_warranty %}
    -- Explicit callbacks retain their existing meaning even if the team uses
    -- "inspection" in the title. A sequence alone cannot turn a consultation
    -- into a claim visit (the reviewed 2/1 consultation is an example).
    when {{ calendar_warranty_keyword_signal(summary_upper) }} then 'warranty'
    {% endif %}
    when regexp_contains({{ summary_upper }}, r'\b(?:CONSULTATION|INSPECTION)\b') then 'consultation'
    {% if include_warranty %}
    when {{ session_current }} > {{ session_total }} then 'warranty'
    {% endif %}
    when regexp_contains({{ summary_upper }}, r'\b(?:EXTRA|COMPLIMENTARY|FOLLOW[- ]?UP)\b') then 'complimentary'
    when regexp_contains({{ summary_upper }}, r'\b\d{1,2}\s*/\s*\d{1,2}\b') then 'service'
    else 'other'
end
{%- endmacro %}
