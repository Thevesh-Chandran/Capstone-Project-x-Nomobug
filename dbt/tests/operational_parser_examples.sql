{{ config(tags=['operational']) }}
with examples as (
    select * from unnest([
        struct('CUST523 / 524' as value, 2 as expected), ('CUST 501', 1),
        ('CUST1 / unknown', 0), ('60123456789', 0), ('CUST417 ( Giro )', 0), ('', 0)
    ])
)
select value from examples where array_length({{ sales_reference_array('value') }}) != expected
union all
select 'invalid amount' from unnest([1]) where {{ rm_decimal("'TESTING'") }} is not null
union all
select 'comma amount' from unnest([1]) where {{ rm_decimal("'1,200.50'") }} is distinct from numeric '1200.50'
union all
select 'RM amount' from unnest([1]) where {{ rm_decimal("'RM1,200.50'") }} is distinct from numeric '1200.50'
union all
select 'RM spaced amount' from unnest([1]) where {{ rm_decimal("'RM 490.00'") }} is distinct from numeric '490.00'
