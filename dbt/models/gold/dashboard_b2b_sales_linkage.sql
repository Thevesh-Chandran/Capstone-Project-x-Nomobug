{{ config(schema='gold', tags=['gold', 'dashboard']) }}
with leads as (
    select source_sheet_row as lead_row, status_label,
        regexp_replace(lower(business_name_raw), r'[^a-z0-9]', '') as business,
        regexp_replace(regexp_replace(phone_raw, r'[^0-9]', ''), r'^(60|0+)', '') as phone,
        safe_cast(json_value(to_json_string(b), '$.lead_close_cell_date') as date) as closed
    from {{ ref('b2b_follow_up') }} b
    where trim(business_name_raw) != '' or trim(phone_raw) != ''
), sales as (
    select source_sheet_row as sale_row, sales_record_id,
        regexp_replace(lower(source_column_009), r'[^a-z0-9]', '') as business,
        regexp_replace(regexp_replace(phone_raw, r'[^0-9]', ''), r'^(60|0+)', '') as phone,
        safe_cast(json_value(to_json_string(s), '$.sale_close_cell_date') as date) as closed
    from {{ ref('sales') }} s
    where sales_record_id is not null
), candidates as (
    select lead_row, sale_row,
        count(*) over (partition by lead_row) as sale_candidates,
        count(*) over (partition by sales_record_id) as lead_candidates
    from leads join sales using (business, phone, closed)
    where business != '' and length(phone) between 8 and 10
), summary as (
    select count(*) as prospect_rows,
        countif(status_label = 'WON' and candidates.lead_row is not null) as corroborated_sales
    from leads left join candidates on leads.lead_row = candidates.lead_row
        and sale_candidates = 1 and lead_candidates = 1
)
select *, prospect_rows - corroborated_sales as unresolved_rows from summary
