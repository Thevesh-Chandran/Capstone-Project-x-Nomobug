"""Bounded ESA WorldCover 2021 context from public, cached COG byte ranges.

Only public 3-degree tile names are requested. Customer identifiers and service
coordinates are not sent to a third-party extraction API. WorldCover is a fixed
2021 land-cover snapshot, not current property conditions or observed flooding.
Source/attribution: https://esa-worldcover.org/en/data-access
© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021)
processed by ESA WorldCover consortium. CC BY 4.0, DOI 10.5281/zenodo.7254221.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
from google.cloud import bigquery


ROOT = Path(__file__).resolve().parents[1]
PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
CACHE_DIR = ROOT / "data" / "processed" / "environment" / "worldcover_2021"
OUTPUT = CACHE_DIR / "worldcover_context_v1.jsonl"
DESTINATION = f"{PROJECT}.quality.worldcover_2021_context_by_location"
MAX_QUERY_BYTES = 50 * 1024 * 1024
MAX_NETWORK_BYTES = 250 * 1024 * 1024
BLOCK_BYTES = 64 * 1024
MIN_VALID_FRACTION = 0.95
RADII = (250, 1000)
CLASSES = {
    "tree": (10,), "grass": (30,), "crop": (40,), "builtup": (50,),
    "water": (80,), "wetland": (90, 95),
}
VALID_CLASSES = (10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100)


class BudgetExceeded(RuntimeError):
    """The deterministic byte ceiling was reached before another download."""


class NetworkBudget:
    def __init__(self, limit: int = MAX_NETWORK_BYTES):
        if not 1 <= limit <= MAX_NETWORK_BYTES:
            raise ValueError("Network byte limit must be between 1 and 250 MiB")
        self.limit = limit
        self.downloaded = 0

    def require(self, size: int) -> None:
        if self.downloaded + size > self.limit:
            raise BudgetExceeded("WorldCover download would exceed network-byte cap")


class RangeFile(io.RawIOBase):
    """Seekable binary source; every uncached HTTP range counts against budget."""

    def __init__(self, url: str, cache_dir: Path, budget: NetworkBudget):
        super().__init__()
        self.url = url
        self.cache_dir = cache_dir / hashlib.sha256(url.encode()).hexdigest()[:20]
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.budget = budget
        self.position = 0
        metadata_path = self.cache_dir / "metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        else:
            request = Request(url, method="HEAD", headers={"User-Agent": "cp2-worldcover/1.0"})
            with urlopen(request, timeout=30) as response:
                if response.headers.get("Accept-Ranges") != "bytes":
                    raise ValueError("WorldCover server does not support bounded byte ranges")
                metadata = {
                    "url": url, "size": int(response.headers["Content-Length"]),
                    "etag": response.headers.get("ETag"),
                }
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        if metadata.get("url") != url or int(metadata["size"]) <= 0:
            raise ValueError("Invalid WorldCover range-cache metadata")
        self.size = int(metadata["size"])

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            position = offset
        elif whence == 1:
            position = self.position + offset
        elif whence == 2:
            position = self.size + offset
        else:
            raise ValueError("Unsupported seek origin")
        if position < 0:
            raise ValueError("Cannot seek to a negative offset")
        self.position = position
        return position

    def _block(self, index: int) -> bytes:
        start = index * BLOCK_BYTES
        end = min(start + BLOCK_BYTES, self.size) - 1
        expected = end - start + 1
        path = self.cache_dir / f"{index:08d}.bin"
        if path.exists():
            payload = path.read_bytes()
            if len(payload) != expected:
                raise ValueError("Incomplete cached WorldCover byte range")
            return payload
        self.budget.require(expected)
        request = Request(self.url, headers={
            "Range": f"bytes={start}-{end}", "User-Agent": "cp2-worldcover/1.0",
        })
        with urlopen(request, timeout=45) as response:
            if response.status != 206:
                raise ValueError("Server ignored byte Range; full download prohibited")
            content_range = response.headers.get("Content-Range", "")
            if content_range != f"bytes {start}-{end}/{self.size}":
                raise ValueError("Unexpected WorldCover Content-Range")
            payload = response.read(expected)
            self.budget.downloaded += len(payload)
        if len(payload) != expected:
            raise ValueError("Incomplete WorldCover HTTP byte range")
        temporary = path.with_suffix(".part")
        temporary.write_bytes(payload)
        temporary.replace(path)
        return payload

    def read(self, size: int = -1) -> bytes:
        if self.closed:
            raise ValueError("Read from closed range file")
        end = self.size if size < 0 else min(self.position + size, self.size)
        if end <= self.position:
            return b""
        parts = []
        while self.position < end:
            index = self.position // BLOCK_BYTES
            block = self._block(index)
            start_in_block = self.position % BLOCK_BYTES
            length = min(len(block) - start_in_block, end - self.position)
            parts.append(block[start_in_block:start_in_block + length])
            self.position += length
        return b"".join(parts)

    def readinto(self, buffer) -> int:
        payload = self.read(len(buffer))
        buffer[:len(payload)] = payload
        return len(payload)


def tile_name(latitude: float, longitude: float) -> str:
    lat_origin = int(math.floor(latitude / 3.0) * 3)
    lon_origin = int(math.floor(longitude / 3.0) * 3)
    return (f"{'N' if lat_origin >= 0 else 'S'}{abs(lat_origin):02d}"
            f"{'E' if lon_origin >= 0 else 'W'}{abs(lon_origin):03d}")


def tile_url(tile: str) -> str:
    if not re.fullmatch(r"[NS]\d{2}[EW]\d{3}", tile):
        raise ValueError("Invalid public WorldCover tile identifier")
    return ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
            f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")


def location_id(latitude: float, longitude: float) -> str:
    return hashlib.sha256(f"{latitude:.5f},{longitude:.5f}".encode()).hexdigest()[:20]


def anchor_locations(client: bigquery.Client, limit: int) -> tuple[list[dict], int]:
    sql = f"""
    with anchors as (
        select f.latitude, f.longitude
        from `{PROJECT}.analytics_ml.warranty_fixed_horizon_dataset` d
        join `{PROJECT}.gold.calendar_service_event_facts` f
          on f.calendar_event_row = d.anchor_event_row
    ), locations as (
        select round(latitude, 5) as latitude, round(longitude, 5) as longitude,
            count(*) as anchor_usage
        from anchors
        where latitude between 1 and 8 and longitude between 99 and 105
        group by 1, 2
    )
    select latitude, longitude, count(*) over () as total_locations
    from locations order by anchor_usage desc,
        farm_fingerprint(format('%.5f,%.5f', latitude, longitude)) limit @location_limit
    """
    parameters = [bigquery.ScalarQueryParameter("location_limit", "INT64", limit)]
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False, query_parameters=parameters))
    if dry.total_bytes_processed > MAX_QUERY_BYTES:
        raise SystemExit("WorldCover anchor query exceeds 50 MiB input cap")
    rows = [dict(row) for row in client.query(sql, job_config=bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_QUERY_BYTES, query_parameters=parameters,
    )).result(timeout=120)]
    total = int(rows[0]["total_locations"]) if rows else 0
    return [{"latitude": float(row["latitude"]), "longitude": float(row["longitude"])}
            for row in rows], total


def summarize_pixels(values: np.ndarray, distance_m: np.ndarray, radius: int) -> dict:
    mask = distance_m <= radius
    total = int(mask.sum())
    valid = mask & np.isin(values, VALID_CLASSES)
    count = int(valid.sum())
    coverage = count / total if total else None
    available = total > 0 and coverage >= MIN_VALID_FRACTION
    result = {
        f"worldcover_total_pixels_{radius}m": total,
        f"worldcover_valid_pixels_{radius}m": count,
        f"worldcover_valid_fraction_{radius}m": coverage,
        f"worldcover_available_{radius}m": available,
    }
    for category, codes in CLASSES.items():
        result[f"worldcover_{category}_fraction_{radius}m"] = (
            float((valid & np.isin(values, codes)).sum() / count) if available else None)
    return result


class RasterTiles:
    def __init__(self, cache_dir: Path, budget: NetworkBudget):
        # Optional geospatial dependency is only needed for execute mode.
        import rasterio
        self.rasterio = rasterio
        self.cache_dir = cache_dir
        self.budget = budget
        self.stack = ExitStack()
        self.datasets = {}

    def __enter__(self):
        self.stack.enter_context(self.rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def dataset(self, tile: str):
        if tile not in self.datasets:
            url = tile_url(tile)
            filename = f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"

            def opener(path: str, mode: str = "rb"):
                if path != filename or mode not in ("r", "rb"):
                    raise FileNotFoundError(path)
                return RangeFile(url, self.cache_dir, self.budget)

            dataset = self.stack.enter_context(self.rasterio.open(
                filename, driver="GTiff", opener=opener, sharing=False))
            if dataset.crs.to_epsg() != 4326 or dataset.count != 1:
                raise ValueError("Unexpected WorldCover raster grid")
            self.datasets[tile] = dataset
        return self.datasets[tile]

    def context(self, latitude: float, longitude: float) -> dict:
        from rasterio.windows import Window, from_bounds, transform
        radius = max(RADII)
        lat_delta = radius / 111_320.0
        lon_scale = 111_320.0 * math.cos(math.radians(latitude))
        lon_delta = radius / lon_scale
        west, east = longitude - lon_delta, longitude + lon_delta
        south, north = latitude - lat_delta, latitude + lat_delta
        tiles = sorted({tile_name(lat, lon)
                        for lat in (south, north) for lon in (west, east)})
        values, distances = [], []
        for tile in tiles:
            dataset = self.dataset(tile)
            bounds = dataset.bounds
            tile_west, tile_east = max(west, bounds.left), min(east, bounds.right)
            tile_south, tile_north = max(south, bounds.bottom), min(north, bounds.top)
            if tile_west >= tile_east or tile_south >= tile_north:
                continue
            fractional = from_bounds(tile_west, tile_south, tile_east, tile_north,
                                     transform=dataset.transform)
            col_start, row_start = math.floor(fractional.col_off), math.floor(fractional.row_off)
            col_end = math.ceil(fractional.col_off + fractional.width)
            row_end = math.ceil(fractional.row_off + fractional.height)
            window = Window(col_start, row_start, col_end - col_start,
                            row_end - row_start).intersection(Window(0, 0, dataset.width, dataset.height))
            data = dataset.read(1, window=window)
            pixel_transform = transform(window, dataset.transform)
            rows, cols = np.indices(data.shape)
            xs = pixel_transform.c + (cols + 0.5) * pixel_transform.a
            ys = pixel_transform.f + (rows + 0.5) * pixel_transform.e
            distance = np.sqrt(((xs - longitude) * lon_scale) ** 2
                               + ((ys - latitude) * 111_320.0) ** 2)
            values.append(data.ravel())
            distances.append(distance.ravel())
        if not values:
            raise ValueError("No WorldCover raster pixels intersect location")
        pixel_values, pixel_distances = np.concatenate(values), np.concatenate(distances)
        result = {
            "location_id": location_id(latitude, longitude),
            "latitude": latitude, "longitude": longitude,
            "worldcover_year": 2021, "worldcover_version": "v200",
            "worldcover_source_tiles": ",".join(tiles),
            "worldcover_source": "ESA WorldCover 2021 v200;10m;doi:10.5281/zenodo.7254221",
            "worldcover_buffer_method": "pixel_centres_approx_circular;111320m_per_degree;cos_latitude",
            "worldcover_wetland_definition": "classes90_herbaceous_wetland_and95_mangrove",
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        for radius in RADII:
            result.update(summarize_pixels(pixel_values, pixel_distances, radius))
        return result


def cached_context() -> dict[str, dict]:
    if not OUTPUT.exists():
        return {}
    rows = [json.loads(line) for line in OUTPUT.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    if len(rows) != len({row["location_id"] for row in rows}):
        raise ValueError("Duplicate cached WorldCover locations")
    return {row["location_id"]: row for row in rows}


def validate_rows(rows: list[dict]) -> None:
    if not rows or len(rows) > 500 or len(rows) != len({row["location_id"] for row in rows}):
        raise ValueError("WorldCover output must contain 1–500 distinct locations")
    for row in rows:
        for radius in RADII:
            available = row[f"worldcover_available_{radius}m"]
            fractions = [row[f"worldcover_{category}_fraction_{radius}m"] for category in CLASSES]
            if available and (any(value is None or not 0 <= value <= 1 for value in fractions)
                              or sum(fractions) > 1.000000001):
                raise ValueError("Invalid WorldCover fraction bounds")
            if not available and any(value is not None for value in fractions):
                raise ValueError("Unavailable WorldCover coverage must remain null")


def upload(client: bigquery.Client, rows: list[dict]) -> None:
    validate_rows(rows)
    schema = []
    for field, value in rows[0].items():
        if isinstance(value, bool):
            kind = "BOOLEAN"
        elif isinstance(value, int):
            kind = "INTEGER"
        elif isinstance(value, float) or value is None:
            kind = "FLOAT"
        else:
            kind = "STRING"
        schema.append(bigquery.SchemaField(field, kind))
    client.load_table_from_json(rows, DESTINATION, job_config=bigquery.LoadJobConfig(
        schema=schema, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )).result(timeout=180)


def report_model_coverage(client: bigquery.Client, rows: list[dict]) -> None:
    def keys(available_radius=None):
        return [f"{row['latitude']:.5f},{row['longitude']:.5f}" for row in rows
                if available_radius is None or row[f"worldcover_available_{available_radius}m"]]

    parameters = [
        bigquery.ArrayQueryParameter("selected_keys", "STRING", keys()),
        bigquery.ArrayQueryParameter("available_250m_keys", "STRING", keys(250)),
        bigquery.ArrayQueryParameter("available_1000m_keys", "STRING", keys(1000)),
    ]
    sql = f"""
    with scoped as (
        select d.population,
            if(d.anchor_date < date '2026-01-01', 'pre_2026', '2026') as period,
            f.latitude, f.longitude,
            format('%.5f,%.5f', round(f.latitude, 5), round(f.longitude, 5)) as coordinate_key
        from `{PROJECT}.analytics_ml.warranty_fixed_horizon_dataset` d
        left join `{PROJECT}.gold.calendar_service_event_facts` f
          on f.calendar_event_row = d.anchor_event_row
    )
    select population, period, count(*) as anchor_rows,
        countif(latitude is not null and longitude is not null) as geocoded_rows,
        countif(coordinate_key in unnest(@selected_keys)) as selected_context_rows,
        countif(coordinate_key in unnest(@available_250m_keys)) as available_250m_rows,
        countif(coordinate_key in unnest(@available_1000m_keys)) as available_1000m_rows
    from scoped group by population, period order by population, period
    """
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False, query_parameters=parameters))
    if dry.total_bytes_processed > MAX_QUERY_BYTES:
        raise SystemExit("WorldCover coverage query exceeds 50 MiB cap")
    print("Model coverage (bounded 500-location enrichment, not all properties):")
    for row in client.query(sql, job_config=bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_QUERY_BYTES, query_parameters=parameters,
    )).result(timeout=120):
        print(json.dumps(dict(row), sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--max-locations", type=int, default=2)
    parser.add_argument("--max-download-mib", type=int, default=250)
    args = parser.parse_args()
    if not 1 <= args.max_locations <= 500 or not 1 <= args.max_download_mib <= 250:
        raise SystemExit("Caps are 1–500 locations and 1–250 MiB download")
    if args.upload and not args.execute:
        raise SystemExit("--upload requires --execute")
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    try:
        locations, total = anchor_locations(client, args.max_locations)
        print(f"Eligible Malaysian anchor locations: {total}; selected: {len(locations)}")
        if not args.execute:
            print("PLAN ONLY: no WorldCover downloads or warehouse writes")
            return
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache = cached_context()
        budget = NetworkBudget(args.max_download_mib * 1024 * 1024)
        failures = 0
        started = time.monotonic()
        with RasterTiles(CACHE_DIR / "range_cache", budget) as tiles:
            for index, item in enumerate(locations, start=1):
                lid = location_id(**item)
                if lid in cache:
                    continue
                try:
                    cache[lid] = tiles.context(**item)
                    OUTPUT.write_text("".join(json.dumps(row) + "\n" for row in cache.values()),
                                      encoding="utf-8")
                except (HTTPError, OSError, ValueError, BudgetExceeded) as exc:
                    failures += 1
                    print(f"Location {index}: unavailable ({type(exc).__name__}); no zero-filled features")
                    if isinstance(exc, BudgetExceeded):
                        break
                if index % 25 == 0:
                    print(f"Processed {index}; downloaded {budget.downloaded / 1024 / 1024:.2f} MiB")
        selected = [cache[location_id(**item)] for item in locations if location_id(**item) in cache]
        print(f"Cached selected locations: {len(selected)}/{len(locations)}; failures: {failures}")
        print(f"Downloaded {budget.downloaded / 1024 / 1024:.2f} MiB in {time.monotonic()-started:.1f}s")
        for radius in RADII:
            print(f"Available {radius}m fractions: {sum(row[f'worldcover_available_{radius}m'] for row in selected)}")
        if args.upload:
            if len(selected) != len(locations):
                raise SystemExit("Incomplete selected coverage; warehouse output preserved")
            if args.max_locations < min(total, 500):
                raise SystemExit("Pilot cannot replace full warehouse context; use --max-locations 500")
            upload(client, selected)
            print(f"WROTE {DESTINATION}: {len(selected)} locations; cap-selected from {total}")
            report_model_coverage(client, selected)
    finally:
        client.close()


if __name__ == "__main__":
    main()
