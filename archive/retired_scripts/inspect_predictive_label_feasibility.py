"""Aggregate-only feasibility audit for leakage-safe warranty outcomes."""

from google.cloud import bigquery


PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
MAX_BYTES = 100 * 1024 * 1024

SQL = r"""
with observation as (
  select least(max(event_date_local), current_date('Asia/Kuala_Lumpur')) as observed_through
  from `profound-keel-500007-s4.gold.calendar_service_event_facts`
), packages as (
  select sales_record_id, closed_date, package_sessions_recorded,
         contract_type_raw, package_type_raw, pest_type_raw,
         sale_total_rm, recorded_returning_client
  from `profound-keel-500007-s4.gold.sales_package_facts`
  where include_in_sale_count
), event_summary as (
  select
    sales_record_id,
    min(if(not warranty_claim_candidate, event_date_local, null)) as first_base_event_date,
    min(if(not warranty_claim_candidate and session_current = session_total,
           event_date_local, null)) as package_completion_anchor,
    countif(not warranty_claim_candidate and session_current = session_total)
      as completion_anchor_event_count,
    array_agg(if(warranty_claim_candidate, event_date_local, null)
              ignore nulls order by event_date_local) as warranty_dates
  from `profound-keel-500007-s4.gold.calendar_service_event_facts`
  where sales_record_id is not null
  group by sales_record_id
), labelled as (
  select
    p.*,
    e.first_base_event_date,
    e.package_completion_anchor,
    e.completion_anchor_event_count,
    o.observed_through,
    case
      when p.package_sessions_recorded = 3 then 'three_session_30d_after_completion'
      when p.package_sessions_recorded >= 6
        or regexp_contains(upper(coalesce(p.contract_type_raw, '')), r'YEAR')
        then 'long_package_365d_after_first_service'
      else 'outside_candidate_definitions'
    end as candidate_definition,
    case
      when p.package_sessions_recorded = 3
        then e.package_completion_anchor
      when p.package_sessions_recorded >= 6
        or regexp_contains(upper(coalesce(p.contract_type_raw, '')), r'YEAR')
        then e.first_base_event_date
    end as prediction_anchor,
    case
      when p.package_sessions_recorded = 3 then 30
      when p.package_sessions_recorded >= 6
        or regexp_contains(upper(coalesce(p.contract_type_raw, '')), r'YEAR')
        then 365
    end as outcome_horizon_days,
    case
      when p.package_sessions_recorded = 3 and e.package_completion_anchor is not null
        then exists(select 1 from unnest(e.warranty_dates) d
                    where d > e.package_completion_anchor
                      and d <= date_add(e.package_completion_anchor, interval 30 day))
      when (p.package_sessions_recorded >= 6
            or regexp_contains(upper(coalesce(p.contract_type_raw, '')), r'YEAR'))
           and e.first_base_event_date is not null
        then exists(select 1 from unnest(e.warranty_dates) d
                    where d > e.first_base_event_date
                      and d <= date_add(e.first_base_event_date, interval 365 day))
    end as outcome_positive
  from packages p
  left join event_summary e using (sales_record_id)
  cross join observation o
), assessed as (
  select *,
    prediction_anchor is not null
      and outcome_horizon_days is not null
      and date_add(prediction_anchor, interval outcome_horizon_days day) <= observed_through
      as label_mature,
    prediction_anchor is not null and closed_date is not null
      and prediction_anchor >= closed_date as anchor_not_before_sale
  from labelled
)
select
  candidate_definition,
  extract(year from prediction_anchor) as anchor_year,
  count(*) as package_rows,
  countif(prediction_anchor is not null) as with_anchor,
  countif(label_mature) as mature_rows,
  countif(label_mature and outcome_positive) as mature_positive_rows,
  countif(label_mature and not outcome_positive) as mature_negative_rows,
  countif(label_mature and not anchor_not_before_sale) as mature_anchor_before_sale_rows,
  countif(completion_anchor_event_count > 1) as multiple_completion_anchor_rows,
  min(prediction_anchor) as earliest_anchor,
  max(prediction_anchor) as latest_anchor,
  any_value(observed_through) as observed_through
from assessed
group by candidate_definition, anchor_year
order by candidate_definition, anchor_year
"""


def main() -> None:
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    dry = client.query(SQL, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False))
    print(f"Estimated bytes: {dry.total_bytes_processed:,}")
    if dry.total_bytes_processed > MAX_BYTES:
        raise SystemExit("Feasibility audit exceeds 100 MiB cap")
    rows = client.query(SQL, job_config=bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES, job_timeout_ms=600000),
        job_retry=None).result(timeout=630)
    print("candidate_definition | anchor_year | packages | anchors | mature | positive | negative | anchor_before_sale | multiple_completion_anchors | anchor_range | observed_through")
    for row in rows:
        print(
            f"{row.candidate_definition} | {row.anchor_year} | {row.package_rows} | "
            f"{row.with_anchor} | {row.mature_rows} | {row.mature_positive_rows} | "
            f"{row.mature_negative_rows} | {row.mature_anchor_before_sale_rows} | "
            f"{row.multiple_completion_anchor_rows} | {row.earliest_anchor}..{row.latest_anchor} | "
            f"{row.observed_through}"
        )


if __name__ == "__main__":
    main()
