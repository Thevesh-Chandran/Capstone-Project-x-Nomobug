{# Standard pest category from free-text Sales pest names, e.g. 'Lipas dan semut' -> 'Cockroach + Ant'.
   Same keywords and order as PESTS in webapp/analytics.py (a test keeps the two in step). #}
{% macro pest_group(expr) -%}
case
    when nullif(trim({{ expr }}), '') is null then 'Unspecified'
    else coalesce(nullif(array_to_string(array(
        select label from unnest([
            struct('Cockroach' as label, regexp_contains(upper({{ expr }}), r'\b(LIPAS|COCKROACH|GPC)') as hit),
            struct('Ant' as label, regexp_contains(upper({{ expr }}), r'\b(SEMUT|SEMUIT|ANT)') as hit),
            struct('Rodent' as label, regexp_contains(upper({{ expr }}), r'\b(TIKUS|TIKSU|RODENT|RAT)') as hit),
            struct('Termite' as label, regexp_contains(upper({{ expr }}), r'\b(ANAI|TERMITE)') as hit),
            struct('Fly' as label, regexp_contains(upper({{ expr }}), r'\b(LALAT|FLY)') as hit),
            struct('Centipede / millipede' as label, regexp_contains(upper({{ expr }}), r'\b(LIPAN|GONGGOK|KAMITETEP)') as hit),
            struct('Bed bug' as label, regexp_contains(upper({{ expr }}), r'\b(BED BUG|BEDBUG|PEPIJAT)') as hit),
            struct('Mosquito' as label, regexp_contains(upper({{ expr }}), r'\b(NYAMUK|MOSQUITO)') as hit)
        ]) with offset as position
        where hit
        order by position
    ), ' + '), ''), 'Other / unspecified')
end
{%- endmacro %}
