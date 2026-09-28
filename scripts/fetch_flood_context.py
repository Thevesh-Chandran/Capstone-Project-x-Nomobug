"""Enrich paid-service anchors with publication-gated Copernicus GFM exposure.

Observed flooding in an approximate 1 km buffer is regional context, not proof
that a customer's property flooded. Unknown/flagged pixels never become dry.
Only public map URLs and a broad regional bounding box are sent to EODC.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import threading
from urllib.parse import urlparse

import numpy as np
import requests
import rasterio
from rasterio.warp import transform
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data/processed/environment/gfm'
PROJECT = 'profound-keel-500007-s4'
SOURCE = f'{PROJECT}.analytics_ml.warranty_callback_fixed_horizon_dataset'
DESTINATION = f'{PROJECT}.quality.gfm_flood_context_by_anchor'
STAC = 'https://stac.eodc.eu/api/v1/collections/GFM/items'
ASSETS = ('ensemble_flood_extent', 'exclusion_mask', 'reference_water_mask', 'advisory_flags')
MYT = timezone(timedelta(hours=8))
RADIUS = 1000
MIN_VALID = 0.5
FEATURES = [f'gfm_prior_{days}d_max_flood_fraction_1km' for days in (7, 14, 30)] + [
    'gfm_prior_30d_observed_days', 'gfm_prior_30d_flood_detected_days',
    'gfm_days_since_detected_flood_capped_30d', 'gfm_days_since_valid_observation',
    'gfm_prior_30d_max_valid_fraction_1km']


class MissingQualityLayerError(ValueError):
    """A catalogue scene cannot support the declared reliability policy."""


def parse_time(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Source timestamp must have a timezone')
    return result.astimezone(timezone.utc)


def source_times(item):
    props = item['properties']
    sensed = parse_time(props['datetime'])
    available = max(parse_time(props['created']), parse_time(props['processing:datetime']))
    return sensed, available


def prior_observation(item, anchor_date, horizon=30):
    sensed, available = source_times(item)
    anchor = datetime.combine(datetime.fromisoformat(anchor_date).date(), datetime.min.time(), MYT)
    elapsed = (anchor.date() - sensed.astimezone(MYT).date()).days
    return 1 <= elapsed <= horizon and sensed < anchor and available < anchor


def buffer_statistics(flood, exclusion, reference, advisory, circle):
    valid = circle & np.isin(flood, [0, 1]) & (exclusion == 0) & (reference == 0) & (advisory == 0)
    total = int(circle.sum())
    fraction_valid = float(valid.sum() / total) if total else 0.0
    fraction_flooded = float(((flood == 1) & valid).sum() / valid.sum()) if valid.any() else None
    return fraction_flooded if fraction_valid >= MIN_VALID else None, fraction_valid


def read_buffer(dataset, window):
    """Read a small native window without constructing a boundless GDAL VRT."""
    row, col = int(window.row_off), int(window.col_off)
    height, width = int(window.height), int(window.width)
    result = np.full((height, width), 255, dtype=dataset.dtypes[0])
    top, left = max(row, 0), max(col, 0)
    bottom, right = min(row+height, dataset.height), min(col+width, dataset.width)
    if bottom > top and right > left:
        result[top-row:bottom-row, left-col:right-col] = dataset.read(
            1, window=Window(left, top, right-left, bottom-top))
    return result


class DownloadCache:
    def __init__(self, directory, max_bytes):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.reserved_bytes = 0
        self.downloaded_bytes = 0
        self.lock = threading.Lock()
        self.url_locks = {}

    def get(self, url):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'data.eodc.eu' or not parsed.path.startswith('/collections/GFM'):
            raise ValueError('Unapproved flood asset URL')
        digest = hashlib.sha256(url.encode()).hexdigest()
        destination = self.directory / f'{digest}.tif'
        metadata = destination.with_suffix('.json')
        with self.lock:
            url_lock = self.url_locks.setdefault(url, threading.Lock())
        with url_lock:
            if destination.exists() and metadata.exists():
                receipt = json.loads(metadata.read_text())
                if receipt['url'] == url and destination.stat().st_size == receipt['bytes']:
                    return destination
                raise ValueError('Invalid cached flood asset')
            with requests.get(url, stream=True, timeout=(15, 60), headers={'Accept-Encoding': 'identity'}) as response:
                response.raise_for_status()
                size = int(response.headers.get('Content-Length', '0'))
                if not 0 < size <= 32 * 1024 * 1024:
                    raise ValueError('Asset exceeds 32 MiB file guard or lacks length')
                with self.lock:
                    if self.reserved_bytes + size > self.max_bytes:
                        raise RuntimeError('Flood network-byte ceiling reached')
                    self.reserved_bytes += size
                partial = destination.with_suffix('.part')
                downloaded = 0
                sha = hashlib.sha256()
                try:
                    with partial.open('wb') as handle:
                        for chunk in response.iter_content(64 * 1024):
                            downloaded += len(chunk)
                            if downloaded > size:
                                raise ValueError('Unexpected flood asset size')
                            sha.update(chunk)
                            handle.write(chunk)
                    if downloaded != size:
                        raise ValueError('Incomplete flood asset')
                    partial.replace(destination)
                    metadata.write_text(json.dumps({'url': url, 'bytes': size, 'sha256': sha.hexdigest(),
                                                     'etag': response.headers.get('ETag')}))
                    with self.lock:
                        self.downloaded_bytes += size
                finally:
                    if partial.exists():
                        partial.unlink()
            return destination


def read_anchors():
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT, location='asia-southeast1')
    sql = f'''select d.population, d.sales_record_id, cast(d.anchor_date as string) anchor_date,
        d.anchor_event_row, f.latitude, f.longitude, d.location_uncertainty_radius_m
        from `{SOURCE}` d join `{PROJECT}.gold.calendar_service_event_facts` f
        on d.anchor_event_row = f.calendar_event_row'''
    return [dict(row) for row in client.query(sql, job_config=bigquery.QueryJobConfig(
        maximum_bytes_billed=100 * 1024 * 1024)).result(timeout=300)]


def catalogue(anchors):
    path = CACHE / 'catalogue.json'
    points = [a for a in anchors if a['latitude'] is not None and a['longitude'] is not None]
    bbox = [min(a['longitude'] for a in points)-0.1, min(a['latitude'] for a in points)-0.1,
            max(a['longitude'] for a in points)+0.1, max(a['latitude'] for a in points)+0.1]
    start = min(a['anchor_date'] for a in anchors)
    start = (datetime.fromisoformat(start) - timedelta(days=31)).date().isoformat()
    end = max(a['anchor_date'] for a in anchors)
    if path.exists():
        cached = json.loads(path.read_text())
        if (cached.get('start') == start and cached.get('end') == end
                and cached.get('query_bbox') == bbox
                and cached.get('requested_assets') == list(ASSETS)):
            return cached
    fields = 'id,bbox,geometry,properties,' + ','.join('assets.'+a for a in ASSETS)
    params = {'bbox': ','.join(f'{v:.1f}' for v in bbox),
              'datetime': f'{start}T00:00:00Z/{end}T23:59:59Z', 'limit': 1000, 'fields': fields}
    url = STAC
    items = []
    downloaded = 0
    while url:
        if urlparse(url).hostname != 'stac.eodc.eu':
            raise ValueError('Unapproved catalogue pagination URL')
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        downloaded += len(response.content)
        if downloaded > 50 * 1024 * 1024:
            raise ValueError('Flood catalogue exceeds 50 MiB guard')
        page = response.json()
        items.extend(page['features'])
        print(f'GFM catalogue: {len(items)} items', flush=True)
        url = next((link['href'] for link in page.get('links', []) if link['rel'] == 'next'), None)
        params = None
    payload = {'query_bbox': bbox, 'start': start, 'end': end, 'features': items,
               'requested_assets': list(ASSETS),
               'fetched_at': datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(payload, sort_keys=True))
    return payload


def scene_observations(item, anchors, coordinates, projected, cache):
    props = item['properties']
    if sum(bool(value) for value in props.get('flood_members', {}).values()) < 2:
        return {}
    sensed, available = source_times(item)
    sensed_date = sensed.astimezone(MYT).date()
    bounds = props['proj:bbox']
    point_ids = set()
    for anchor in anchors:
        point_id = anchor['_point_id']
        elapsed = (anchor['_date'] - sensed_date).days
        if point_id is None or not (1 <= elapsed <= 30 and available < anchor['_midnight']):
            continue
        x, y = projected[props['proj:wkt2']][point_id]
        if bounds[0] <= x < bounds[2] and bounds[1] <= y < bounds[3]:
            point_ids.add(point_id)
    if not point_ids:
        return {}
    missing = set(ASSETS) - set(item['assets'])
    if missing:
        raise MissingQualityLayerError('Missing required GFM quality layer(s): '
                                       + ', '.join(sorted(missing)))
    signature = json.dumps({'item': item['id'], 'assets': item['assets'], 'radius': RADIUS,
                            'minimum_valid': MIN_VALID,
                            'coordinates': [coordinates[index] for index in sorted(point_ids)]}, sort_keys=True)
    checkpoint = CACHE / 'observations' / (hashlib.sha256(signature.encode()).hexdigest()+'.json')
    if checkpoint.exists():
        payload = json.loads(checkpoint.read_text())
        if payload['point_ids'] == sorted(point_ids):
            return payload['observations']
    paths = {name: cache.get(item['assets'][name]['href']) for name in ASSETS}
    opened = {name: rasterio.open(path) for name, path in paths.items()}
    observations = {}
    try:
        dataset = opened['ensemble_flood_extent']
        for other in opened.values():
            if (other.crs != dataset.crs or other.transform != dataset.transform
                    or other.shape != dataset.shape):
                raise ValueError('Flood quality rasters are not aligned')
        for point_id in sorted(point_ids):
            x, y = projected[props['proj:wkt2']][point_id]
            row, col = dataset.index(x, y)
            pixels = int(np.ceil(RADIUS / abs(dataset.transform.a))) + 1
            window = Window(col-pixels, row-pixels, 2*pixels+1, 2*pixels+1)
            rows, cols = np.indices((2*pixels+1, 2*pixels+1))
            cx = dataset.transform.c + (cols+window.col_off+0.5) * dataset.transform.a
            cy = dataset.transform.f + (rows+window.row_off+0.5) * dataset.transform.e
            circle = (cx-x)**2 + (cy-y)**2 <= RADIUS**2
            arrays = [read_buffer(opened[name], window) for name in ASSETS]
            value, valid = buffer_statistics(*arrays, circle)
            observations[str(point_id)] = {'fraction': value, 'valid_fraction': valid}
    finally:
        for dataset in opened.values():
            dataset.close()
    checkpoint.write_text(json.dumps({'point_ids': sorted(point_ids), 'observations': observations}))
    return observations


def aggregate_anchor(anchor, observations, fingerprint, fetched_at):
    values = []
    for item, observation in observations:
        if observation['fraction'] is not None and prior_observation(item, anchor['anchor_date']):
            sensed, available = source_times(item)
            days = (datetime.fromisoformat(anchor['anchor_date']).date() - sensed.astimezone(MYT).date()).days
            values.append((days, sensed, available, observation['fraction'], observation['valid_fraction']))
    row = {key: anchor[key] for key in ('population', 'sales_record_id', 'anchor_date')}
    row['flood_anchor_id'] = hashlib.sha256('|'.join(str(row[k]) for k in ('population', 'sales_record_id', 'anchor_date')).encode()).hexdigest()
    for days in (7, 14, 30):
        fractions = [v[3] for v in values if v[0] <= days]
        row[f'gfm_prior_{days}d_max_flood_fraction_1km'] = max(fractions) if fractions else None
    flooded = [v for v in values if v[3] > 0]
    row.update({
        'gfm_prior_30d_observed_days': len(set(v[0] for v in values)),
        'gfm_prior_30d_flood_detected_days': len(set(v[0] for v in flooded)),
        'gfm_days_since_detected_flood_capped_30d': min(v[0] for v in flooded) if flooded else (30 if values else None),
        'gfm_days_since_valid_observation': min(v[0] for v in values) if values else None,
        'gfm_prior_30d_max_valid_fraction_1km': max(v[4] for v in values) if values else None,
        'gfm_last_observation_at': max(v[1] for v in values).isoformat() if values else None,
        'gfm_last_available_at': max(v[2] for v in values).isoformat() if values else None,
        'gfm_source_catalogue_sha256': fingerprint, 'gfm_fetched_at': fetched_at,
        'gfm_status': 'observed_context' if values else 'unknown_no_reliable_prior_observation',
    })
    return row


def mark_source_failures(rows, anchors, items, projected, failures):
    """Distinguish failed relevant maps from absence of reliable observations."""
    failed_ids = {failure['item_id'] for failure in failures}
    failed_items = [item for item in items if item['id'] in failed_ids]
    affected = 0
    for row, anchor in zip(rows, anchors, strict=True):
        point_id = anchor['_point_id']
        if point_id is None:
            continue
        for item in failed_items:
            if not prior_observation(item, anchor['anchor_date']):
                continue
            props = item['properties']
            x, y = projected[props['proj:wkt2']][point_id]
            bounds = props['proj:bbox']
            if bounds[0] <= x < bounds[2] and bounds[1] <= y < bounds[3]:
                row['gfm_status'] = ('observed_context_partial_source_errors'
                                     if row['gfm_prior_30d_observed_days'] > 0
                                     else 'unknown_source_errors')
                affected += 1
                break
    return affected


def upload(rows):
    from google.cloud import bigquery
    types = {'anchor_date': 'DATE', 'gfm_last_observation_at': 'TIMESTAMP',
             'gfm_last_available_at': 'TIMESTAMP', 'gfm_fetched_at': 'TIMESTAMP'}
    for name in FEATURES:
        types[name] = 'FLOAT' if 'fraction' in name else 'INTEGER'
    schema = [bigquery.SchemaField(name, types.get(name, 'STRING')) for name in rows[0]]
    client = bigquery.Client(project=PROJECT, location='asia-southeast1')
    client.load_table_from_json(rows, DESTINATION, job_config=bigquery.LoadJobConfig(
        schema=schema, write_disposition='WRITE_TRUNCATE')).result(timeout=300)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--anchors-json', type=Path)
    parser.add_argument('--max-network-mib', type=int, default=1024)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.max_network_mib <= 4096 or not 1 <= args.workers <= 6:
        raise SystemExit('Network guard must be 1–4096 MiB; workers 1–6')
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE/'observations').mkdir(exist_ok=True)
    anchors = json.loads(args.anchors_json.read_text()) if args.anchors_json else read_anchors()
    coordinates = sorted(set((a['latitude'], a['longitude']) for a in anchors
                             if a['latitude'] is not None and a['longitude'] is not None))
    ids = {point: index for index, point in enumerate(coordinates)}
    for anchor in anchors:
        anchor['_point_id'] = ids.get((anchor['latitude'], anchor['longitude']))
        anchor['_date'] = datetime.fromisoformat(anchor['anchor_date']).date()
        anchor['_midnight'] = datetime.combine(anchor['_date'], datetime.min.time(), MYT)
    catalogue_data = catalogue(anchors)
    fingerprint = hashlib.sha256(json.dumps(catalogue_data, sort_keys=True).encode()).hexdigest()
    items = sorted(catalogue_data['features'], key=lambda item: item['id'])
    projected = {}
    for wkt in set(item['properties']['proj:wkt2'] for item in items):
        xs, ys = transform('EPSG:4326', wkt, [p[1] for p in coordinates], [p[0] for p in coordinates])
        projected[wkt] = list(zip(xs, ys))
    cache = DownloadCache(CACHE/'rasters', args.max_network_mib * 1024 * 1024)
    point_observations = {index: [] for index in range(len(coordinates))}
    failures = []
    success = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(scene_observations, item, anchors, coordinates, projected, cache): item for item in items}
        for number, future in enumerate(as_completed(futures), 1):
            item = futures[future]
            try:
                result = future.result()
                if result:
                    success += 1
                for point, observation in result.items():
                    point_observations[int(point)].append((item, observation))
            except Exception as exc:
                failures.append({'item_id': item['id'], 'error': str(exc)[:300],
                                 'kind': ('missing_quality_layers'
                                          if isinstance(exc, MissingQualityLayerError)
                                          else 'retrieval_or_extraction_error')})
            if number % 100 == 0:
                print(f'GFM extraction {number}/{len(items)}: {success} relevant maps, {len(failures)} errors, {cache.downloaded_bytes/1048576:.1f} MiB', flush=True)
    fetched_at = datetime.now(timezone.utc).isoformat()
    rows = [aggregate_anchor(anchor, point_observations.get(anchor['_point_id'], []), fingerprint, fetched_at) for anchor in anchors]
    affected = mark_source_failures(rows, anchors, items, projected, failures)
    output = CACHE/'flood_context_by_anchor.jsonl'
    output.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    receipt = {'source': STAC, 'catalogue_sha256': fingerprint, 'catalogue_items': len(items),
               'anchors': len(rows), 'locations': len(coordinates), 'relevant_maps': success,
               'downloaded_bytes': cache.downloaded_bytes, 'errors': failures,
               'anchors_with_source_errors': affected,
               'observed_anchors': sum(row['gfm_prior_30d_observed_days'] > 0 for row in rows),
               'flood_exposed_anchors': sum(row['gfm_prior_30d_flood_detected_days'] > 0 for row in rows),
               'buffer_radius_m': RADIUS, 'min_reliable_pixel_fraction': MIN_VALID,
               'quality_masks': list(ASSETS[1:]), 'missing_is_not_no_flood': True,
               'available_before_local_anchor_midnight': True, 'fetched_at': fetched_at}
    (CACHE/'receipt.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps({key: value for key, value in receipt.items() if key != 'errors'}, indent=2))
    if args.upload:
        upload(rows)


if __name__ == '__main__':
    main()
