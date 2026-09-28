"""Add conservative, reported regional flood context from public GDACS records.

Analyst affected-area polygons are not observed inundation footprints. No match
means no matching record in this queried catalogue, never evidence of dry land.
Customer coordinates remain local; public source queries use Malaysia only.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import threading
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/processed/environment/gdacs"
MYT = timezone(timedelta(hours=8))
UTC = timezone.utc
QUERY_START = "2024-01-01"
QUERY_END = "2026-09-27"
DESTINATION = "profound-keel-500007-s4.quality.gdacs_reported_flood_context_by_anchor"
API = "https://www.gdacs.org/gdacsapi/api/"
NUMERIC = [f"gdacs_prior_{days}d_reported_events" for days in (7, 14, 30)] + [
    "gdacs_days_since_reported_event_capped_30d"]
NAIVE_AVAILABILITY_DELAY = timedelta(days=1)


def source_timestamp(value, *, availability=False):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        # GDACS JSON omits the zone. Reports show UTC, while database insert
        # stamps can differ by a European local-time offset. Delay their use.
        result = result.replace(tzinfo=UTC)
        if availability:
            result += NAIVE_AVAILABILITY_DELAY
    return result.astimezone(UTC)


def point_on_segment(x, y, a, b):
    cross = (x-a[0])*(b[1]-a[1]) - (y-a[1])*(b[0]-a[0])
    return (abs(cross) <= 1e-12 and min(a[0], b[0])-1e-12 <= x <= max(a[0], b[0])+1e-12
            and min(a[1], b[1])-1e-12 <= y <= max(a[1], b[1])+1e-12)


def point_in_ring(x, y, ring):
    inside = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        if point_on_segment(x, y, a, b):
            return True
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if x < crossing:
                inside = not inside
    return inside


def point_in_geometry(longitude, latitude, geometry):
    kind, coordinates = geometry["type"], geometry["coordinates"]
    polygons = [coordinates] if kind == "Polygon" else coordinates if kind == "MultiPolygon" else []
    return any(rings and point_in_ring(longitude, latitude, rings[0])
               and not any(point_in_ring(longitude, latitude, hole) for hole in rings[1:])
               for rings in polygons)


class PublicCache:
    def __init__(self, directory, budget=64*1024*1024):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.budget = budget
        self.downloaded = 0
        self.lock = threading.Lock()

    def get(self, url):
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "www.gdacs.org" or not parsed.path.startswith("/gdacsapi/api/"):
            raise ValueError("Unapproved GDACS resource URL")
        path = self.directory / (hashlib.sha256(url.encode()).hexdigest()+".json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        chunks = []
        size = 0
        with requests.get(url, stream=True, timeout=(15, 45)) as response:
            response.raise_for_status()
            if response.status_code == 204:
                payload = {"type": "FeatureCollection", "features": [], "_http_status": 204}
                path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
                return payload
            for chunk in response.iter_content(64*1024):
                size += len(chunk)
                if size > 8*1024*1024:
                    raise ValueError("GDACS single-resource byte guard exceeded")
                with self.lock:
                    self.downloaded += len(chunk)
                    if self.downloaded > self.budget:
                        raise ValueError("GDACS total network-byte guard exceeded")
                chunks.append(chunk)
        payload = json.loads(b"".join(chunks))
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return payload


def query_events(cache, start=QUERY_START, end=QUERY_END):
    """Verify pagination ends at an empty page, including a short first page."""
    endpoint = API + "Events/geteventlist/search"
    parameters = {"eventlist": "FL", "country": "Malaysia", "alertlevel": "Green;Orange;Red",
                  "fromDate": start, "toDate": end, "pageSize": 100}
    events, pages, keys = [], [], set()
    for number in range(1, 11):
        params = {**parameters, "pageNumber": number}
        url = requests.Request("GET", endpoint, params=params).prepare().url
        payload = cache.get(url)
        if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
            raise ValueError("Unexpected GDACS catalogue response")
        batch = payload["features"]
        if len(batch) > 100:
            raise ValueError("GDACS catalogue exceeds requested page size")
        pages.append({"page_number": number, "records": len(batch), "url": url,
                      "http_status": payload.get("_http_status", 200)})
        if not batch:
            return events, {"endpoint": endpoint, "parameters": parameters, "pages": pages,
                            "completed_by_empty_page": True}
        batch_keys = [(f["properties"]["eventtype"], f["properties"]["eventid"]) for f in batch]
        if len(set(batch_keys)) != len(batch_keys) or any(key in keys for key in batch_keys):
            raise ValueError("Duplicate events across GDACS pages; pagination may not be honoured")
        keys.update(batch_keys)
        events.extend(batch)
    raise ValueError("GDACS query did not complete within 10-page guard")


def prepare_reports(event, geometry_payload, detail_payload):
    event_props = event["properties"]
    detail_props = detail_payload["properties"]
    # All historical episodes inherit current event modification metadata in
    # this API. No attempt is made to reconstruct earlier publication times.
    available = [source_timestamp(event_props["datemodified"], availability=True),
                 source_timestamp(detail_props["datemodified"], availability=True)]
    for indicator in detail_props.get("sendai", []):
        if indicator.get("dateinsert"):
            available.append(source_timestamp(indicator["dateinsert"], availability=True))
    reports = []
    for feature in geometry_payload["features"]:
        props, geometry = feature["properties"], feature["geometry"]
        if props.get("Class") != "Poly_Affected" or geometry["type"] not in ("Polygon", "MultiPolygon"):
            continue
        if (props.get("eventid") != event_props["eventid"]
                or props.get("episodeid") != event_props["episodeid"]):
            raise ValueError("GDACS geometry key mismatch")
        if not props.get("polygondate") or not props.get("datemodified"):
            raise ValueError("GDACS affected geometry lacks date provenance")
        event_at = source_timestamp(props["polygondate"])
        publication = max(available + [source_timestamp(props["datemodified"], availability=True), event_at])
        reports.append({"eventid": props["eventid"], "episodeid": props["episodeid"],
                        "event_at": event_at.isoformat(), "available_at": publication.isoformat(),
                        "geometry": geometry})
    return reports


def aggregate_anchor(anchor, reports, fingerprint, fetched_at, query_start=QUERY_START, query_end=QUERY_END):
    row = {key: str(anchor[key]) for key in ("population", "sales_record_id", "anchor_date")}
    row["flood_anchor_id"] = hashlib.sha256("|".join(row[k] for k in
        ("population", "sales_record_id", "anchor_date")).encode()).hexdigest()
    midnight = datetime.combine(datetime.fromisoformat(row["anchor_date"]).date(), datetime.min.time(), MYT)
    lat, lon = anchor.get("latitude"), anchor.get("longitude")
    status = None
    if lat is None or lon is None or not math.isfinite(lat) or not math.isfinite(lon):
        status = "unknown_missing_location"
    elif midnight.date() < datetime.fromisoformat(query_start).date()+timedelta(days=30) or row["anchor_date"] > query_end:
        status = "unknown_outside_query_period"
    matches = []
    if status is None:
        for report in reports:
            event_at = source_timestamp(report["event_at"])
            available_at = source_timestamp(report["available_at"])
            elapsed = (midnight.date()-event_at.astimezone(MYT).date()).days
            if (1 <= elapsed <= 30 and event_at < midnight and available_at < midnight
                    and point_in_geometry(lon, lat, report["geometry"])):
                matches.append((elapsed, report["eventid"], event_at, available_at))
        status = "reported_region_match" if matches else "no_matching_recorded_report"
    for days in (7, 14, 30):
        row[f"gdacs_prior_{days}d_reported_events"] = (None if status.startswith("unknown_") else
            len({m[1] for m in matches if m[0] <= days}))
    row.update({"gdacs_days_since_reported_event_capped_30d": (None if status.startswith("unknown_") else
                min(m[0] for m in matches) if matches else 30),
                "gdacs_last_report_available_at": max(m[3] for m in matches).isoformat() if matches else None,
                "gdacs_last_report_event_at": max(m[2] for m in matches).isoformat() if matches else None,
                "gdacs_source_sha256": fingerprint, "gdacs_fetched_at": fetched_at,
                "gdacs_status": status})
    return row


def upload(rows):
    from google.cloud import bigquery
    fields = {"anchor_date": "DATE", "gdacs_last_report_available_at": "TIMESTAMP",
              "gdacs_last_report_event_at": "TIMESTAMP", "gdacs_fetched_at": "TIMESTAMP"}
    fields.update({name: "INTEGER" for name in NUMERIC})
    schema = [bigquery.SchemaField(name, fields.get(name, "STRING")) for name in rows[0]]
    client = bigquery.Client(project="profound-keel-500007-s4", location="asia-southeast1")
    client.load_table_from_json(rows, DESTINATION, job_config=bigquery.LoadJobConfig(
        schema=schema, write_disposition="WRITE_TRUNCATE")).result(timeout=300)


def load_anchors(path=None):
    if path is not None:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        from scripts.fetch_flood_context import read_anchors
    except ModuleNotFoundError as error:
        if error.name != "scripts":
            raise
        from fetch_flood_context import read_anchors
    return read_anchors()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchors-json", type=Path, help="Replay frozen anchors; default reads the bounded BigQuery source")
    parser.add_argument("--events-json", type=Path, help="Replay a frozen catalogue with verified query metadata")
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = PublicCache(CACHE/"public")
    if args.events_json:
        frozen = json.loads(args.events_json.read_text(encoding="utf-8"))
        events, query = frozen["features"], frozen["query"]
        if (not query.get("completed_by_empty_page") or query["parameters"]["country"] != "Malaysia"
                or query["parameters"]["eventlist"] != "FL"
                or query["parameters"]["alertlevel"] != "Green;Orange;Red"
                or query["parameters"]["fromDate"] != QUERY_START
                or query["parameters"]["toDate"] != QUERY_END):
            raise ValueError("Frozen GDACS catalogue does not have the required complete query provenance")
    else:
        events, query = query_events(cache)
        (CACHE/"events_catalogue.json").write_text(json.dumps({"type": "FeatureCollection",
            "features": events, "query": query}, sort_keys=True), encoding="utf-8")
    if not events:
        raise SystemExit("GDACS query unexpectedly returned no Malaysian flood events")
    def fetch(event):
        props = event["properties"]
        if props.get("eventtype") != "FL" or not any(c.get("iso3") == "MYS" for c in props.get("affectedcountries", [])):
            raise ValueError("Unexpected non-Malaysian flood event")
        geometry = cache.get(props["url"]["geometry"])
        details = cache.get(props["url"]["details"])
        return {"event": event, "geometry": geometry, "details": details}
    # Fail the run before upload if any source fails; missing reports must not
    # be silently turned into no matching reports.
    with ThreadPoolExecutor(max_workers=4) as pool:
        payloads = list(pool.map(fetch, events))
    reports = [r for p in payloads for r in prepare_reports(p["event"], p["geometry"], p["details"])]
    payload = {"query_start": QUERY_START, "query_end": QUERY_END, "country": "Malaysia", "query": query,
               "alert_levels": ["Green", "Orange", "Red"], "payloads": payloads,
               "naive_availability_delay_hours": 24, "geometry_class": "Poly_Affected"}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    (CACHE/"source_snapshot.json").write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    anchors = load_anchors(args.anchors_json)
    fetched_at = datetime.now(UTC).isoformat()
    rows = [aggregate_anchor(a, reports, fingerprint, fetched_at) for a in anchors]
    (CACHE/"reported_flood_context_by_anchor.jsonl").write_text(
        "".join(json.dumps(r)+"\n" for r in rows), encoding="utf-8")
    counts_by_year = {year: {"anchors": sum(r["anchor_date"].startswith(year) for r in rows),
        "matched_anchors": sum(r["anchor_date"].startswith(year) and r["gdacs_status"] == "reported_region_match" for r in rows)}
        for year in sorted({r["anchor_date"][:4] for r in rows})}
    receipt = {"source": API, "source_sha256": fingerprint, "events": len(events), "query": query,
               "affected_polygons": len(reports), "anchors": len(rows), "coverage_by_year": counts_by_year,
               "downloaded_bytes": cache.downloaded, "fetched_at": fetched_at,
               "availability_proxy": "current modification and insertion timestamps plus 24h when timezone absent",
               "reported_regions_not_observed_inundation": True, "errors": []}
    (CACHE/"receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2), flush=True)
    if args.upload:
        upload(rows)


if __name__ == "__main__":
    main()
