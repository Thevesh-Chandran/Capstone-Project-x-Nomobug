{{ config(tags=['analytics_ml']) }}
with enriched as (
    select * from {{ ref('warranty_callback_flood_dataset') }}
), base as (
    select * from {{ ref('warranty_callback_fixed_horizon_dataset') }}
), failures as (
    select e.anchor_event_row, 'changed_or_missing_anchor' as failure
    from base b full outer join enriched e using (anchor_event_row)
    where b.anchor_event_row is null or e.anchor_event_row is null
       or to_json_string(b) is distinct from to_json_string((select as struct e.* except (
            flood_anchor_id,
            gfm_prior_7d_max_flood_fraction_1km,
            gfm_prior_14d_max_flood_fraction_1km,
            gfm_prior_30d_max_flood_fraction_1km,
            gfm_prior_30d_observed_days,
            gfm_prior_30d_flood_detected_days,
            gfm_days_since_detected_flood_capped_30d,
            gfm_days_since_valid_observation,
            gfm_prior_30d_max_valid_fraction_1km,
            gfm_last_observation_at,
            gfm_last_available_at,
            gfm_source_catalogue_sha256,
            gfm_fetched_at,
            gfm_status,
            gdacs_prior_7d_reported_events,
            gdacs_prior_14d_reported_events,
            gdacs_prior_30d_reported_events,
            gdacs_days_since_reported_event_capped_30d,
            gdacs_last_report_available_at,
            gdacs_last_report_event_at,
            gdacs_source_sha256,
            gdacs_fetched_at,
            gdacs_status)))
    union all
    select anchor_event_row, 'missing_anchor_context'
    from enriched
    where gfm_status = 'missing_anchor_context'
       or gfm_source_catalogue_sha256 is null
       or gfm_fetched_at is null
       or gdacs_status = 'missing_anchor_context'
       or gdacs_source_sha256 is null
       or gdacs_fetched_at is null
    union all
    select anchor_event_row, 'invalid_observation_counts'
    from enriched
    where gfm_prior_30d_observed_days not between 0 and 30
       or gfm_prior_30d_flood_detected_days not between 0 and gfm_prior_30d_observed_days
       or (gfm_days_since_detected_flood_capped_30d is not null
           and gfm_days_since_detected_flood_capped_30d not between 0 and 30)
       or (gfm_days_since_valid_observation is not null
           and gfm_days_since_valid_observation not between 1 and 30)
    union all
    select anchor_event_row, 'unobserved_location_encoded_as_dry'
    from enriched
    where gfm_prior_30d_observed_days = 0 and (
        gfm_prior_7d_max_flood_fraction_1km is not null
        or gfm_prior_14d_max_flood_fraction_1km is not null
        or gfm_prior_30d_max_flood_fraction_1km is not null
        or gfm_prior_30d_max_valid_fraction_1km is not null
        or gfm_last_observation_at is not null
        or gfm_last_available_at is not null
        or gfm_days_since_detected_flood_capped_30d is not null
        or gfm_days_since_valid_observation is not null)
    union all
    select anchor_event_row, 'observed_location_missing_validity'
    from enriched
    where gfm_prior_30d_observed_days > 0 and (
        gfm_prior_30d_max_flood_fraction_1km is null
        or gfm_prior_30d_max_valid_fraction_1km is null
        or gfm_prior_30d_max_valid_fraction_1km < 0.5
        or gfm_last_observation_at is null
        or gfm_last_available_at is null
        or gfm_days_since_valid_observation is null)
    union all
    select anchor_event_row, 'future_observation_or_publication'
    from enriched
    where gfm_last_observation_at >= timestamp(anchor_date, 'Asia/Kuala_Lumpur')
       or gfm_last_available_at >= timestamp(anchor_date, 'Asia/Kuala_Lumpur')
       or gfm_last_observation_at < timestamp(date_sub(anchor_date, interval 30 day), 'Asia/Kuala_Lumpur')
    union all
    select anchor_event_row, 'invalid_fraction'
    from enriched,
    unnest([gfm_prior_7d_max_flood_fraction_1km,
            gfm_prior_14d_max_flood_fraction_1km,
            gfm_prior_30d_max_flood_fraction_1km,
            gfm_prior_30d_max_valid_fraction_1km]) as fraction
    where fraction is not null and (is_nan(fraction) or is_inf(fraction)
        or fraction < 0 or fraction > 1)
    union all
    select anchor_event_row, 'flood_detection_inconsistent'
    from enriched
    where gfm_prior_30d_flood_detected_days > 0 and (
        gfm_prior_30d_max_flood_fraction_1km <= 0
        or gfm_days_since_detected_flood_capped_30d is null)
    union all
    select anchor_event_row, 'inconsistent_nested_windows'
    from enriched
    where gfm_prior_7d_max_flood_fraction_1km > gfm_prior_14d_max_flood_fraction_1km
       or gfm_prior_14d_max_flood_fraction_1km > gfm_prior_30d_max_flood_fraction_1km
       or (gfm_prior_7d_max_flood_fraction_1km is not null
           and gfm_prior_14d_max_flood_fraction_1km is null)
    union all
    select anchor_event_row, 'inconsistent_gdacs_windows'
    from enriched
    where gdacs_prior_7d_reported_events < 0
       or gdacs_prior_14d_reported_events < gdacs_prior_7d_reported_events
       or gdacs_prior_30d_reported_events < gdacs_prior_14d_reported_events
       or ((gdacs_prior_7d_reported_events is null) != (gdacs_prior_14d_reported_events is null))
       or ((gdacs_prior_14d_reported_events is null) != (gdacs_prior_30d_reported_events is null))
       or (gdacs_days_since_reported_event_capped_30d is not null
           and gdacs_days_since_reported_event_capped_30d not between 0 and 30)
    union all
    select anchor_event_row, 'future_gdacs_report_or_event'
    from enriched
    where gdacs_last_report_available_at >= timestamp(anchor_date, 'Asia/Kuala_Lumpur')
       or gdacs_last_report_event_at >= timestamp(anchor_date, 'Asia/Kuala_Lumpur')
    union all
    select anchor_event_row, 'missing_gdacs_report_provenance'
    from enriched
    where gdacs_prior_30d_reported_events > 0 and (
        gdacs_last_report_available_at is null
        or gdacs_last_report_event_at is null
        or gdacs_days_since_reported_event_capped_30d is null)
    union all
    select anchor_event_row, 'unknown_gdacs_coverage_has_report_values'
    from enriched
    where gdacs_prior_30d_reported_events is null and (
        gdacs_days_since_reported_event_capped_30d is not null
        or gdacs_last_report_available_at is not null
        or gdacs_last_report_event_at is not null)
    union all
    select anchor_event_row, 'inconsistent_gdacs_status'
    from enriched
    where (starts_with(gdacs_status, 'unknown_')
           and gdacs_prior_30d_reported_events is not null)
       or (not starts_with(gdacs_status, 'unknown_')
           and gdacs_prior_30d_reported_events is null)
       or (gdacs_status = 'reported_region_match'
           and gdacs_prior_30d_reported_events = 0)
       or (gdacs_status = 'no_matching_recorded_report'
           and (gdacs_prior_30d_reported_events != 0
                or gdacs_days_since_reported_event_capped_30d is distinct from 30))
)
select * from failures
