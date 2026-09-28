{% macro calendar_address_line(description_text, allow_unlabelled=true) %}
-- A labelled address takes priority. For older unlabelled descriptions, use
-- only a line beginning with a premise number/lot and containing a street or
-- residential cue. Never infer an address from a bare postcode or phone.
coalesce(
    nullif(trim(regexp_replace(
        regexp_extract(replace({{ description_text }}, chr(160), ' '),
            r'(?im)(?:Alamat(?:[*_ ]*[:.]|[ \t]+)|^[ \t*_]*(?:Address(?:es)?|Addres|Full[ \t]+address)[*_ ]*[:.])\s*([^\r\n<]+)'),
        r'(?i)\s+(?:Package|Problem|Invoice(?:\s*id)?|Emel|Email|Phone(?:\s*No)?|Treatment|Nama)\s*:.*$',
        ''
    )), '')
    {% if allow_unlabelled %}
    ,
    nullif(trim(regexp_extract(replace({{ description_text }}, chr(160), ' '),
        r'(?im)^[ \t]*((?:No\.?[ \t]*[0-9]+|Lot[ \t]*[0-9]+|[0-9]+[A-Z]?(?:[-/][A-Z0-9]+)*)(?:[^\r\n<]*?\b(?:Jalan|Jln|Taman|Residensi|Persiaran|Lorong|Road|Street)\b)[^\r\n<]*)'
    )), '')
    {% endif %}
)
{% endmacro %}
