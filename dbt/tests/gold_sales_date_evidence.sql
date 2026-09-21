{{ config(tags=['gold']) }}
-- Guard the sequence evidence used to infer the year of pre-timestamp SALES rows.
with early as (
    select
        source_sheet_row,
        closed_date,
        lag(closed_date) over (order by source_sheet_row) as previous_closed_date
    from {{ ref('sales_package_facts') }}
    where closed_date_year_source = 'early_sequence_inferred'
), anchor as (
    select min(closed_date) as first_timestamped_closed_date
    from {{ ref('sales_package_facts') }}
    where closed_date_year_source = 'entry_timestamp'
)
select 'early_date_after_timestamped_anchor' as failure
from unnest([1])
where (select max(closed_date) from early) >
      (select first_timestamped_closed_date from anchor)
union all
select 'early_large_backstep'
from early
where date_diff(closed_date, previous_closed_date, day) < -31
