{{ config(schema='gold', tags=['gold', 'dashboard', 'looker']) }}
-- Privacy-safe map source. One several-kilometre geohash area, never an event
-- or property coordinate. Low-volume cells are withheld from this release view.
select
    area_cell,
    st_y(observed_event_centroid) as area_centroid_latitude,
    st_x(observed_event_centroid) as area_centroid_longitude,
    scheduled_service_event_rows,
    matched_sales_records,
    repeat_signal_event_rows,
    warranty_label_event_rows,
    over_sequence_event_rows,
    repeat_signal_share,
    'geohash_precision_5_several_km_analytical_area_not_pest_radius_or_property'
        as map_grain_evidence,
    denominator_evidence
from {{ ref('spatial_service_area_metrics') }}
where sufficient_volume_for_comparison
