{{ config(tags=['calendar', 'matching']) }}
with examples as (
 select 'two_contacts' label, '60 11-6164 1493 / 6011-11013001' value, ['+601111013001', '+601161641493'] expected
 union all select 'search_format', '60 11-1101 3001', ['+601111013001']
 union all select 'local_format', '011-1101 3001', ['+601111013001']
 union all select 'annotation', '010-2564605 / +60 11-32954153 (contact)', ['+60102564605', '+601132954153']
 union all select 'do_not_truncate', '0111101300101161641493', cast([] as array<string>)
 union all select 'empty', 'N/A', cast([] as array<string>)
 union all select 'repeat', '01111013001 / +601111013001', ['+601111013001']
 union all select 'foreign_explicit', '+81 90-7213-2055', ['+819072132055']
)
select label from examples
where to_json_string({{ phone_numbers('value') }}) != to_json_string(expected)
