{% macro phone_numbers(value) -%}
array(
  select distinct canonical from (
    select case
      when regexp_contains(digits, r'^01[0-9]{8,9}$') then concat('+60', substr(digits, 2))
      when regexp_contains(digits, r'^601[0-9]{8,9}$') then concat('+', digits)
      when regexp_contains(trim(piece), r'^\+') and regexp_contains(digits, r'^[1-9][0-9]{7,14}$') then concat('+', digits)
    end as canonical
    from (
      select piece, regexp_replace(piece, r'[^0-9]', '') as digits
      from unnest(regexp_extract_all(coalesce({{ value }}, ''), r'\+?[0-9][0-9 \t().\-]*[0-9]')) piece
    )
  ) where canonical is not null order by canonical
)
{%- endmacro %}
