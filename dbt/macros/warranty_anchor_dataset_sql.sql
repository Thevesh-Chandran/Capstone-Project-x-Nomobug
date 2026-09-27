{% macro warranty_anchor_dataset_sql(callback=false) %}
-- Fixed, prediction-safe outcome windows. No future appointment date is a feature.
-- The same property/package is kept together during downstream validation.
with observation as (
    {{ calendar_snapshot_observation_sql() }}
), uncertain_packages as (
    select distinct m.matched_sales_record_id as sales_record_id
    from {{ ref('calendar_events') }} e
    join {{ ref('calendar_event_matches') }} m using (calendar_event_row)
    where e.warranty_label_uncertain
), candidates as (
    select f.*, p.package_sessions_recorded, p.closed_date, p.sale_total_rm,
        p.pest_type_raw, p.package_type_raw,
        p.premise_type,
        {% if callback %}
        'matched_packages_recorded_callback_30d' as population,
        {% else %}
        case when p.package_sessions_recorded = 3
            then 'residential_3x_final_30d'
            else 'residential_4x_6x_12x_after_service_30d' end as population,
        {% endif %}
        row_number() over (partition by f.sales_record_id, f.session_current
            order by f.event_date_local, f.event_start_ts, f.calendar_event_row) as anchor_order,
        count(*) over (partition by f.sales_record_id, f.session_current) as anchor_count
    from {{ ref('calendar_service_event_facts') }} f
    join {{ ref('sales_package_facts') }} p using (sales_record_id)
    where p.include_in_sale_count and p.closed_date is not null
      {% if callback %}
      and p.premise_type in ('RESIDENTIAL', 'COMMERCIAL')
      and p.package_sessions_recorded >= 1
      and f.event_category = 'service'
      {% else %}
      and p.premise_type = 'RESIDENTIAL'
      and p.package_sessions_recorded in (3,4,6,12)
      and p.warranty_policy_eligible
      {% endif %}
      and f.event_date_local >= p.closed_date
      and not f.warranty_claim_candidate
      and f.event_category not in ('consultation', 'administrative', 'cancelled')
      and f.session_current between 1 and p.package_sessions_recorded
      and f.session_total = p.package_sessions_recorded
      {% if not callback %}
      and (p.package_sessions_recorded != 3 or f.session_current = 3)
      {% endif %}
      and not exists (select 1 from uncertain_packages u where u.sales_record_id = f.sales_record_id)
), anchors as (
    select c.*, date_add(event_date_local, interval 30 day) as outcome_end_date,
        o.observed_through
    from candidates c cross join observation o
    where anchor_order = 1 and anchor_count = 1
      and date_add(event_date_local, interval 30 day) <= o.observed_through
), history_links as (
    -- Separate equality joins avoid a broad OR join across the full history.
    -- A visit linked by multiple identifiers contributes only once.
    select a.calendar_event_row as anchor_row, h.calendar_event_row as history_row
    from anchors a
    join {{ ref('calendar_service_event_facts') }} h
      on h.sales_record_id = a.sales_record_id
     and h.event_date_local < a.event_date_local
     and {{ calendar_history_available('h', 'a') }}
    union distinct
    select a.calendar_event_row as anchor_row, h.calendar_event_row as history_row
    from anchors a
    join {{ ref('calendar_service_event_facts') }} h
      on a.address_hash is not null and h.address_hash = a.address_hash
     and h.event_date_local < a.event_date_local
     and {{ calendar_history_available('h', 'a') }}
    union distinct
    select a.calendar_event_row as anchor_row, h.calendar_event_row as history_row
    from anchors a
    join {{ ref('calendar_service_event_facts') }} h
      on st_geohash(h.service_geography, 4) = st_geohash(a.service_geography, 4)
     and h.event_date_local >= date_sub(a.event_date_local, interval 90 day)
     and h.event_date_local < a.event_date_local
     and {{ calendar_history_available('h', 'a') }}
), histories as (
    select a.calendar_event_row,
        countif(h.sales_record_id = a.sales_record_id and h.warranty_claim_candidate)
            as prior_package_warranty_claims,
        countif(h.sales_record_id = a.sales_record_id and not h.warranty_claim_candidate)
            as prior_package_service_events,
        countif(a.address_hash is not null and h.address_hash = a.address_hash
            and h.warranty_claim_candidate) as prior_property_warranty_claims,
        countif(a.address_hash is not null and h.address_hash = a.address_hash
            and not h.warranty_claim_candidate) as prior_property_service_events,
        date_diff(a.event_date_local, max(if(h.sales_record_id = a.sales_record_id
            and not h.warranty_claim_candidate, h.event_date_local, null)), day)
            as days_since_previous_service,
        date_diff(a.event_date_local, max(if(a.address_hash is not null
            and h.address_hash = a.address_hash and h.warranty_claim_candidate,
            h.event_date_local, null)), day) as days_since_prior_property_claim,
        countif(a.address_hash is not null and h.address_hash = a.address_hash
            and h.warranty_claim_candidate
            and h.event_date_local >= date_sub(a.event_date_local, interval 90 day))
            as prior_property_claims_90d,
        countif(h.warranty_claim_candidate
            and st_geohash(h.service_geography, 4) = st_geohash(a.service_geography, 4)
            and h.event_date_local >= date_sub(a.event_date_local, interval 90 day))
            as prior_area_claims_90d,
        countif(not h.warranty_claim_candidate
            and st_geohash(h.service_geography, 4) = st_geohash(a.service_geography, 4)
            and h.event_date_local >= date_sub(a.event_date_local, interval 90 day))
            as prior_area_services_90d
    from anchors a
    left join history_links l on l.anchor_row = a.calendar_event_row
    left join {{ ref('calendar_service_event_facts') }} h
      on h.calendar_event_row = l.history_row
    group by a.calendar_event_row, a.event_date_local
), outcomes as (
    select a.calendar_event_row,
        countif(w.warranty_claim_candidate) > 0 as warranty_signal_within_30d,
        countif(w.warranty_claim_candidate) as warranty_claim_count_30d
    from anchors a
    left join {{ ref('calendar_service_event_facts') }} w
      on w.sales_record_id = a.sales_record_id
     and w.event_date_local > a.event_date_local
     and w.event_date_local <= a.outcome_end_date
    group by a.calendar_event_row
)
select a.population, a.sales_record_id, a.address_hash, a.premise_type,
    a.calendar_event_row as anchor_event_row,
    a.event_date_local as anchor_date, a.outcome_end_date, a.observed_through,
    a.session_current as service_number, a.package_sessions_recorded,
    a.sale_total_rm, date_diff(a.event_date_local, a.closed_date, day) as days_sale_to_anchor,
    coalesce(nullif(trim(a.pest_type_raw), ''), 'UNKNOWN') as pest_category,
    coalesce(nullif(trim(a.package_type_raw), ''), 'UNKNOWN') as package_category,
    a.calendar_pest_text_category, a.calendar_service_method_category,
    a.location_uncertainty_radius_m,
    sin(2 * acos(-1) * extract(month from a.event_date_local) / 12) as anchor_month_sin,
    cos(2 * acos(-1) * extract(month from a.event_date_local) / 12) as anchor_month_cos,
    h.* except(calendar_event_row),
    w.warranty_signal_within_30d, w.warranty_claim_count_30d,
    weather.* except(calendar_event_row),
    env.elevation_m, env.local_relief_500m_m, env.nearest_mapped_water_m,
    env.nearest_mapped_forest_m,
    hot.hotosm_nearest_waterway_m, hot.hotosm_water_features_500m,
    hot.hotosm_water_features_1km, hot.hotosm_water_features_2km,
    hot.hotosm_nearest_drainage_m, hot.hotosm_nearest_flowing_water_m,
    hot.hotosm_nearest_standing_water_m,
    {% for radius in [250, 1000] %}
    {% for category in ['builtup', 'tree', 'grass', 'crop', 'water', 'wetland'] %}
    wc.worldcover_{{ category }}_fraction_{{ radius }}m,
    {% endfor %}
    wc.worldcover_available_{{ radius }}m,
    {% endfor %}
    'recorded_claim_visit_not_confirmed_biological_recurrence' as label_evidence,
    'immediately_after_recorded_base_service' as prediction_time_definition
from anchors a
join histories h using (calendar_event_row)
join outcomes w using (calendar_event_row)
left join {{ ref('warranty_anchor_environment_features') }} weather using (calendar_event_row)
left join {{ source('quality', 'environmental_context_by_location') }} env
  on env.latitude = round(a.latitude, 5) and env.longitude = round(a.longitude, 5)
left join {{ source('quality', 'hotosm_waterway_context_by_location') }} hot
  on hot.latitude = round(a.latitude, 5) and hot.longitude = round(a.longitude, 5)
left join {{ source('landcover_quality', 'worldcover_2021_context_by_location') }} wc
  on wc.latitude = round(a.latitude, 5) and wc.longitude = round(a.longitude, 5)

{% endmacro %}
