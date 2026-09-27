{{ config(schema='analytics_ml', tags=['analytics_ml'], materialized='table') }}
-- Leakage-safe experiment cohort, not a production risk score.
-- Prediction time is immediately after the recorded 3/3 Calendar event.
-- Selected outcome is a later recorded Calendar warranty signal within 30 days.
-- Only warranty-eligible residential 3x packages are included.
-- It does not prove completed treatments or biological pest recurrence.
with observation as (
    select least(max(event_date_local), current_date('Asia/Kuala_Lumpur'))
        as observed_through
    from {{ ref('calendar_service_event_facts') }}
), completion_candidates as (
    select
        sales_record_id,
        calendar_event_row,
        event_date_local as prediction_anchor_date,
        event_start_ts,
        event_end_ts,
        is_all_day,
        event_created_ts,
        event_updated_ts,
        recurring_event_id,
        calendar_pest_text_category,
        calendar_service_method_category,
        calendar_name as assigned_team_calendar,
        address_hash,
        f.latitude,
        f.longitude,
        st_geohash(service_geography, 5) as area_cell,
        coalesce(f.event_day_weather_available, false) as local_weather_available,
        coalesce(f.event_day_weather_available, rw.weather_date is not null)
            as event_day_weather_available,
        coalesce(f.complete_prior_14d_weather, rw.complete_prior_14d_weather, false)
            as complete_prior_14d_weather,
        coalesce(f.event_day_temperature_mean_c, rw.event_day_temperature_mean_c)
            as event_day_temperature_mean_c,
        coalesce(f.event_day_precipitation_mm, rw.event_day_precipitation_mm)
            as event_day_precipitation_mm,
        coalesce(f.event_day_relative_humidity_mean_pct,
            rw.event_day_relative_humidity_mean_pct) as event_day_relative_humidity_mean_pct,
        coalesce(f.event_day_soil_moisture_0_to_7cm_mean,
            rw.event_day_soil_moisture_0_to_7cm_mean)
            as event_day_soil_moisture_0_to_7cm_mean,
        coalesce(f.prior_3d_precipitation_mm, rw.prior_3d_precipitation_mm)
            as prior_3d_precipitation_mm,
        coalesce(f.prior_7d_precipitation_mm, rw.prior_7d_precipitation_mm)
            as prior_7d_precipitation_mm,
        coalesce(f.prior_14d_precipitation_mm, rw.prior_14d_precipitation_mm)
            as prior_14d_precipitation_mm,
        coalesce(f.prior_7d_relative_humidity_mean_pct,
            rw.prior_7d_relative_humidity_mean_pct)
            as prior_7d_relative_humidity_mean_pct,
        coalesce(f.prior_7d_soil_moisture_0_to_7cm_mean,
            rw.prior_7d_soil_moisture_0_to_7cm_mean)
            as prior_7d_soil_moisture_0_to_7cm_mean,
        case
            when f.event_day_weather_available then 'local_0_1_degree_grid'
            when rw.weather_date is not null then 'service_region_daily_mean_fallback'
            else 'unavailable'
        end as weather_feature_scope,
        row_number() over (
            partition by sales_record_id
            order by event_date_local, event_start_ts, calendar_event_row
        ) as anchor_order,
        count(*) over (partition by sales_record_id) as completion_anchor_count
    from {{ ref('calendar_service_event_facts') }} f
    left join {{ ref('regional_weather_features_by_date') }} rw
      on rw.weather_date = f.event_date_local
    where sales_record_id is not null
      and not warranty_claim_candidate
      and session_current = 3
      and session_total = 3
), base_service_sequence as (
    select sales_record_id,
        min(event_date_local) as first_base_service_date,
        min(if(session_current = 1, event_date_local, null)) as session_1_date,
        min(if(session_current = 2, event_date_local, null)) as session_2_date,
        any_value(if(session_current = 1, calendar_name, null))
            as session_1_team,
        any_value(if(session_current = 2, calendar_name, null))
            as session_2_team,
        any_value(if(session_current = 3, calendar_name, null))
            as session_3_team,
        count(distinct if(session_current between 1 and 3, calendar_name, null))
            as distinct_teams_first_three_sessions
    from {{ ref('calendar_service_event_facts') }} sequence_event
    where sales_record_id is not null and not warranty_claim_candidate
      and event_date_local <= (
          select min(c.prediction_anchor_date) from completion_candidates c
          where c.sales_record_id = sequence_event.sales_record_id
      )
    group by sales_record_id
), package_history as (
    select c.calendar_event_row,
        countif(e.event_date_local < c.prediction_anchor_date
            and not e.warranty_claim_candidate) as prior_package_service_events,
        countif(e.event_date_local < c.prediction_anchor_date
            and e.warranty_claim_candidate) as prior_package_warranty_signals
    from completion_candidates c
    left join {{ ref('calendar_service_event_facts') }} e
      on e.sales_record_id = c.sales_record_id
    group by c.calendar_event_row
), property_history as (
    select c.calendar_event_row,
        countif(e.event_date_local < c.prediction_anchor_date
            and not e.warranty_claim_candidate) as prior_property_service_events,
        countif(e.event_date_local < c.prediction_anchor_date
            and e.warranty_claim_candidate) as prior_property_warranty_signals,
        count(distinct if(e.event_date_local < c.prediction_anchor_date,
            e.sales_record_id, null)) as prior_property_distinct_packages,
        countif(e.event_date_local >= date_sub(c.prediction_anchor_date, interval 90 day)
            and e.event_date_local < c.prediction_anchor_date
            and not e.warranty_claim_candidate) as prior_property_service_events_90d,
        countif(e.event_date_local >= date_sub(c.prediction_anchor_date, interval 90 day)
            and e.event_date_local < c.prediction_anchor_date
            and e.warranty_claim_candidate) as prior_property_warranty_signals_90d,
        date_diff(c.prediction_anchor_date,
            min(if(e.event_date_local < c.prediction_anchor_date,
                e.event_date_local, null)), day) as prior_property_observed_days,
        date_diff(c.prediction_anchor_date,
            max(if(e.event_date_local < c.prediction_anchor_date,
                e.event_date_local, null)), day) as days_since_prior_property_event,
        date_diff(c.prediction_anchor_date,
            max(if(e.event_date_local < c.prediction_anchor_date
                and e.warranty_claim_candidate, e.event_date_local, null)), day)
            as days_since_prior_property_warranty_signal
    from completion_candidates c
    left join {{ ref('calendar_service_event_facts') }} e
      on c.address_hash is not null and e.address_hash = c.address_hash
    group by c.calendar_event_row, c.prediction_anchor_date
), team_history as (
    select c.calendar_event_row,
        countif(e.event_date_local < c.prediction_anchor_date)
            as prior_team_service_events,
        countif(e.event_date_local < c.prediction_anchor_date
            and e.warranty_claim_candidate) as prior_team_warranty_signals
    from completion_candidates c
    left join {{ ref('calendar_service_event_facts') }} e
      on e.calendar_name = c.assigned_team_calendar
    group by c.calendar_event_row
), area_history as (
    select c.calendar_event_row,
        countif(e.event_date_local < c.prediction_anchor_date)
            as prior_area_service_events,
        countif(e.event_date_local < c.prediction_anchor_date
            and e.warranty_claim_candidate) as prior_area_warranty_signals
    from completion_candidates c
    left join {{ ref('calendar_service_event_facts') }} e
      on c.area_cell is not null
     and st_geohash(e.service_geography, 5) = c.area_cell
    group by c.calendar_event_row
), daily_team_workload as (
    select c.calendar_event_row,
        countif(e.event_date_local = c.prediction_anchor_date)
            as team_events_on_anchor_day,
        countif(e.event_start_ts < c.event_start_ts
            and e.event_start_ts >= timestamp_sub(c.event_start_ts, interval 7 day))
            as team_events_prior_7d,
        countif(e.event_date_local = c.prediction_anchor_date
            and e.event_start_ts < c.event_start_ts) as team_events_before_anchor_same_day,
        sum(if(e.event_start_ts < c.event_start_ts
            and e.event_start_ts >= timestamp_sub(c.event_start_ts, interval 7 day)
            and not e.is_all_day,
            greatest(timestamp_diff(e.event_end_ts, e.event_start_ts, minute), 0), 0))
            as team_scheduled_minutes_prior_7d
    from completion_candidates c
    left join {{ ref('calendar_service_event_facts') }} e
      on e.calendar_name = c.assigned_team_calendar
     and e.event_date_local between date_sub(c.prediction_anchor_date, interval 7 day)
                                and c.prediction_anchor_date
     and e.event_created_ts <= c.event_start_ts
    group by c.calendar_event_row
), payment_entries as (
    select sale_id as sales_record_id, f.payment_date, f.amount_rm
    from {{ ref('payments') }} p
    cross join unnest(p.sales_references) as sale_id
    join {{ ref('payment_record_facts') }} f using (payment_record_id)
    where f.referenced_sale_count = 1
      and not f.payment_date_needs_review
      and not f.amount_needs_review
), payment_history as (
    select c.calendar_event_row,
        countif(p.payment_date <= c.prediction_anchor_date) as prior_payment_count,
        sum(if(p.payment_date <= c.prediction_anchor_date, p.amount_rm, 0))
            as prior_payment_amount_rm,
        date_diff(c.prediction_anchor_date,
            max(if(p.payment_date <= c.prediction_anchor_date, p.payment_date, null)), day)
            as days_since_last_payment
    from completion_candidates c
    left join payment_entries p using (sales_record_id)
    group by c.calendar_event_row, c.prediction_anchor_date
), pest_premise_history as (
    select c.calendar_event_row,
        countif(not e.warranty_claim_candidate) as prior_pest_premise_service_events,
        countif(e.warranty_claim_candidate) as prior_pest_premise_warranty_signals,
        countif(not e.warranty_claim_candidate
            and e.event_date_local >= date_sub(c.prediction_anchor_date, interval 90 day))
            as prior_pest_premise_service_events_90d,
        countif(e.warranty_claim_candidate
            and e.event_date_local >= date_sub(c.prediction_anchor_date, interval 90 day))
            as prior_pest_premise_warranty_signals_90d
    from completion_candidates c
    join {{ ref('sales_package_facts') }} current_package
      on current_package.sales_record_id = c.sales_record_id
    left join {{ ref('calendar_service_event_facts') }} e
      on e.event_date_local < c.prediction_anchor_date
    left join {{ ref('sales_package_facts') }} historical_package
      on historical_package.sales_record_id = e.sales_record_id
     and coalesce(nullif(trim(historical_package.pest_type_raw), ''), 'UNKNOWN')
         = coalesce(nullif(trim(current_package.pest_type_raw), ''), 'UNKNOWN')
     and historical_package.premise_type = current_package.premise_type
    where historical_package.sales_record_id is not null
    group by c.calendar_event_row
), warranty_outcomes as (
    select sales_record_id, array_agg(event_date_local order by event_date_local)
        as warranty_dates
    from {{ ref('calendar_service_event_facts') }}
    where sales_record_id is not null and warranty_claim_candidate
    group by sales_record_id
), eligible as (
    select
        p.sales_record_id,
        c.address_hash,
        p.closed_date,
        c.calendar_event_row as prediction_anchor_event_row,
        c.prediction_anchor_date,
        date_add(c.prediction_anchor_date, interval 30 day) as outcome_window_end_date,
        o.observed_through,
        extract(year from c.prediction_anchor_date) as anchor_year,
        extract(month from c.prediction_anchor_date) as anchor_month,
        extract(dayofweek from c.prediction_anchor_date) as anchor_day_of_week,
        extract(hour from c.event_start_ts at time zone 'Asia/Kuala_Lumpur')
            as anchor_hour_local,
        extract(dayofweek from c.prediction_anchor_date) in (1, 7) as anchor_is_weekend,
        case
            when extract(hour from c.event_start_ts at time zone 'Asia/Kuala_Lumpur') < 12
                then 'MORNING'
            when extract(hour from c.event_start_ts at time zone 'Asia/Kuala_Lumpur') < 17
                then 'AFTERNOON'
            else 'EVENING'
        end as appointment_daypart,
        timestamp_diff(c.event_start_ts, c.event_created_ts, hour)
            as booking_lead_hours,
        case when c.event_updated_ts <= c.event_start_ts then
            timestamp_diff(c.event_start_ts, c.event_updated_ts, hour)
        end as last_pre_service_edit_lead_hours,
        c.event_updated_ts <= c.event_start_ts
            and timestamp_diff(c.event_start_ts, c.event_updated_ts, hour) between 0 and 24
            as edited_within_24h_before_service,
        c.recurring_event_id is not null as recurring_calendar_event,
        if(c.is_all_day, null,
            timestamp_diff(c.event_end_ts, c.event_start_ts, minute))
            as scheduled_duration_minutes,
        date_diff(c.prediction_anchor_date, p.closed_date, day)
            as days_sale_to_completion,
        date_diff(c.prediction_anchor_date, f.first_base_service_date, day)
            as days_first_to_completion,
        date_diff(f.session_2_date, f.session_1_date, day) as days_session_1_to_2,
        date_diff(c.prediction_anchor_date, f.session_2_date, day) as days_session_2_to_3,
        abs(date_diff(f.session_2_date, f.session_1_date, day)
            - date_diff(c.prediction_anchor_date, f.session_2_date, day))
            as session_interval_difference_days,
        f.distinct_teams_first_three_sessions,
        f.session_1_team != f.session_2_team as team_changed_session_1_to_2,
        f.session_2_team != f.session_3_team as team_changed_session_2_to_3,
        p.sale_total_rm,
        p.sale_total_rm is null as sale_total_missing,
        coalesce(p.recorded_returning_client, false) as recorded_returning_client,
        coalesce(nullif(trim(p.acquisition_relationship_raw), ''), 'UNKNOWN')
            as acquisition_category,
        coalesce(nullif(trim(p.pest_type_raw), ''), 'UNKNOWN') as pest_category,
        coalesce(nullif(trim(p.package_type_raw), ''), 'UNKNOWN') as package_category,
        coalesce(nullif(trim(p.contract_type_raw), ''), 'UNKNOWN') as contract_category,
        p.premise_type,
        p.package_sessions_recorded,
        p.trbs_status,
        p.billing_arrangement,
        p.sales_pic,
        p.days_first_contact_to_close,
        concat(coalesce(nullif(trim(p.pest_type_raw), ''), 'UNKNOWN'), ' | ',
            p.premise_type) as pest_premise_category,
        concat(case
                when ah.prior_property_service_events = 0 then 'NO_PRIOR'
                when ah.prior_property_service_events = 1 then 'ONE_PRIOR'
                when ah.prior_property_service_events <= 3 then 'TWO_TO_THREE_PRIOR'
                else 'FOUR_PLUS_PRIOR'
            end, ' | ', coalesce(nullif(trim(p.pest_type_raw), ''), 'UNKNOWN'))
            as property_history_pest_category,
        concat(coalesce(nullif(trim(p.pest_type_raw), ''), 'UNKNOWN'), ' | ',
            coalesce(nullif(trim(c.assigned_team_calendar), ''), 'UNKNOWN'))
            as pest_team_category,
        coalesce(nullif(trim(c.assigned_team_calendar), ''), 'UNKNOWN')
            as assigned_team_calendar,
        c.area_cell,
        c.calendar_pest_text_category,
        c.calendar_service_method_category,
        ph.prior_package_service_events,
        ph.prior_package_warranty_signals,
        ah.prior_property_service_events,
        ah.prior_property_warranty_signals,
        ah.prior_property_distinct_packages,
        ah.prior_property_service_events_90d,
        ah.prior_property_warranty_signals_90d,
        safe_divide(90 * ah.prior_property_service_events,
            greatest(ah.prior_property_observed_days, 1))
            as prior_property_service_events_per_90_active_days,
        safe_divide(ah.prior_property_service_events_90d,
            greatest(ah.prior_property_service_events, 1))
            as recent_90d_share_of_prior_property_services,
        ah.days_since_prior_property_event,
        ah.days_since_prior_property_warranty_signal,
        th.prior_team_service_events,
        th.prior_team_warranty_signals,
        safe_divide(th.prior_team_warranty_signals, th.prior_team_service_events)
            as prior_team_warranty_rate,
        safe_divide(th.prior_team_warranty_signals + 2,
            th.prior_team_service_events + 10) as prior_team_warranty_rate_smoothed,
        ar.prior_area_service_events,
        ar.prior_area_warranty_signals,
        safe_divide(ar.prior_area_warranty_signals, ar.prior_area_service_events)
            as prior_area_warranty_rate,
        safe_divide(ar.prior_area_warranty_signals + 2,
            ar.prior_area_service_events + 10) as prior_area_warranty_rate_smoothed,
        dw.team_events_on_anchor_day,
        dw.team_events_prior_7d,
        dw.team_events_before_anchor_same_day,
        dw.team_scheduled_minutes_prior_7d,
        (cast(coalesce(f.session_1_team != f.session_2_team, false) as int64)
            + cast(coalesce(f.session_2_team != f.session_3_team, false) as int64))
            * dw.team_events_prior_7d as workload_team_change_interaction,
        pph.prior_pest_premise_service_events,
        pph.prior_pest_premise_warranty_signals,
        safe_divide(pph.prior_pest_premise_warranty_signals,
            pph.prior_pest_premise_service_events) as prior_pest_premise_warranty_rate,
        safe_divide(pph.prior_pest_premise_warranty_signals + 2,
            pph.prior_pest_premise_service_events + 10)
            as prior_pest_premise_warranty_rate_smoothed,
        pph.prior_pest_premise_service_events_90d,
        pph.prior_pest_premise_warranty_signals_90d,
        safe_divide(pph.prior_pest_premise_warranty_signals_90d,
            pph.prior_pest_premise_service_events_90d)
            as prior_pest_premise_warranty_rate_90d,
        safe_divide(pph.prior_pest_premise_warranty_signals_90d + 2,
            pph.prior_pest_premise_service_events_90d + 10)
            as prior_pest_premise_warranty_rate_90d_smoothed,
        pay.prior_payment_count,
        pay.prior_payment_amount_rm,
        safe_divide(pay.prior_payment_amount_rm, p.sale_total_rm)
            as prior_payment_to_sale_ratio,
        pay.days_since_last_payment,
        c.event_day_weather_available,
        c.local_weather_available,
        c.complete_prior_14d_weather,
        c.weather_feature_scope,
        c.event_day_temperature_mean_c,
        c.event_day_precipitation_mm,
        c.event_day_relative_humidity_mean_pct,
        c.event_day_soil_moisture_0_to_7cm_mean,
        c.prior_3d_precipitation_mm,
        c.prior_7d_precipitation_mm,
        c.prior_14d_precipitation_mm,
        c.prior_7d_relative_humidity_mean_pct,
        c.prior_7d_soil_moisture_0_to_7cm_mean,
        c.prior_7d_precipitation_mm * c.prior_7d_relative_humidity_mean_pct
            as rain_humidity_7d_interaction,
        c.prior_14d_precipitation_mm * c.prior_7d_soil_moisture_0_to_7cm_mean
            as rain_soil_moisture_interaction,
        concat(coalesce(nullif(trim(p.pest_type_raw), ''), 'UNKNOWN'), ' | ',
            case
                when c.prior_7d_precipitation_mm >= 50 then 'VERY_WET'
                when c.prior_7d_precipitation_mm >= 20 then 'WET'
                when c.prior_7d_precipitation_mm > 0 then 'SOME_RAIN'
                else 'DRY'
            end) as pest_rain_band_category,
        concat(c.calendar_service_method_category, ' | ',
            case
                when c.prior_7d_relative_humidity_mean_pct >= 85 then 'VERY_HUMID'
                when c.prior_7d_relative_humidity_mean_pct >= 75 then 'HUMID'
                else 'LOWER_HUMIDITY'
            end) as method_humidity_band_category,
        env.elevation_m,
        env.local_relief_500m_m,
        env.nearest_mapped_water_m,
        env.mapped_water_features_2km,
        env.nearest_mapped_water_m is not null as mapped_water_within_2km,
        env.nearest_mapped_forest_m,
        env.mapped_forest_features_2km,
        env.nearest_mapped_forest_m is not null as mapped_forest_within_2km,
        env.places_result_capped as environmental_places_result_capped,
        env.location_id is not null as environmental_context_available,
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
        hot.location_id is not null as hotosm_waterway_context_available,
        exists(
            select 1 from unnest(coalesce(w.warranty_dates, [])) warranty_date
            where warranty_date > c.prediction_anchor_date
              and warranty_date <= date_add(c.prediction_anchor_date, interval 30 day)
        ) as warranty_signal_within_30d,
        exists(
            select 1 from unnest(coalesce(w.warranty_dates, [])) warranty_date
            where warranty_date > c.prediction_anchor_date
              and warranty_date <= date_add(c.prediction_anchor_date, interval 14 day)
        ) as warranty_signal_within_14d,
        if(date_add(c.prediction_anchor_date, interval 60 day) <= o.observed_through,
            exists(
                select 1 from unnest(coalesce(w.warranty_dates, [])) warranty_date
                where warranty_date > c.prediction_anchor_date
                  and warranty_date <= date_add(c.prediction_anchor_date, interval 60 day)
            ), null) as warranty_signal_within_60d,
        if(date_add(c.prediction_anchor_date, interval 90 day) <= o.observed_through,
            exists(
                select 1 from unnest(coalesce(w.warranty_dates, [])) warranty_date
                where warranty_date > c.prediction_anchor_date
                  and warranty_date <= date_add(c.prediction_anchor_date, interval 90 day)
            ), null) as warranty_signal_within_90d,
        c.completion_anchor_count
    from {{ ref('sales_package_facts') }} p
    join completion_candidates c
      on p.sales_record_id = c.sales_record_id and c.anchor_order = 1
    join base_service_sequence f on p.sales_record_id = f.sales_record_id
    left join package_history ph on c.calendar_event_row = ph.calendar_event_row
    left join property_history ah on c.calendar_event_row = ah.calendar_event_row
    left join team_history th on c.calendar_event_row = th.calendar_event_row
    left join area_history ar on c.calendar_event_row = ar.calendar_event_row
    left join daily_team_workload dw on c.calendar_event_row = dw.calendar_event_row
    left join payment_history pay on c.calendar_event_row = pay.calendar_event_row
    left join pest_premise_history pph on c.calendar_event_row = pph.calendar_event_row
    left join warranty_outcomes w on p.sales_record_id = w.sales_record_id
    left join {{ source('quality', 'environmental_context_by_location') }} env
      on env.latitude = round(c.latitude, 5)
     and env.longitude = round(c.longitude, 5)
    left join {{ source('quality', 'hotosm_waterway_context_by_location') }} hot
      on hot.latitude = round(c.latitude, 5)
     and hot.longitude = round(c.longitude, 5)
    cross join observation o
    where p.include_in_sale_count
      and p.package_sessions_recorded = 3
      and p.warranty_policy_eligible
      and p.premise_type = 'RESIDENTIAL'
      and p.closed_date is not null
      and c.prediction_anchor_date >= p.closed_date
      and c.completion_anchor_count = 1
      and date_add(c.prediction_anchor_date, interval 30 day) <= o.observed_through
      and not exists (
          select 1 from {{ ref('calendar_events') }} reviewed_event
          join {{ ref('calendar_event_matches') }} reviewed_match using (calendar_event_row)
          where reviewed_event.warranty_label_uncertain
            and reviewed_match.matched_sales_record_id = p.sales_record_id
      )
)
select
    *,
    case
        when prediction_anchor_date < date '2026-01-01' then 'train_2024_2025'
        else 'holdout_2026'
    end as evaluation_split,
    'eligible_residential_3x_recorded_calendar_warranty_signal_within_30d_after_3_of_3'
        as target_definition,
    'after_recorded_3_of_3_event' as prediction_time_definition,
    'scheduled_or_recorded_calendar_signal_not_completed_treatment_or_pest_recurrence_proof'
        as label_evidence
from eligible
