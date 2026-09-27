"""Load a pinned HOTOSM Malaysia waterways snapshot and derive location context."""

import hashlib
import json
import zipfile
from pathlib import Path

import requests
from google.cloud import bigquery

PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
SNAPSHOT_DATE = "2026-09-09"
URL = ("https://production-raw-data-api.s3.amazonaws.com/ISO3/MYS/"
       "waterways/hotosm_mys_waterways_osm_geojson.zip")
EXPECTED_SHA256 = "544664dd486c2b2b8471c8ba2092f879dfa6282406943cf3a211cbdd0853c513"
ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "tmp" / f"hotosm_mys_waterways_{SNAPSHOT_DATE.replace('-', '')}.zip"
NDJSON_PATH = ROOT / "tmp" / "hotosm_mys_waterways_region.ndjson"
RAW_TABLE = f"{PROJECT}.bronze.hotosm_mys_waterways_20260909"
FEATURE_TABLE = f"{PROJECT}.quality.hotosm_mys_waterways_20260909"
CONTEXT_TABLE = f"{PROJECT}.quality.hotosm_waterway_context_by_location_v1"


def coordinate_pairs(value):
    if (isinstance(value, list) and len(value) >= 2
            and all(isinstance(item, (int, float)) for item in value[:2])):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from coordinate_pairs(item)


def context_query(digest: str) -> str:
    return f"""
    create or replace table `{CONTEXT_TABLE}` as
    with locations as (
        select location_id, latitude, longitude,
            st_geogpoint(longitude, latitude) as point
        from `{PROJECT}.quality.environmental_context_by_location_v1`
    )
    select
        l.location_id, l.latitude, l.longitude,
        min(st_distance(l.point, w.geography)) as hotosm_nearest_waterway_m,
        count(distinct if(st_dwithin(l.point, w.geography, 500),
            w.feature_id, null)) as hotosm_water_features_500m,
        count(distinct if(st_dwithin(l.point, w.geography, 1000),
            w.feature_id, null)) as hotosm_water_features_1km,
        count(distinct if(st_dwithin(l.point, w.geography, 2000),
            w.feature_id, null)) as hotosm_water_features_2km,
        min(if(w.water_feature_group = 'DRAINAGE',
            st_distance(l.point, w.geography), null)) as hotosm_nearest_drainage_m,
        min(if(w.water_feature_group = 'FLOWING_WATER',
            st_distance(l.point, w.geography), null)) as hotosm_nearest_flowing_water_m,
        min(if(w.water_feature_group = 'STANDING_WATER',
            st_distance(l.point, w.geography), null)) as hotosm_nearest_standing_water_m,
        count(distinct if(w.water_feature_group = 'DRAINAGE'
            and st_dwithin(l.point, w.geography, 2000), w.feature_id, null))
            as hotosm_drainage_features_2km,
        count(distinct if(w.water_feature_group = 'FLOWING_WATER'
            and st_dwithin(l.point, w.geography, 2000), w.feature_id, null))
            as hotosm_flowing_water_features_2km,
        count(distinct if(w.water_feature_group = 'STANDING_WATER'
            and st_dwithin(l.point, w.geography, 2000), w.feature_id, null))
            as hotosm_standing_water_features_2km,
        date '{SNAPSHOT_DATE}' as source_snapshot_date,
        '{digest}' as source_sha256,
        'OpenStreetMap contributors via HOTOSM/HDX; ODbL' as attribution
    from locations l
    left join `{FEATURE_TABLE}` w
      on st_dwithin(l.point, w.geography, 10000)
    group by l.location_id, l.latitude, l.longitude
    """


def main() -> None:
    ZIP_PATH.parent.mkdir(exist_ok=True)
    if not ZIP_PATH.exists():
        response = requests.get(URL, timeout=180)
        response.raise_for_status()
        ZIP_PATH.write_bytes(response.content)
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"Unexpected HOTOSM snapshot hash: {digest}")

    # This bounding box covers all current service coordinates plus roughly
    # 5â€“7 km. Exact 10 km proximity is applied later with BigQuery geography.
    bounds = (100.35, 1.43, 104.01, 5.71)
    selected = 0
    with zipfile.ZipFile(ZIP_PATH) as archive:
        with archive.open("waterways.geojson") as source:
            collection = json.load(source)
        with NDJSON_PATH.open("w", encoding="utf-8") as output:
            for feature in collection["features"]:
                points = coordinate_pairs(feature["geometry"]["coordinates"])
                if not any(bounds[0] <= p[0] <= bounds[2]
                           and bounds[1] <= p[1] <= bounds[3] for p in points):
                    continue
                props = feature.get("properties") or {}
                record = {
                    "feature_id": props.get("id"),
                    "feature_name": props.get("name"),
                    "waterway": props.get("waterway"),
                    "water": props.get("water"),
                    "natural_class": props.get("natural_class"),
                    "adm1_name": props.get("adm1_name"),
                    "adm2_name": props.get("adm2_name"),
                    "geometry_json": json.dumps(
                        feature["geometry"], separators=(",", ":")),
                    "source_snapshot_date": SNAPSHOT_DATE,
                    "source_sha256": digest,
                }
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                selected += 1

    client = bigquery.Client(project=PROJECT, location=LOCATION)
    schema = [
        bigquery.SchemaField("feature_id", "STRING"),
        bigquery.SchemaField("feature_name", "STRING"),
        bigquery.SchemaField("waterway", "STRING"),
        bigquery.SchemaField("water", "STRING"),
        bigquery.SchemaField("natural_class", "STRING"),
        bigquery.SchemaField("adm1_name", "STRING"),
        bigquery.SchemaField("adm2_name", "STRING"),
        bigquery.SchemaField("geometry_json", "STRING"),
        bigquery.SchemaField("source_snapshot_date", "DATE"),
        bigquery.SchemaField("source_sha256", "STRING"),
    ]
    with NDJSON_PATH.open("rb") as source:
        client.load_table_from_file(source, RAW_TABLE, job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )).result(timeout=600)

    feature_sql = f"""
    create or replace table `{FEATURE_TABLE}` as
    select * except(geometry_json), st_geogfromgeojson(geometry_json) as geography,
        case
            when waterway in ('drain', 'ditch', 'canal') then 'DRAINAGE'
            when waterway in ('river', 'stream', 'tidal_channel') then 'FLOWING_WATER'
            when coalesce(water, natural_class) in
                ('pond', 'lake', 'reservoir', 'basin', 'water') then 'STANDING_WATER'
            when coalesce(water, natural_class) = 'wetland' then 'WETLAND'
            else 'OTHER_WATER'
        end as water_feature_group
    from `{RAW_TABLE}`
    where safe.st_geogfromgeojson(geometry_json) is not null
    """
    client.query(feature_sql).result(timeout=600)

    context_sql = context_query(digest)
    client.query(context_sql).result(timeout=600)
    print(f"HOTOSM LOAD PASS: {selected} regional features; hash {digest}")
    print(f"WROTE {CONTEXT_TABLE}: {client.get_table(CONTEXT_TABLE).num_rows} locations")


if __name__ == "__main__":
    main()
