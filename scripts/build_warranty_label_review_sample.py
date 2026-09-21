"""Create a privacy-reduced, stratified warranty-label review sample."""

import json
from pathlib import Path

from google.cloud import bigquery

PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tmp" / "warranty_label_review_rows.json"

SQL = r"""
with service_bounds as (
    select sales_record_id,
        min(if(not warranty_claim_candidate and session_current = 1,
            event_date_local, null)) as first_service_date,
        min(if(not warranty_claim_candidate
            and session_current = p.package_sessions_recorded,
            event_date_local, null)) as final_service_date
    from `profound-keel-500007-s4.gold.calendar_service_event_facts` e
    join `profound-keel-500007-s4.gold.sales_package_facts` p
      using (sales_record_id)
    group by sales_record_id
), universe as (
    select
        e.calendar_event_row,
        e.event_id,
        e.calendar_name,
        e.event_date_local,
        extract(year from e.event_date_local) as event_year,
        e.event_category,
        e.warranty_claim_candidate as system_label,
        coalesce(e.warranty_claim_reason, 'none') as detection_reason,
        e.session_current,
        e.session_total,
        e.sequence_over_package,
        e.recurring_event_id is not null as recurring_event,
        m.matched_sales_record_id as sales_record_id,
        m.match_status,
        p.premise_type,
        p.package_sessions_recorded,
        p.warranty_policy_category,
        p.warranty_policy_rule,
        p.pest_type_raw as sales_pest_type,
        e.calendar_pest_text_category,
        e.calendar_service_method_category,
        b.first_service_date,
        b.final_service_date,
        case
            when p.premise_type = 'COMMERCIAL' then 'INELIGIBLE_COMMERCIAL'
            when p.premise_type = 'RESIDENTIAL' and p.package_sessions_recorded = 1
                then 'INELIGIBLE_RESIDENTIAL_1X'
            when p.premise_type = 'RESIDENTIAL' and p.package_sessions_recorded = 3
                 and b.final_service_date is not null
                 and e.event_date_local > b.final_service_date
                 and e.event_date_local <= date_add(b.final_service_date, interval 30 day)
                then 'WITHIN_3X_POST_FINAL_30D'
            when p.premise_type = 'RESIDENTIAL' and p.package_sessions_recorded = 3
                then 'OUTSIDE_OR_UNRESOLVED_3X_WINDOW'
            when p.premise_type = 'RESIDENTIAL' and p.package_sessions_recorded in (4,6,12)
                 and b.first_service_date is not null
                 and e.event_date_local >= b.first_service_date
                 and (b.final_service_date is null
                      or e.event_date_local <= date_add(b.final_service_date, interval 30 day))
                then 'WITHIN_ACTIVE_MULTI_SERVICE_COVERAGE'
            when p.premise_type = 'RESIDENTIAL' and p.package_sessions_recorded in (4,6,12)
                then 'OUTSIDE_OR_UNRESOLVED_MULTI_SERVICE_WINDOW'
            else 'UNMATCHED_OR_UNDEFINED_POLICY'
        end as policy_window_status,
        array_to_string(regexp_extract_all(upper(coalesce(raw.summary, '')),
            r'WARRANTY|CLAIM|CALLBACK|EXTRA|COMPLIMENTARY|FOLLOW[- ]?UP|RESCHEDULE|POSTPONE|CHECK|REVIEW|CALCULATE|CONVERSION RATE'), ', ')
            as evidence_keywords,
        regexp_contains(upper(coalesce(raw.description, '')),
            r'WARRANTY|CLAIM|CALLBACK') as description_has_warranty_keyword,
        regexp_contains(upper(coalesce(raw.summary, '')),
            r'RESCHEDULE|POSTPONE|CANCEL') as title_has_schedule_change_keyword,
        timestamp_diff(safe_cast(raw.updated_raw as timestamp),
            safe_cast(raw.created_raw as timestamp), hour) as hours_created_to_last_update,
        case
            when e.warranty_claim_candidate and e.warranty_claim_reason = 'explicit_warranty_label'
                then 'POSITIVE_EXPLICIT'
            when e.warranty_claim_candidate and e.warranty_claim_reason = 'post_package_sequence'
                 and p.warranty_policy_eligible then 'POSITIVE_SEQUENCE_ELIGIBLE'
            when e.warranty_claim_candidate and e.warranty_claim_reason = 'post_package_sequence'
                then 'POSITIVE_SEQUENCE_POLICY_REVIEW'
            when not e.warranty_claim_candidate and e.event_category = 'complimentary'
                then 'NEGATIVE_COMPLIMENTARY'
            else 'NEGATIVE_OTHER_MATCHED'
        end as review_stratum
    from `profound-keel-500007-s4.silver.calendar_events` e
    join `profound-keel-500007-s4.bronze.calendar_events_78147d417f3d97d3c1d9ef0be59638fd7850e4195108e1fc7b879483c7f35b66` raw
      using (calendar_event_row)
    left join `profound-keel-500007-s4.silver.calendar_event_matches` m
      using (calendar_event_row)
    left join `profound-keel-500007-s4.gold.sales_package_facts` p
      on p.sales_record_id = m.matched_sales_record_id
    left join service_bounds b on b.sales_record_id = m.matched_sales_record_id
    where e.status = 'confirmed'
      and (e.warranty_claim_candidate
           or e.event_category = 'complimentary'
           or (e.event_category = 'other' and m.matched_sales_record_id is not null))
), ranked as (
    select *, row_number() over (
        partition by review_stratum
        order by farm_fingerprint(concat(cast(calendar_event_row as string),
            '|cp2-warranty-label-review-v1'))
    ) as stratum_rank
    from universe
)
select * except(stratum_rank)
from ranked
where (review_stratum = 'POSITIVE_EXPLICIT' and stratum_rank <= 24)
   or (review_stratum = 'POSITIVE_SEQUENCE_ELIGIBLE' and stratum_rank <= 32)
   or (review_stratum = 'POSITIVE_SEQUENCE_POLICY_REVIEW' and stratum_rank <= 8)
   or (review_stratum = 'NEGATIVE_COMPLIMENTARY' and stratum_rank <= 8)
   or (review_stratum = 'NEGATIVE_OTHER_MATCHED' and stratum_rank <= 8)
order by review_stratum, event_year, package_sessions_recorded, calendar_event_row
"""


def main() -> None:
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    rows = [dict(row) for row in client.query(SQL).result(timeout=300)]
    for index, row in enumerate(rows, start=1):
        row["review_id"] = f"WR-{index:03d}"
        for key, value in list(row.items()):
            if hasattr(value, "isoformat"):
                row[key] = value.isoformat()
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    counts = {}
    for row in rows:
        counts[row["review_stratum"]] = counts.get(row["review_stratum"], 0) + 1
    print(f"WROTE {OUTPUT}: {len(rows)} rows")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
