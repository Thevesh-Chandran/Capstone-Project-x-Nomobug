{{ config(tags=['operational']) }}
select payment_record_id from {{ ref('payment_sales_links') }}
group by payment_record_id, sales_record_id having count(*) != 1
union all
select l.payment_record_id from {{ ref('payment_sales_links') }} l
left join {{ ref('payments') }} p using (payment_record_id)
where p.payment_record_id is null or l.allocated_amount_rm is not null
union all
select p.payment_record_id from {{ ref('payments') }} p
where (select count(*) from {{ ref('payment_sales_links') }} l where l.payment_record_id = p.payment_record_id)
    != (select count(distinct id) from unnest(p.sales_references) id)
