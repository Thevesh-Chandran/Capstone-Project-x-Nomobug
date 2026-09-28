{% macro acquisition_group(label) %}
case
    when {{ label }} = '' then 'MISSING'
    when {{ label }} = 'NA' then 'UNKNOWN'
    when regexp_contains({{ label }}, r'^B\d+$') then 'BUSINESS_AD'
    when regexp_contains({{ label }}, r'^(ADS|A|CA)\s*\d+$') then 'REGULAR_AD'
    when {{ label }} = 'ADS' then 'UNSPECIFIED_AD'
    when {{ label }} in ('WEBSITE', 'WBSITE', 'WEBSIITE') then 'WEBSITE'
    when {{ label }} in ('FACEBOOK', 'FB') then 'FACEBOOK'
    when {{ label }} = 'INSTAGRAM' then 'INSTAGRAM'
    when {{ label }} in ('TIKTOK', 'TIKTOK CHAT') then 'TIKTOK'
    when {{ label }} = 'GOOGLE' then 'GOOGLE'
    when {{ label }} = 'CALL' then 'CALL'
    when {{ label }} in ('REFERRAL', 'REFERAL') then 'REFERRAL'
    when {{ label }} = 'RETURNING CUST' then 'RETURNING_CUSTOMER'
    else 'UNRESOLVED'
end
{% endmacro %}
