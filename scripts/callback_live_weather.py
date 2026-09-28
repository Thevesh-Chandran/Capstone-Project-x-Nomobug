"""Refresh prior-day IFS weather privately without changing warehouse pins."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import urllib.parse
import urllib.request

try:
    from scripts import fetch_open_meteo_weather as weather
except ModuleNotFoundError:
    import fetch_open_meteo_weather as weather

FIELDS = {
    'temperature_2m_mean': 'temperature_2m_mean_c',
    'precipitation_sum': 'precipitation_sum_mm',
    'rain_sum': 'rain_sum_mm',
    'relative_humidity_2m_mean': 'relative_humidity_2m_mean_pct',
    'soil_moisture_0_to_7cm_mean': 'soil_moisture_0_to_7cm_mean',
}


def parse_batch(payload, locations, start, end):
    responses = payload if isinstance(payload, list) else [payload]
    if len(responses) != len(locations):
        raise ValueError('Weather response location count differs')
    expected = [(start + timedelta(days=i)).isoformat()
                for i in range((end-start).days+1)]
    rows = []
    for loc, response in zip(locations, responses, strict=True):
        daily = response.get('daily', {})
        if daily.get('time') != expected or response.get('timezone') != 'Asia/Kuala_Lumpur':
            raise ValueError('Weather dates/timezone differ from requested past window')
        if any(len(daily.get(field, [])) != len(expected) for field in FIELDS):
            raise ValueError('Weather variable coverage differs')
        for i, day in enumerate(expected):
            row = {'weather_location_id': weather.location_id(**loc),
                   'requested_latitude': loc['latitude'],
                   'requested_longitude': loc['longitude'],
                   'grid_latitude': response.get('latitude'),
                   'grid_longitude': response.get('longitude'),
                   'weather_date': day, 'weather_model': 'ecmwf_ifs'}
            for source, target in FIELDS.items():
                value = daily[source][i]
                if value is not None and (isinstance(value, bool) or
                        not isinstance(value, (int, float)) or not math.isfinite(value)):
                    raise ValueError('Invalid weather measurement')
                row[target] = value
            for field in ['precipitation_sum_mm', 'rain_sum_mm']:
                if row[field] is not None and row[field] < 0:
                    raise ValueError('Negative rain measurement')
            humidity = row['relative_humidity_2m_mean_pct']
            if humidity is not None and not 0 <= humidity <= 100:
                raise ValueError('Humidity outside physical range')
            moisture = row['soil_moisture_0_to_7cm_mean']
            if moisture is not None and not 0 <= moisture <= 1:
                raise ValueError('Soil moisture outside physical range')
            rows.append(row)
    return rows


def refresh(output_dir: Path, local_day: date, *, locations=None, opener=None):
    """Fetch 30 prior days; unavailable values remain null, never filled as dry."""
    output_dir.mkdir(parents=True, exist_ok=True)
    locations = weather.fetch_locations() if locations is None else locations
    if not locations or len(locations) > 100:
        raise ValueError('Weather grid inventory empty or exceeds 100-cell gate')
    if len({weather.location_id(**loc) for loc in locations}) != len(locations):
        raise ValueError('Weather grid inventory is not unique')
    start, end = local_day-timedelta(days=30), local_day-timedelta(days=1)
    opener = opener or urllib.request.urlopen
    rows = []
    for offset in range(0, len(locations), 10):
        batch = locations[offset:offset+10]
        parameters = urllib.parse.urlencode({
            'latitude': ','.join(f"{x['latitude']:.5f}" for x in batch),
            'longitude': ','.join(f"{x['longitude']:.5f}" for x in batch),
            'start_date': start.isoformat(), 'end_date': end.isoformat(),
            'daily': ','.join(FIELDS), 'timezone': 'Asia/Kuala_Lumpur',
            'models': 'ecmwf_ifs', 'cell_selection': 'land',
        })
        request = urllib.request.Request(weather.API_URL+'?'+parameters,
            headers={'User-Agent': 'nomobug-capstone-live-weather/1.0'})
        with opener(request, timeout=45) as response:
            rows.extend(parse_batch(json.load(response), batch, start, end))
    path = output_dir/'weather_private.json'
    with path.open('x', encoding='utf-8') as handle:
        json.dump(rows, handle, allow_nan=False, separators=(',', ':'))
    receipt = {'model': 'ecmwf_ifs', 'locations': len(locations), 'rows': len(rows),
        'requested_start': start.isoformat(), 'requested_end': end.isoformat(),
        'extracted_at_utc': datetime.now(timezone.utc).isoformat(),
        'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'rows_with_all_measurements': sum(all(row[f] is not None for f in FIELDS.values()) for row in rows),
        'source_url': 'https://open-meteo.com/en/docs/historical-weather-api',
        'limits': 'Regional reanalysis, not property observations; nulls retained; only prior dates.'}
    (output_dir/'weather_receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return receipt
