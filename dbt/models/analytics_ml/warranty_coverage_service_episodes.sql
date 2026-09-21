{{ config(schema='analytics_ml', tags=['analytics_ml'], materialized='table') }}
-- One row per mature residential 4x/6x/12x service interval.
-- Coverage begins at service 1, continues between services, and ends 30 days
-- after the final service. Multiple recorded warranty signals are retained.
with observation as (
    select least(max(event_date_local), current_date('Asia/Kuala_Lumpur'))
        as observed_through
    from {{ ref('calendar_service_event_facts') }}
), eligible_packages as (
    select *
    from {{ ref('sales_package_facts') }}
    where premise_type = 'RESIDENTIAL'
      and package_sessions_recorded in (4, 6, 12)
      and warranty_policy_eligible
), service_candidates as (
    select
        f.*,
        p.package_sessions_recorded,
        p.closed_date,
        p.pest_type_raw,
        p.package_type_raw,
        p.sale_total_rm,
        row_number() over (
            partition by f.sales_record_id, f.session_current
            order by f.event_date_local, f.event_start_ts, f.calendar_event_row
        ) as session_anchor_order,
        count(*) over (
            partition by f.sales_record_id, f.session_current
        ) as session_anchor_count
    from {{ ref('calendar_service_event_facts') }} f
    join eligible_packages p using (sales_record_id)
    where not f.warranty_claim_candidate
      and f.session_current between 1 and p.package_sessions_recorded
      and (f.session_total is null
           or f.session_total = p.package_sessions_recorded)
), service_anchors as (
    select
        *,
        lead(event_date_local) over (
            partition by sales_record_id order by session_current
        ) as next_service_date,
        lag(event_date_local) over (
            partition by sales_record_id order by session_current
        ) as previous_service_date,
        count(*) over (partition by sales_record_id) as recorded_anchor_count,
        min(session_current) over (partition by sales_record_id)
            as first_recorded_session,
        max(session_current) over (partition by sales_record_id)
            as last_recorded_session
    from service_candidates
    where session_anchor_order = 1
), intervals as (
    select
        a.*,
        a.event_date_local as coverage_interval_start,
        case
            when a.session_current = a.package_sessions_recorded
                then date_add(a.event_date_local, interval 30 day)
            when a.next_service_date is not null
                then date_sub(a.next_service_date, interval 1 day)
        end as coverage_interval_end,
        o.observed_through
    from service_anchors a
    cross join observation o
), labelled as (
    select
        i.sales_record_id,
        i.calendar_event_row as service_anchor_event_row,
        i.session_current as service_number,
        i.package_sessions_recorded,
        i.closed_date,
        i.event_date_local as service_date,
        i.previous_service_date,
        i.next_service_date,
        i.coverage_interval_start,
        i.coverage_interval_end,
        date_diff(i.coverage_interval_end, i.coverage_interval_start, day) + 1
            as exposure_days,
        i.observed_through,
        i.recorded_anchor_count,
        i.first_recorded_session,
        i.last_recorded_session,
        i.session_anchor_count,
        coalesce(nullif(trim(i.pest_type_raw), ''), 'UNKNOWN') as pest_category,
        coalesce(nullif(trim(i.package_type_raw), ''), 'UNKNOWN')
            as package_category,
        i.sale_total_rm,
        i.calendar_name as assigned_team_calendar,
        i.calendar_pest_text_category,
        i.calendar_service_method_category,
        st_geohash(i.service_geography, 5) as area_cell,
        i.latitude,
        i.longitude,
        i.location_uncertainty_radius_m,
        i.complete_prior_14d_weather,
        i.prior_3d_precipitation_mm,
        i.prior_7d_precipitation_mm,
        i.prior_14d_precipitation_mm,
        i.prior_7d_relative_humidity_mean_pct,
        i.prior_7d_soil_moisture_0_to_7cm_mean,
        hot.hotosm_nearest_waterway_m,
        hot.hotosm_water_features_500m,
        hot.hotosm_water_features_1km,
        hot.hotosm_water_features_2km,
        hot.hotosm_nearest_drainage_m,
        hot.hotosm_nearest_flowing_water_m,
        hot.hotosm_nearest_standing_water_m,
        hot.hotosm_drainage_features_2km,
        hot.hotosm_flowing_water_features_2km,
        hot.hotosm_standing_water_features_2km,
        countif(w.warranty_claim_candidate) as warranty_claim_count_in_interval,
        countif(w.warranty_claim_candidate) > 0 as any_warranty_claim_in_interval,
        count(distinct if(w.warranty_claim_candidate,
            w.event_date_local, null)) as warranty_claim_days_in_interval
    from intervals i
    left join {{ ref('calendar_service_event_facts') }} w
      on w.sales_record_id = i.sales_record_id
     and w.warranty_claim_candidate
     and w.event_date_local between i.coverage_interval_start
                              and i.coverage_interval_end
    left join {{ source('quality', 'hotosm_waterway_context_by_location') }} hot
      on hot.latitude = round(i.latitude, 5)
     and hot.longitude = round(i.longitude, 5)
    where i.coverage_interval_end is not null
      and i.coverage_interval_end <= i.observed_through
      and i.coverage_interval_end >= i.coverage_interval_start
      and i.coverage_interval_start >= i.closed_date
    group by all
)
select
    *,
    case when service_date < date '2026-01-01'
        then 'train_2024_2025' else 'holdout_2026' end as evaluation_split,
    'residential_4x_6x_12x_service_interval_claim_count' as target_definition,
    'after_each_recorded_base_service' as prediction_time_definition,
    'calendar_warranty_signal_not_confirmed_biological_recurrence'
        as label_evidence
from labelled
