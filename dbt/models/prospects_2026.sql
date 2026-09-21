-- All source rows remain here. Filter row_class = 'prospect_candidate' for analysis.
-- A row is an enquiry record, NOT a unique customer or a confirmed sale.
with source_rows as (
    select
        *,
        '{{ var("prospects_snapshot_id") }}' as snapshot_id,
        timestamp('{{ var("prospects_snapshot_extracted_at") }}') as snapshot_extracted_at,
        nullif(trim(source_column_002), '') as phone_raw_trimmed,
        nullif(trim(source_column_013), '') as first_reply_raw_trimmed,
        regexp_replace(trim(source_column_013), r'[-\s]+', ' ') as first_reply_parse_text,
        upper(regexp_replace(trim(source_column_003), r'\s+', ' ')) as acquisition_label,
        upper(trim(source_column_006)) as customer_type_label,
        upper(trim(source_column_007)) as pest_label,
        upper(trim(source_column_008)) as status_label,
        upper(trim(source_column_009)) as pic_label
    from {{ source('bronze', 'prospects_2026_snapshot') }}
), classified as (
    select
        *,
        {{ acquisition_group('acquisition_label') }} as acquisition_group,
        case
            when phone_raw_trimmed is not null or first_reply_raw_trimmed is not null
                then 'prospect_candidate'
            -- Ignore ONLY the five automatic follow-up columns when detecting placeholders.
            when exists (
                select 1 from unnest([
                    source_column_003, source_column_004, source_column_005,
                    source_column_006, source_column_007, source_column_008,
                    source_column_009, source_column_010, source_column_011,
                    source_column_012, source_column_019, source_column_020,
                    source_column_021, source_column_022, source_column_023,
                    source_column_024
                ]) as value where trim(value) != ''
            ) then 'other_values_needs_review'
            when trim(source_column_001) != '' then 'numbered_only_placeholder'
            else 'followup_only_placeholder'
        end as row_class,
        -- Owner confirmed this tab contains 2026 only; ENGAGE is first staff reply.
        -- SAFE parsing leaves impossible or unexpected date formats null.
        case when regexp_contains(first_reply_parse_text, r'^\d{1,2} [A-Za-z]+$')
            then coalesce(
                safe.parse_date('%d %B %Y', concat(first_reply_parse_text, ' 2026')),
                safe.parse_date('%d %b %Y', concat(first_reply_parse_text, ' 2026'))
            )
        end as first_reply_date,
        case when customer_type_label in ('RESIDENTIAL', 'BUSINESS')
            then customer_type_label end as customer_type,
        case
            when pest_label = 'GPC' then 'GPC'
            when pest_label in ('ANAI ANAI', 'ANAI-ANAI') then 'ANAI ANAI'
        end as pest_category,
        case
            when status_label in ('CLOSED', 'CLOOSED') then 'CLOSED'
            when status_label = 'OPEN' then 'OPEN'
        end as conversation_status,
        case when pic_label in ('CHIA', 'THEVESH') then pic_label end as pic
    from source_rows
)
select
    *,
    acquisition_group = 'UNRESOLVED' as acquisition_needs_review,
    -- Campaign audience is separate from the customer's recorded business type.
    case when acquisition_group in ('BUSINESS_AD', 'REGULAR_AD')
        then regexp_replace(acquisition_label, r'\s+', '') end as campaign_code,
    concat(snapshot_id, ':', cast(source_sheet_row as string)) as snapshot_row_id,
    first_reply_raw_trimmed is not null and first_reply_date is null as first_reply_needs_review,
    customer_type_label != '' and customer_type is null as customer_type_needs_review,
    pest_label != '' and pest_category is null as pest_needs_review,
    status_label != '' and conversation_status is null as status_needs_review,
    pic_label != '' and pic is null as pic_needs_review,
    -- An exact recorded signal only. Missing WON does NOT mean lost.
    upper(trim(source_column_012)) = 'WON' as remark_is_exact_won,
    source_column_003 as acquisition_source_raw,
    source_column_004 as booking_raw,
    source_column_005 as enquiry_prompt_raw,
    source_column_010 as payment_link_raw,
    source_column_011 as category_raw,
    source_column_012 as remark_raw,
    source_column_014 as followup_1_scheduled_raw,
    source_column_015 as followup_2_scheduled_raw,
    source_column_016 as followup_3_scheduled_raw,
    source_column_017 as followup_4_scheduled_raw,
    source_column_018 as followup_5_scheduled_raw
from classified
