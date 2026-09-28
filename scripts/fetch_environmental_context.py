"""Fetch cached static environmental context for ML anchor locations.

Sources:
- Open-Meteo Elevation API (Copernicus DEM GLO-90, 90 m)
- Geoapify Places API (mapped water/wetland/waterway/forest features)

These are exposure proxies, not official flood-history or drainage-condition data.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from google.cloud import bigquery


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "processed" / "environment"
ELEVATION_CACHE = CACHE_DIR / "open_meteo_elevation_v1.jsonl"
GEOAPIFY_ELEVATION_CACHE = CACHE_DIR / "geoapify_elevation_v1.jsonl"
PLACES_CACHE = CACHE_DIR / "geoapify_environment_places_v2.jsonl"
PROJECT = os.getenv("NOMOBUG_BQ_PROJECT", "profound-keel-500007-s4")
LOCATION = os.getenv("NOMOBUG_BQ_LOCATION", "asia-southeast1")
DESTINATION = f"{PROJECT}.quality.environmental_context_by_location_v1"
MAX_BYTES = 25 * 1024 * 1024
RADIUS_M = 2000


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def location_id(latitude: float, longitude: float) -> str:
    key = f"{latitude:.5f},{longitude:.5f}"
    return hashlib.sha256(key.encode()).hexdigest()[:20]


def read_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {
        row["location_id"]: row
        for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    }


def append_cache(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")


def get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "nomobug-capstone-environment/1.0"})
    for attempt in range(9):
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code != 429 or attempt == 8:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else min(2 ** attempt, 60)
            time.sleep(delay)
        except (URLError, ConnectionResetError, TimeoutError):
            if attempt == 8:
                raise
            time.sleep(min(2 ** attempt, 60))
    raise RuntimeError("unreachable retry state")


def post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method="POST", headers={
        "User-Agent": "nomobug-capstone-environment/1.0",
        "Content-Type": "application/json",
    })
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def anchor_locations(client: bigquery.Client) -> list[dict]:
    tick = "`"
    sql = f"""
    select distinct round(f.latitude, 5) latitude, round(f.longitude, 5) longitude
    from {tick}{PROJECT}.analytics_ml.warranty_risk_3session_dataset{tick} d
    join {tick}{PROJECT}.gold.calendar_service_event_facts{tick} f
      on f.calendar_event_row = d.prediction_anchor_event_row
    where f.latitude is not null and f.longitude is not null
    order by latitude, longitude
    """
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False))
    if dry.total_bytes_processed > MAX_BYTES:
        raise SystemExit("Environmental location query exceeds 25 MiB cap")
    return [dict(row) for row in client.query(
        sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES)
    ).result(timeout=120)]


def offset_points(latitude: float, longitude: float) -> list[tuple[float, float]]:
    # Approximately 500 m cardinal offsets, adequate for a local-relief proxy.
    lat_delta = 500 / 111_320
    lon_delta = 500 / (111_320 * max(math.cos(math.radians(latitude)), 0.1))
    return [
        (latitude, longitude), (latitude + lat_delta, longitude),
        (latitude - lat_delta, longitude), (latitude, longitude + lon_delta),
        (latitude, longitude - lon_delta),
    ]


def fetch_elevation(locations: list[dict]) -> dict[str, dict]:
    cache = read_cache(ELEVATION_CACHE)
    missing = [item for item in locations if location_id(**item) not in cache]
    for start in range(0, len(missing), 10):  # smaller resumable batches
        batch = missing[start:start + 10]
        expanded = [point for item in batch for point in offset_points(**item)]
        params = urlencode({
            "latitude": ",".join(f"{point[0]:.6f}" for point in expanded),
            "longitude": ",".join(f"{point[1]:.6f}" for point in expanded),
        })
        payload = get_json(f"https://api.open-meteo.com/v1/elevation?{params}")
        values = payload.get("elevation", [])
        if len(values) != len(expanded):
            raise RuntimeError("Open-Meteo elevation response length mismatch")
        rows = []
        for index, item in enumerate(batch):
            elevations = [float(v) for v in values[index * 5:(index + 1) * 5]]
            rows.append({
                "location_id": location_id(**item), **item,
                "elevation_m": elevations[0],
                "local_relief_500m_m": max(elevations) - min(elevations),
                "elevation_source": "open_meteo_copernicus_dem_glo_90",
            })
        append_cache(ELEVATION_CACHE, rows)
        cache.update({row["location_id"]: row for row in rows})
        time.sleep(0.8)
    return cache


def fetch_geoapify_elevation(locations: list[dict], api_key: str) -> dict[str, dict]:
    """Fetch a consistent elevation/relief surface in <=1000-point POST batches."""
    cache = read_cache(GEOAPIFY_ELEVATION_CACHE)
    missing = [item for item in locations if location_id(**item) not in cache]
    for start in range(0, len(missing), 200):  # 200 locations x 5 points
        batch = missing[start:start + 200]
        expanded = [point for item in batch for point in offset_points(**item)]
        payload = post_json(
            "https://api.geoapify.com/v1/geodata/elevation?" + urlencode({"apiKey": api_key}),
            {"format": "json", "units": "metric", "locations": [
                [point[1], point[0]] for point in expanded
            ]},
        )
        results = payload.get("results", [])
        if len(results) != len(expanded):
            raise RuntimeError("Geoapify elevation response length mismatch")
        rows = []
        for index, item in enumerate(batch):
            elevations = [result.get("elevation") for result in results[index * 5:(index + 1) * 5]]
            if any(value is None for value in elevations):
                raise RuntimeError("Geoapify returned missing terrain elevation")
            elevations = [float(value) for value in elevations]
            rows.append({
                "location_id": location_id(**item), **item,
                "elevation_m": elevations[0],
                "local_relief_500m_m": max(elevations) - min(elevations),
                "elevation_source": "geoapify_elevation",
            })
        append_cache(GEOAPIFY_ELEVATION_CACHE, rows)
        cache.update({row["location_id"]: row for row in rows})
        time.sleep(0.5)
    return cache


def fetch_places(locations: list[dict], api_key: str) -> dict[str, dict]:
    cache = read_cache(PLACES_CACHE)
    categories = "natural.water,natural.wetland,waterway,natural.forest"
    missing = [item for item in locations if location_id(**item) not in cache]

    def fetch_one(item: dict) -> dict:
        lid = location_id(**item)
        lon, lat = item["longitude"], item["latitude"]
        params = urlencode({
            "categories": categories,
            "filter": f"circle:{lon},{lat},{RADIUS_M}",
            "bias": f"proximity:{lon},{lat}",
            "limit": 100,
            "apiKey": api_key,
        })
        payload = get_json(f"https://api.geoapify.com/v2/places?{params}")
        features = payload.get("features", [])
        distances = [feature.get("properties", {}).get("distance") for feature in features]
        distances = [float(value) for value in distances if value is not None]
        water_distances = []
        forest_distances = []
        for feature in features:
            properties = feature.get("properties", {})
            distance = properties.get("distance")
            feature_categories = properties.get("categories", [])
            if distance is None:
                continue
            if any(category == "waterway" or category.startswith("waterway.")
                   or category == "natural.water" or category.startswith("natural.water.")
                   or category == "natural.wetland" for category in feature_categories):
                water_distances.append(float(distance))
            if any(category == "natural.forest" or category.startswith("natural.forest.")
                   for category in feature_categories):
                forest_distances.append(float(distance))
        return {
            "location_id": lid, **item,
            "nearest_mapped_water_or_green_m": min(distances) if distances else None,
            "mapped_water_or_green_features_2km": len(features),
            "nearest_mapped_water_m": min(water_distances) if water_distances else None,
            "mapped_water_features_2km": len(water_distances),
            "nearest_mapped_forest_m": min(forest_distances) if forest_distances else None,
            "mapped_forest_features_2km": len(forest_distances),
            "places_result_capped": len(features) >= 100,
            "places_categories": categories,
            "places_source": "geoapify_places_openstreetmap_derived",
        }

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_one, item) for item in missing]
        for future in as_completed(futures):
            row = future.result()
            append_cache(PLACES_CACHE, [row])
            cache[row["location_id"]] = row
    return cache


def load_bigquery(client: bigquery.Client, rows: list[dict]) -> None:
    schema = [
        bigquery.SchemaField("location_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("latitude", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("longitude", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("elevation_m", "FLOAT"),
        bigquery.SchemaField("local_relief_500m_m", "FLOAT"),
        bigquery.SchemaField("nearest_mapped_water_or_green_m", "FLOAT"),
        bigquery.SchemaField("mapped_water_or_green_features_2km", "INTEGER"),
        bigquery.SchemaField("nearest_mapped_water_m", "FLOAT"),
        bigquery.SchemaField("mapped_water_features_2km", "INTEGER"),
        bigquery.SchemaField("nearest_mapped_forest_m", "FLOAT"),
        bigquery.SchemaField("mapped_forest_features_2km", "INTEGER"),
        bigquery.SchemaField("places_result_capped", "BOOLEAN"),
        bigquery.SchemaField("elevation_source", "STRING"),
        bigquery.SchemaField("places_categories", "STRING"),
        bigquery.SchemaField("places_source", "STRING"),
    ]
    job = client.load_table_from_json(rows, DESTINATION, job_config=bigquery.LoadJobConfig(
        schema=schema, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE))
    job.result(timeout=180)


def main() -> None:
    load_dotenv()
    api_key = os.getenv("NOMOBUG_GEOAPIFY_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("NOMOBUG_GEOAPIFY_API_KEY is required in .env")
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    locations = anchor_locations(client)
    elevation = fetch_geoapify_elevation(locations, api_key)
    places = fetch_places(locations, api_key)
    rows = []
    for item in locations:
        lid = location_id(**item)
        rows.append({**elevation[lid], **places[lid]})
    if len(rows) != len(locations) or len({row["location_id"] for row in rows}) != len(rows):
        raise SystemExit("Environmental context grain validation failed; no warehouse write")
    load_bigquery(client, rows)
    capped = sum(bool(row["places_result_capped"]) for row in rows)
    print(f"Environmental locations: {len(rows)}")
    print(f"Elevation coverage: {sum(row['elevation_m'] is not None for row in rows)}/{len(rows)}")
    print(f"Places coverage: {sum(row['nearest_mapped_water_or_green_m'] is not None for row in rows)}/{len(rows)}")
    print(f"Places responses capped at 100: {capped}/{len(rows)}")
    print(f"WROTE {DESTINATION}")


if __name__ == "__main__":
    main()
