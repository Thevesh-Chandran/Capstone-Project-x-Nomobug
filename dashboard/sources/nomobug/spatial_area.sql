select a.area_cell,
  coalesce(n.place, d.district, 'Unnamed area') as place,
  a.area_centroid_latitude as lat, a.area_centroid_longitude as lng,
  a.scheduled_service_event_rows as services, a.matched_sales_records as sales_records,
  a.repeat_signal_event_rows as return_visits, a.repeat_signal_share as return_share
from `profound-keel-500007-s4.gold.dashboard_spatial_area` a
left join `profound-keel-500007-s4.predictions.area_cell_names` n using (area_cell)
left join `profound-keel-500007-s4.predictions.district_boundaries` d
  on st_contains(st_geogfromgeojson(d.geom, make_valid => true), st_geogpoint(a.area_centroid_longitude, a.area_centroid_latitude))
where a.area_centroid_latitude is not null and a.area_centroid_longitude is not null
