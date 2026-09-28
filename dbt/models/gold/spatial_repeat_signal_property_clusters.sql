{{ config(schema='gold', tags=['gold', 'spatial']) }}
-- DBSCAN at property grain. A cluster needs at least three distinct properties;
-- the 1/2/5 km radii are sensitivity views, not inferred pest-spread radii.
select
    *,
    st_clusterdbscan(service_geography, 1000, 3) over () as cluster_1km,
    st_clusterdbscan(service_geography, 2000, 3) over () as cluster_2km,
    st_clusterdbscan(service_geography, 5000, 3) over () as cluster_5km
from {{ ref('spatial_repeat_signal_properties') }}
