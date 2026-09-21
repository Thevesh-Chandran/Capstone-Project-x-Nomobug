{{ config(schema='gold', tags=['gold'], materialized='table') }}
-- One row per identified SALES package. A Customer ID is a sale ID, not a person ID.
with source_sales as (
    select s.*,
        safe_cast(regexp_extract(entry_timestamp_raw, r'(?:19|20)[0-9]{2}') as int64) as entry_year,
        regexp_replace(
            regexp_replace(initcap(trim(closed_date_raw)), r'(?i)Sept', 'Sep'),
            r'[ /]+', '-'
        ) as close_day_month
    from {{ ref('sales') }} s
    where s.sales_record_id is not null
), year_context as (
    select *,
        last_value(entry_year ignore nulls) over (
            order by source_sheet_row
            rows between unbounded preceding and 1 preceding
        ) as prior_entry_year,
        first_value(entry_year ignore nulls) over (
            order by source_sheet_row
            rows between 1 following and unbounded following
        ) as next_entry_year,
        min(if(entry_year is not null, source_sheet_row, null)) over () as first_timestamped_row
    from source_sales
), dated as (
    select *,
        case
            when safe.parse_date('%d-%b-%Y', concat(close_day_month, '-2000')) is null
                then null
            when entry_year is not null then entry_year
            when prior_entry_year is null and next_entry_year is not null
                and source_sheet_row < first_timestamped_row then next_entry_year
            when prior_entry_year = next_entry_year then prior_entry_year
        end as closed_date_year,
        case
            when safe.parse_date('%d-%b-%Y', concat(close_day_month, '-2000')) is null
                then 'unresolved'
            when entry_year is not null then 'entry_timestamp'
            when prior_entry_year is null and next_entry_year is not null
                and source_sheet_row < first_timestamped_row then 'early_sequence_inferred'
            when prior_entry_year = next_entry_year then 'adjacent_timestamps_inferred'
            else 'unresolved'
        end as closed_date_year_source
    from year_context
), parsed_dates as (
    select *,
        safe.parse_date(
            '%d-%b-%Y', concat(close_day_month, '-', cast(closed_date_year as string))
        ) as parsed_closed_date,
        safe.parse_date(
            '%d-%b-%Y', concat(
                regexp_replace(initcap(trim(first_contact_date_raw)), r'[ /]+', '-'),
                '-', cast(closed_date_year as string)
            )
        ) as same_year_first_contact_date
    from dated
)
select
    sales_row_id,
    s.sales_record_id,
    source_sheet_row,
    sale_total_rm,
    total_needs_review as sale_total_needs_review,
    closed_date_raw,
    parsed_closed_date as closed_date,
    closed_date_year_source,
    trim(closed_date_raw) != '' and parsed_closed_date is null as closed_date_needs_review,
    trim(closed_date_raw) = '' as closed_date_missing,
    {{ rm_decimal('deposit_paid_raw') }} as deposit_recorded_rm,
    {{ rm_decimal('balance_paid_raw') }} as balance_recorded_rm,
    safe_cast(nullif(trim(total_sessions_raw), '') as int64) as package_sessions_recorded,
    nullif(trim(pest_type_raw), '') as pest_type_raw,
    nullif(trim(package_type_raw), '') as package_type_raw,
    nullif(trim(contract_type_raw), '') as contract_type_raw,
    coalesce(nullif(upper(trim(premise_type_raw)), ''), 'UNKNOWN') as premise_type,
    coalesce(nullif(upper(trim(trbs_raw)), ''), 'UNKNOWN') as trbs_status,
    coalesce(nullif(upper(trim(billing_arrangement_raw)), ''), 'UNKNOWN')
        as billing_arrangement,
    coalesce(nullif(upper(trim(pic_raw)), ''), 'UNKNOWN') as sales_pic,
    case
        when same_year_first_contact_date is null or parsed_closed_date is null then null
        when same_year_first_contact_date <= parsed_closed_date
            then date_diff(parsed_closed_date, same_year_first_contact_date, day)
        else date_diff(parsed_closed_date,
            date_sub(same_year_first_contact_date, interval 1 year), day)
    end as days_first_contact_to_close,
    recorded_returning_client,
    acquisition_relationship_raw,
    s.snapshot_table,
    coalesce(o.disposition, 'recorded_sale_candidate') as sale_disposition,
    o.disposition is null as include_in_sale_count
from parsed_dates s
left join {{ ref('sale_disposition_overrides') }} o
    on s.sales_record_id = o.sales_record_id
