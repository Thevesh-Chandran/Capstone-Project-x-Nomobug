{{ config(tags=['calendar', 'location']) }}
-- Calendar event is the service-location grain. A linked sale may describe a
-- different property, so coordinates are never inherited from SALES here.
select
    e.calendar_event_row,
    e.event_date_local,
    e.event_category,
    e.warranty_claim_candidate,
    e.warranty_claim_reason,
    e.extra_visit_candidate,
    g.address_hash,
    g.latitude,
    g.longitude,
    st_geogpoint(g.longitude, g.latitude) as service_geography,
    to_hex(sha256(format('%.5f,%.5f', round(g.latitude, 1), round(g.longitude, 1))))
        as weather_location_id,
    g.geocode_provider,
    g.coordinate_source,
    g.manual_override_protected,
    g.precision_tier,
    g.provider_result_type,
    g.provider_confidence,
    g.postcode_agrees,
    g.geocoded_at_utc,
    case g.precision_tier
        when 'precise_candidate' then 250
        when 'street_candidate' then 1000
        when 'postcode_area_candidate' then 5000
        when 'area_analysis_candidate' then
            case g.provider_result_type
                when 'building' then 2000
                when 'amenity' then 2500
                when 'street' then 3000
                else 5000
            end
        when 'text_agreement_candidate' then
            case g.provider_result_type
                when 'building' then 1500
                when 'amenity' then 2000
                when 'street' then 2500
                when 'suburb' then 7500
                when 'district' then 10000
                when 'city' then 10000
                else 5000
            end
        when 'proximity_candidate' then 5000
        when 'peer_address_candidate' then 2500
        when 'google_hinted_area_candidate' then 10000
        when 'manual_verified' then 250
        when 'area_reference_verified' then 5000
    end as location_uncertainty_radius_m,
    g.precision_tier in (
        'precise_candidate', 'street_candidate', 'postcode_area_candidate',
        'area_analysis_candidate', 'text_agreement_candidate', 'proximity_candidate',
        'peer_address_candidate', 'manual_verified', 'area_reference_verified'
    ) as heatmap_eligible,
    g.precision_tier in (
        'precise_candidate', 'street_candidate', 'postcode_area_candidate',
        'area_analysis_candidate', 'text_agreement_candidate', 'proximity_candidate',
        'peer_address_candidate', 'google_hinted_area_candidate',
        'manual_verified', 'area_reference_verified'
    ) as weather_eligible
from {{ ref('calendar_events') }} e
join {{ source('quality', 'calendar_event_geocodes_all') }} g using (calendar_event_row)
where e.service_candidate
  and e.event_date_local between date '2023-01-01' and date '2026-12-31'
