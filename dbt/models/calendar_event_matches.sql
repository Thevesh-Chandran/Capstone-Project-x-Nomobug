{{ config(tags=['calendar', 'matching']) }}
with raw_calendar as (
    select
        calendar_event_row,
        calendar_name,
        calendar_id,
        event_id,
        status,
        event_type,
        start_raw,
        end_raw,
        is_all_day,
        recurring_event_id,
        upper(coalesce(summary, '')) as summary_upper,
        regexp_replace(
            regexp_replace(coalesce(description, ''), r'(?i)</?(?:p|div|li|br)\b[^>]*>', '\n'),
            r'<[^>]+>', ''
        ) as description_text
    from {{ source('calendar_bronze', 'events') }}
), parsed as (
    select *,
        nullif(trim(regexp_extract(description_text,
            r'(?im)^[ \t*_]*(?:Phone[ \t]*(?:No\.?|Number)?|No\.?[ \t]*(?:Tel|Telefon|Fon)|Contact[ \t]*Number|H/P|Mobile[ \t]*No\.?)\s*[ \t*_]*:\s*([^\r\n<]+)')), '') as phone_raw,
        nullif(trim(regexp_extract(description_text,
            r'(?im)^[ \t*_]*(?:Invoice(?:\s*ID)?|INV)[ \t*_]*:\s*([^\r\n<]+)')), '') as invoice_raw,
        nullif(trim(regexp_extract(description_text,
            r'(?im)^[ \t*_]*Nama(?:\s+(?:Premis|Penuh|PIC|Syarikat|Kedai))?[ \t*_]*:\s*([^\r\n<]+)')), '') as premise_name_raw,
        nullif(trim(regexp_extract(description_text,
            r'(?im)^[ \t*_]*(?:Name|Customer\s+Name|Customers\s+Details)[ \t*_]*:\s*([^\r\n<]+)')), '') as customer_name_raw,
        {{ calendar_address_line('description_text', allow_unlabelled=false) }} as address_raw,
        nullif(trim(regexp_extract(description_text,
            r'(?im)^Username\s*:\s*([^\r\n<]+)')), '') as username_raw,
        nullif(trim(regexp_extract(description_text,
            r'(?im)^[ \t*_]*(?:Emel|Email|E-Mail|Valid\s+Emel)[ \t*_]*:\s*([^\r\n<]+)')), '') as email_raw
    from raw_calendar
), keys as (
    select *,
        {{ phone_numbers('phone_raw') }} as phone_keys,
        date(safe_cast(start_raw as timestamp), 'Asia/Kuala_Lumpur') as event_date_local_key,
        safe_cast(regexp_extract(summary_upper, r'\b(\d{1,2})\s*/\s*\d{1,2}\b') as int64) as title_session_current,
        safe_cast(regexp_extract(summary_upper, r'\b\d{1,2}\s*/\s*(\d{1,2})\b') as int64) as title_session_total,
        regexp_contains(summary_upper, r'\bHOUSE\s*(?:&|AND)\s*CAR\s*3\s*X\b')
            as compound_house_car_3x,
        upper(regexp_replace(coalesce(invoice_raw, ''), r'\s+', '')) as invoice_key,
        lower(trim(coalesce(email_raw, ''))) as email_key,
        upper(regexp_replace(coalesce(address_raw, ''), r'[^A-Z0-9]', '')) as address_key,
        upper(regexp_replace(upper(coalesce(address_raw, '')), r'[^A-Z0-9]', '')) as address_compare_key,
        upper(regexp_replace(coalesce(
            regexp_extract(summary_upper, r'\b\d{1,2}\s*/\s*\d{1,2}\s+(.+)$'), ''),
            r'[^A-Z0-9]', '')) as title_name_key,
        upper(regexp_replace(coalesce(
            regexp_extract(summary_upper, r'\b\d{1,2}\s*/\s*\d{1,2}\s+([^()]+)'), ''),
            r'[^A-Z0-9]', '')) as title_customer_key,
        upper(regexp_replace(coalesce(
            regexp_extract(summary_upper, r'\b\d{1,2}\s*/\s*\d{1,2}\s+[^()]+\(([^()]+)\)'), ''),
            r'[^A-Z0-9]', '')) as title_qualifier_key,
        upper(regexp_replace(coalesce(
            regexp_extract(summary_upper,
                r'\b(?:WARRANTY|WARRANTRY|COMPLIMENTARY|EXTRA\s+VISIT|CAR\s+ONLY)\s+([^()]+)'),
            ''), r'[^A-Z0-9]', '')) as event_customer_key,
        coalesce(upper(regexp_extract(summary_upper, r'\bHOUSE\s*([0-9]+)\b')), '') as property_key
    from parsed
), sales_prepared as (
    select *,
        coalesce(
            safe.parse_date('%Y-%m-%d', regexp_extract(source_column_003, r'^\d{4}-\d{1,2}-\d{1,2}')),
            safe.parse_date('%m/%d/%Y', regexp_extract(source_column_003, r'^\d{1,2}/\d{1,2}/\d{4}'))
        ) as source_timestamp_date
    from {{ source('operational_bronze', 'sales') }}
    where trim(source_column_007) != ''
), sales_keys as (
    select
        trim(source_column_007) as sales_record_id,
        {{ phone_numbers('source_column_010') }} as phone_keys,
        source_timestamp_date,
        safe.parse_date('%d-%b-%Y', concat(trim(source_column_004), '-', cast(extract(year from source_timestamp_date) as string))) as closed_date,
        safe_cast(trim(source_column_014) as int64) as total_sessions,
        upper(regexp_replace(source_column_030, r'\s+', '')) as invoice_a_key,
        upper(regexp_replace(source_column_032, r'\s+', '')) as invoice_b_key,
        lower(trim(source_column_012)) as email_key,
        upper(regexp_replace(source_column_011, r'[^A-Z0-9]', '')) as address_key,
        upper(regexp_replace(upper(source_column_011), r'[^A-Z0-9]', '')) as address_compare_key,
        upper(regexp_replace(upper(source_column_009), r'[^A-Z0-9]', '')) as name_key,
        upper(regexp_replace(coalesce(regexp_extract(upper(source_column_009), r'^([^()]+)'), ''), r'[^A-Z0-9]', '')) as name_base_key,
        upper(regexp_replace(upper(source_column_009), r'[^A-Z0-9]', '')) as sales_customer_key,
        coalesce(upper(regexp_extract(upper(source_column_009), r'\bHOUSE\s*([0-9]+)\b')), '') as property_key
    from sales_prepared
), sales_matches as (
    select distinct
        k.calendar_event_row,
        s.sales_record_id,
        case
            when regexp_contains(k.invoice_key, r'[0-9]') and length(k.invoice_key) >= 8 and (
                k.invoice_key = s.invoice_a_key or k.invoice_key = s.invoice_b_key
            ) then 'invoice'
            when k.email_key != '' and strpos(k.email_key, '@') > 0 and k.email_key = s.email_key then 'email'
        end as match_method
    from keys k
    join sales_keys s on (
        (regexp_contains(k.invoice_key, r'[0-9]') and length(k.invoice_key) >= 8 and (
            k.invoice_key = s.invoice_a_key or k.invoice_key = s.invoice_b_key
        ))
        or (k.email_key != '' and strpos(k.email_key, '@') > 0 and k.email_key = s.email_key)
    )
), calendar_phones as (
    select k.calendar_event_row, phone_key from keys k, unnest(k.phone_keys) phone_key
), sales_phones as (
    select distinct s.sales_record_id, phone_key from sales_keys s, unnest(s.phone_keys) phone_key
), phone_matches as (
    select distinct k.calendar_event_row, s.sales_record_id, 'phone' as match_method
    from calendar_phones k join sales_phones s using (phone_key)
), phone_match_counts as (
    select calendar_event_row, count(distinct sales_record_id) as candidate_count
    from phone_matches
    group by calendar_event_row
), phone_title_qualifier_candidates as (
    select distinct p.calendar_event_row, p.sales_record_id, s.closed_date
    from phone_matches p
    join keys k using (calendar_event_row)
    join sales_keys s using (sales_record_id)
    where length(k.title_qualifier_key) >= 5
      and strpos(s.name_key, k.title_qualifier_key) > 0
      and k.title_session_total = s.total_sessions
      and s.closed_date <= k.event_date_local_key
      and abs(date_diff(s.closed_date, s.source_timestamp_date, day)) <= 31
), phone_title_qualifier_ranked as (
    select *,
        row_number() over (
            partition by calendar_event_row
            order by closed_date desc, sales_record_id
        ) as candidate_rank,
        count(*) over (
            partition by calendar_event_row, closed_date
        ) as same_date_count
    from phone_title_qualifier_candidates
), phone_title_qualifier_resolved as (
    select calendar_event_row, sales_record_id,
        'phone_title_qualifier' as match_method
    from phone_title_qualifier_ranked
    where candidate_rank = 1 and same_date_count = 1
), direct_match_counts as (
    select calendar_event_row, count(distinct sales_record_id) as direct_candidate_count
    from (
        select calendar_event_row, sales_record_id from sales_matches
        union all
        select calendar_event_row, sales_record_id from phone_matches
    )
    group by calendar_event_row
), first_session_anchors as (
    select distinct a.calendar_event_row, a.title_session_total,
        a.event_date_local_key, a.address_key, a.property_key,
        sp.sales_record_id, s.total_sessions, s.name_base_key,
        s.sales_customer_key
    from keys a
    cross join unnest(a.phone_keys) phone_key
    join sales_phones sp using (phone_key)
    join sales_keys s using (sales_record_id)
    where a.status = 'confirmed' and a.title_session_current = 1
      and s.total_sessions = a.title_session_total
      and (a.property_key = '' or s.property_key = '' or a.property_key = s.property_key)
), phone_date_session_candidates as (
    select distinct p.calendar_event_row, p.sales_record_id, s.closed_date,
        (
            case when k.title_customer_key != '' and s.name_base_key != '' and (
                k.title_customer_key = s.name_base_key
                or (least(length(k.title_customer_key), length(s.name_base_key)) >= 4 and (
                    strpos(s.name_base_key, k.title_customer_key) > 0
                    or strpos(k.title_customer_key, s.name_base_key) > 0
                ))
            ) then 8 else 0 end
            + case when length(k.address_compare_key) >= 12
                and length(s.address_compare_key) >= 12 and (
                    strpos(k.address_compare_key, s.address_compare_key) > 0
                    or strpos(s.address_compare_key, k.address_compare_key) > 0
                ) then 4 else 0 end
            + case when k.compound_house_car_3x and k.title_session_total = 3
                and s.total_sessions = 6 then 8 else 0 end
        ) as evidence_score
    from phone_matches p
    join phone_match_counts pmc using (calendar_event_row)
    join keys k using (calendar_event_row)
    join sales_keys s using (sales_record_id)
    join first_session_anchors anchor
      on anchor.sales_record_id = p.sales_record_id
     and (
         anchor.title_session_total = k.title_session_total
         or (k.compound_house_car_3x and k.title_session_total = 3
             and anchor.title_session_total = 6)
     )
     and anchor.event_date_local_key between s.closed_date and k.event_date_local_key
     and (
         anchor.address_key = '' or k.address_key = '' or anchor.address_key = k.address_key
         or (k.compound_house_car_3x and k.title_session_total = 3
             and s.total_sessions = 6 and k.title_customer_key != ''
             and s.name_base_key != '' and (
                 strpos(s.name_base_key, k.title_customer_key) > 0
                 or strpos(k.title_customer_key, s.name_base_key) > 0
             ))
     )
    where pmc.candidate_count > 1
      and k.title_session_total between 1 and 100
      and (
          s.total_sessions = k.title_session_total
          or (k.compound_house_car_3x and k.title_session_total = 3
              and s.total_sessions = 6)
      )
      and s.closed_date <= k.event_date_local_key
      and abs(date_diff(s.closed_date, s.source_timestamp_date, day)) <= 31
), phone_date_session_ranked as (
    select *,
        row_number() over (
            partition by calendar_event_row
            order by evidence_score desc, closed_date desc, sales_record_id
        ) as candidate_rank,
        count(*) over (
            partition by calendar_event_row, evidence_score, closed_date
        ) as same_score_date_count
    from phone_date_session_candidates
), phone_date_session_resolved as (
    select c.calendar_event_row, c.sales_record_id,
        'phone_date_session' as match_method
    from phone_date_session_ranked c
    where c.candidate_rank = 1 and c.same_score_date_count = 1
), name_matches as (
    select distinct k.calendar_event_row, s.sales_record_id, 'name' as match_method
    from keys k join sales_keys s on (
        k.title_name_key = s.name_base_key
        or k.title_customer_key = s.name_base_key
    )
    where (k.title_name_key != '' or k.title_customer_key != '') and s.name_base_key != ''
), address_matches as (
    select distinct k.calendar_event_row, s.sales_record_id, 'address' as match_method
    from keys k join sales_keys s on k.address_key = s.address_key
    where length(k.address_key) >= 8 and length(s.address_key) >= 8
), base_sales_candidates as (
    select distinct calendar_event_row, sales_record_id from (
        select calendar_event_row, sales_record_id from sales_matches
        union all
        select calendar_event_row, sales_record_id from phone_matches
        union all
        select calendar_event_row, sales_record_id from name_matches
        union all
        select calendar_event_row, sales_record_id from address_matches
    )
), closed_date_evidence as (
    select
        c.calendar_event_row,
        c.sales_record_id,
        s.closed_date,
        (
            case when (
                k.title_customer_key != '' and s.name_base_key != '' and (
                    k.title_customer_key = s.name_base_key
                    or strpos(s.name_base_key, k.title_customer_key) > 0
                    or strpos(k.title_customer_key, s.name_base_key) > 0
                )
            ) then 8 else 0 end
            + case when k.title_session_total is null
                and length(k.address_compare_key) >= 12
                and k.address_compare_key = s.address_compare_key then 12
                when length(k.address_compare_key) >= 12
                and length(s.address_compare_key) >= 12 and (
                    strpos(k.address_compare_key, s.address_compare_key) > 0
                    or strpos(s.address_compare_key, k.address_compare_key) > 0
                ) then 4 else 0 end
            + case when k.title_session_total is not null and s.total_sessions = k.title_session_total then 2 else 0 end
        ) as evidence_score
    from base_sales_candidates c
    join keys k using (calendar_event_row)
    join sales_keys s using (sales_record_id)
    left join direct_match_counts d using (calendar_event_row)
    where s.closed_date is not null
      and s.closed_date <= k.event_date_local_key
      and coalesce(d.direct_candidate_count, 0) != 1
), closed_date_evidence_ranked as (
    select *,
        row_number() over (
            partition by calendar_event_row
            order by evidence_score desc, closed_date desc, sales_record_id
        ) as evidence_rank,
        count(*) over (
            partition by calendar_event_row, evidence_score, closed_date
        ) as same_score_date_count
    from closed_date_evidence
    where evidence_score > 0
), closed_date_evidence_resolved as (
    select calendar_event_row, sales_record_id,
        'closed_date_evidence' as match_method
    from closed_date_evidence_ranked
    where evidence_rank = 1 and same_score_date_count = 1
), calendar_sequence_anchor_candidates as (
    select distinct
        k.calendar_event_row,
        p.sales_record_id,
        a.event_date_local_key as anchor_date,
        case when k.property_key != '' and s.property_key != ''
                  and k.property_key = s.property_key then 1 else 0 end as property_match,
        case when k.address_compare_key != '' and s.address_compare_key != ''
                  and k.address_compare_key = s.address_compare_key then 1 else 0 end as address_match,
        case when (
            k.title_customer_key != '' and s.sales_customer_key != '' and (
                strpos(s.sales_customer_key, k.title_customer_key) > 0
                or strpos(k.title_customer_key, s.name_base_key) > 0
            )
        ) then 1 else 0 end as customer_name_match,
        case when (
            k.event_customer_key != '' and s.sales_customer_key != '' and (
                strpos(s.sales_customer_key, k.event_customer_key) > 0
                or strpos(k.event_customer_key, s.name_base_key) > 0
            )
        ) then 1 else 0 end as event_name_match
    from phone_matches p
    join keys k using (calendar_event_row)
    join sales_keys s using (sales_record_id)
    join first_session_anchors a
     on a.sales_record_id = p.sales_record_id
     and a.event_date_local_key <= k.event_date_local_key
     and (
         k.title_session_total is null
         or a.title_session_total = k.title_session_total
         or (
             k.title_session_current > a.title_session_total
             and k.title_session_total > a.title_session_total
         )
     )
     and (k.property_key = '' or s.property_key = '' or k.property_key = s.property_key)
    where (
          (k.address_compare_key != '' and s.address_compare_key != '' and
           k.address_compare_key = s.address_compare_key)
          or (
              (k.title_customer_key != '' and s.sales_customer_key != '' and
               strpos(s.sales_customer_key, k.title_customer_key) > 0)
              or (k.event_customer_key != '' and s.sales_customer_key != '' and
                  strpos(s.sales_customer_key, k.event_customer_key) > 0)
          )
    )
), calendar_sequence_anchor_latest as (
    select *,
        max(anchor_date) over (
            partition by calendar_event_row, sales_record_id
        ) as latest_anchor_date
    from calendar_sequence_anchor_candidates
), calendar_sequence_anchor_ranked as (
    select *,
        row_number() over (
            partition by calendar_event_row
            order by property_match desc, address_match desc,
                     latest_anchor_date desc, event_name_match desc,
                     customer_name_match desc, sales_record_id
        ) as anchor_rank,
        count(*) over (
            partition by calendar_event_row, latest_anchor_date
        ) as same_latest_anchor_count
    from calendar_sequence_anchor_latest
), calendar_sequence_anchor_resolved as (
    select calendar_event_row, sales_record_id,
        'calendar_sequence_anchor' as match_method
    from calendar_sequence_anchor_ranked
    where anchor_rank = 1 and same_latest_anchor_count = 1
), all_sales_matches as (
    select * from sales_matches
    union all
    select * from phone_title_qualifier_resolved
    union all
    select * from phone_date_session_resolved
    union all
    select * from closed_date_evidence_resolved
    union all
    select * from calendar_sequence_anchor_resolved
    union all
    select * from phone_matches
    union all
    select * from name_matches
    union all
    select * from address_matches
), ranked_sales_matches as (
    select *,
        case match_method
            when 'invoice' then 1
            when 'phone_title_qualifier' then 2
            when 'phone_date_session' then 3
            when 'calendar_sequence_anchor' then 4
            when 'closed_date_evidence' then 5
            when 'phone' then 6
            when 'email' then 7
            when 'address' then 8
            else 9
        end as match_rank
    from all_sales_matches
), best_sales_matches as (
    select * from ranked_sales_matches
    qualify match_rank = min(match_rank) over (partition by calendar_event_row)
), payment_link_keys as (
    select distinct
        {{ phone_numbers('source_column_002') }} as phone_keys,
        source_sheet_row
    from {{ source('operational_bronze', 'payment_link') }}
    where trim(source_column_002) != ''
), payment_link_matches as (
    select k.calendar_event_row, count(distinct p.source_sheet_row) as payment_link_match_count
    from calendar_phones k join (
      select distinct source_sheet_row, phone_key
      from payment_link_keys, unnest(phone_keys) phone_key
    ) p using (phone_key)
    group by k.calendar_event_row
), sales_summary as (
    select calendar_event_row,
        count(distinct sales_record_id) as sales_match_count,
        min(match_rank) as best_match_rank,
        countif(match_method = 'invoice') as invoice_match_count,
        countif(match_method = 'phone_date_session') as phone_date_session_match_count,
        countif(match_method = 'calendar_sequence_anchor') as calendar_sequence_anchor_match_count,
        countif(match_method = 'phone') as phone_match_count,
        countif(match_method = 'email') as email_match_count,
        countif(match_method = 'name') as name_match_count,
        countif(match_method = 'address') as address_match_count,
        array_agg(distinct sales_record_id ignore nulls) as matched_sales_ids
    from best_sales_matches
    group by calendar_event_row
), warranty_summary as (
    select s.calendar_event_row, count(distinct w.source_sheet_row) as warranty_claim_count
    from sales_summary s cross join unnest(s.matched_sales_ids) as matched_id
    join {{ source('operational_bronze', 'warranty_claim') }} w
      on upper(trim(w.source_column_002)) = upper(trim(matched_id))
        where s.sales_match_count = 1 and s.best_match_rank < 9
    group by s.calendar_event_row
)
select
    k.calendar_event_row,
    k.calendar_name,
    k.calendar_id,
    k.event_id,
    k.status,
    k.event_type,
    k.start_raw,
    k.end_raw,
    safe_cast(k.start_raw as timestamp) as event_start_ts,
    date(safe_cast(k.start_raw as timestamp), 'Asia/Kuala_Lumpur') as event_date_local,
    k.is_all_day,
    k.recurring_event_id,
    ce.event_category,
    ce.service_candidate,
    case when ce.service_candidate then 'service_candidate' else 'non_service_event' end as matching_scope,
    k.phone_raw is not null as phone_present,
    array_length(k.phone_keys) as parsed_phone_count,
    k.invoice_raw is not null as invoice_present,
    coalesce(k.premise_name_raw, k.customer_name_raw) is not null as name_present,
    k.title_name_key != '' as title_name_present,
    k.username_raw is not null as username_present,
    k.email_raw is not null as email_present,
    coalesce(s.sales_match_count, 0) as sales_match_count,
    coalesce(s.invoice_match_count, 0) as invoice_match_count,
    coalesce(s.phone_match_count, 0) as phone_match_count,
    coalesce(s.email_match_count, 0) as email_match_count,
    coalesce(s.address_match_count, 0) as address_match_count,
    case when coalesce(s.sales_match_count, 0) = 1 and s.best_match_rank < 9 then s.matched_sales_ids[offset(0)] end as matched_sales_record_id,
    coalesce(s.phone_date_session_match_count, 0) as phone_date_session_match_count,
    coalesce(s.calendar_sequence_anchor_match_count, 0) as calendar_sequence_anchor_match_count,
    coalesce(p.payment_link_match_count, 0) as payment_link_match_count,
    coalesce(w.warranty_claim_count, 0) as warranty_claim_count,
    case
        when s.sales_match_count = 1 and s.best_match_rank = 1 then 'high_invoice'
        when s.sales_match_count = 1 and s.best_match_rank = 2 then 'medium_phone_title_qualifier'
        when s.sales_match_count = 1 and s.best_match_rank = 3 then 'medium_phone_date_session'
        when s.sales_match_count = 1 and s.best_match_rank = 4 then 'medium_calendar_sequence'
        when s.sales_match_count = 1 and s.best_match_rank = 5 then 'medium_closed_date_evidence'
        when s.sales_match_count = 1 and s.best_match_rank = 6 then 'medium_phone'
        when s.sales_match_count = 1 and s.best_match_rank = 7 then 'medium_email'
        when s.sales_match_count = 1 and s.best_match_rank = 8 then 'low_address'
        when s.sales_match_count > 1 and s.best_match_rank < 9 then 'ambiguous_sales'
        when coalesce(p.payment_link_match_count, 0) > 0 then 'payment_link_only'
        else 'unmatched'
    end as match_status
from keys k
left join sales_summary s using (calendar_event_row)
left join payment_link_matches p using (calendar_event_row)
left join warranty_summary w using (calendar_event_row)
left join {{ ref('calendar_events') }} ce using (calendar_event_row)
