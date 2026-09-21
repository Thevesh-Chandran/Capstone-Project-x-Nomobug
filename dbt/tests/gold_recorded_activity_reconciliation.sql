{{ config(tags=['gold']) }}
select 'sales_monthly_grain' as failure
from {{ ref('sales_monthly_recorded') }}
group by snapshot_table, closed_month
having count(*) != 1
union all
select 'payments_monthly_grain'
from {{ ref('payments_monthly_recorded') }}
group by snapshot_table, payment_month
having count(*) != 1
union all
select 'prospects_monthly_grain'
from {{ ref('prospect_reply_monthly_recorded') }}
group by snapshot_id, first_reply_month
having count(*) != 1
union all
select 'sales_rows_not_preserved'
from unnest([1])
where (select sum(package_rows) from {{ ref('sales_monthly_recorded') }}) !=
      (select count(*) from {{ ref('sales_package_facts') }})
union all
select 'sales_countable_mismatch'
from unnest([1])
where (select sum(countable_package_rows) from {{ ref('sales_monthly_recorded') }}) !=
      (select countif(include_in_sale_count and closed_date is not null and
          closed_date <= current_date('Asia/Kuala_Lumpur'))
       from {{ ref('sales_package_facts') }})
union all
select 'sales_value_mismatch'
from unnest([1])
where (select coalesce(sum(recorded_package_face_value_rm), 0)
       from {{ ref('sales_monthly_recorded') }}) !=
      (select coalesce(sum(if(include_in_sale_count and closed_date is not null and
          closed_date <= current_date('Asia/Kuala_Lumpur'), sale_total_rm, null)), 0)
       from {{ ref('sales_package_facts') }})
union all
select 'payment_rows_not_preserved'
from unnest([1])
where (select sum(payment_rows) from {{ ref('payments_monthly_recorded') }}) !=
      (select count(*) from {{ ref('payment_record_facts') }})
union all
select 'payment_value_mismatch'
from unnest([1])
where (select coalesce(sum(recorded_payment_entry_amount_rm), 0)
       from {{ ref('payments_monthly_recorded') }}) !=
      (select coalesce(sum(if(payment_date is not null and
          payment_date <= current_date('Asia/Kuala_Lumpur'), amount_rm, null)), 0)
       from {{ ref('payment_record_facts') }})
union all
select 'prospect_rows_not_preserved'
from unnest([1])
where (select sum(prospect_candidate_rows) from {{ ref('prospect_reply_monthly_recorded') }}) !=
      (select count(*) from {{ ref('prospects_2026') }} where row_class = 'prospect_candidate')
union all
select 'quality_issue_out_of_bounds'
from {{ ref('recorded_activity_quality') }}
where affected_rows < 0 or affected_rows > source_rows
union all
select 'quality_duplicate_issue'
from {{ ref('recorded_activity_quality') }}
group by source_name, issue_code
having count(*) != 1
