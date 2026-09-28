"""Reported-region geometry and conservative publication-time checks."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, urlparse

import pytest

from scripts import fetch_gdacs_flood_context as gdacs
from scripts import fetch_flood_context as gfm


POLYGON = {"type": "Polygon", "coordinates": [[[100., 2.], [102., 2.],
    [102., 4.], [100., 4.], [100., 2.]]]}


def anchor():
    return {"population": "callback", "sales_record_id": "synthetic-package",
            "anchor_date": "2026-01-10", "latitude": 3., "longitude": 101.}


def report(day, eventid=1, available="2026-01-08T00:00:00+00:00"):
    return {"eventid": eventid, "episodeid": 1, "event_at": day+"T03:00:00+00:00",
            "available_at": available, "geometry": POLYGON}


def test_timezone_naive_publication_is_delayed_one_day_but_aware_time_is_exact():
    assert gdacs.source_timestamp("2026-01-08T03:00:00", availability=True) == datetime(2026, 1, 9, 3, tzinfo=timezone.utc)
    assert gdacs.source_timestamp("2026-01-08T03:00:00+00:00", availability=True) == datetime(2026, 1, 8, 3, tzinfo=timezone.utc)
    assert gdacs.source_timestamp("2026-01-08T03:00:00") == datetime(2026, 1, 8, 3, tzinfo=timezone.utc)


def test_polygon_holes_multipolygons_and_boundary_are_handled():
    assert gdacs.point_in_geometry(101., 3., POLYGON)
    assert gdacs.point_in_geometry(100., 3., POLYGON)
    assert not gdacs.point_in_geometry(99., 3., POLYGON)
    holed = deepcopy(POLYGON)
    holed["coordinates"].append([[100.5, 2.5], [101.5, 2.5], [101.5, 3.5], [100.5, 3.5], [100.5, 2.5]])
    assert not gdacs.point_in_geometry(101., 3., holed)
    assert gdacs.point_in_geometry(100.25, 3., holed)
    multi = {"type": "MultiPolygon", "coordinates": [holed["coordinates"], POLYGON["coordinates"]]}
    assert gdacs.point_in_geometry(101., 3., multi)
    assert not gdacs.point_in_geometry(101., 3., {"type": "Point", "coordinates": [101., 3.]})


def test_report_preparation_uses_latest_metadata_not_backdated_polygon_date():
    event = {"properties": {"eventid": 1, "episodeid": 1, "datemodified": "2026-01-08T00:00:00"}}
    props = {**event["properties"], "Class": "Poly_Affected", "polygondate": "2025-12-25T00:00:00"}
    geometry = {"features": [{"properties": props, "geometry": POLYGON},
        {"properties": {**props, "Class": "Poly_Global"}, "geometry": POLYGON}]}
    details = {"properties": {**event["properties"], "sendai": [{"dateinsert": "2026-01-08T02:00:00"}]}}
    reports = gdacs.prepare_reports(event, geometry, details)
    assert len(reports) == 1
    assert reports[0]["available_at"] == "2026-01-09T02:00:00+00:00"
    assert reports[0]["event_at"] == "2025-12-25T00:00:00+00:00"
    geometry["features"][0]["properties"]["episodeid"] = 2
    with pytest.raises(ValueError, match="key mismatch"):
        gdacs.prepare_reports(event, geometry, details)


def test_report_counts_deduplicate_event_and_preserve_nested_windows():
    reports = [report("2026-01-09", 1), report("2026-01-09", 1),
               report("2026-01-01", 2), report("2025-12-20", 3)]
    row = gdacs.aggregate_anchor(anchor(), reports, "a"*64, "2026-01-12T00:00:00Z")
    assert [row[f"gdacs_prior_{d}d_reported_events"] for d in (7, 14, 30)] == [1, 2, 3]
    assert row["gdacs_days_since_reported_event_capped_30d"] == 1
    assert row["gdacs_status"] == "reported_region_match"


def test_future_publication_and_same_local_day_are_excluded():
    reports = [report("2026-01-09", available="2026-01-09T16:00:00+00:00"),
               report("2026-01-10", 2)]
    row = gdacs.aggregate_anchor(anchor(), reports, "a"*64, "2026-01-12T00:00:00Z")
    assert row["gdacs_prior_30d_reported_events"] == 0
    assert row["gdacs_days_since_reported_event_capped_30d"] == 30
    assert row["gdacs_status"] == "no_matching_recorded_report"
    assert row["gdacs_last_report_available_at"] is None


def test_missing_coordinates_and_incomplete_query_period_stay_unknown():
    missing = anchor()
    missing["latitude"] = None
    row = gdacs.aggregate_anchor(missing, [], "a"*64, "2026-01-12T00:00:00Z")
    assert row["gdacs_status"] == "unknown_missing_location"
    assert all(row[name] is None for name in gdacs.NUMERIC)
    early = anchor()
    early["anchor_date"] = "2024-01-15"
    row = gdacs.aggregate_anchor(early, [], "a"*64, "2026-01-12T00:00:00Z")
    assert row["gdacs_status"] == "unknown_outside_query_period"
    assert all(row[name] is None for name in gdacs.NUMERIC)


def test_unapproved_source_url_is_rejected_without_network(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("Network should not be called")
    monkeypatch.setattr(gdacs.requests, "get", forbidden)
    cache = gdacs.PublicCache(tmp_path)
    with pytest.raises(ValueError, match="Unapproved"):
        cache.get("https://private.invalid/data.json")


def test_short_catalogue_page_still_checks_next_page_and_records_exact_query():
    calls = []
    class Cache:
        def get(self, url):
            params = parse_qs(urlparse(url).query)
            calls.append(params)
            number = int(params["pageNumber"][0])
            return {"type": "FeatureCollection", "features": (
                [{"properties": {"eventtype": "FL", "eventid": 1}}] if number == 1 else []),
                "_http_status": 200 if number == 1 else 204}
    events, query = gdacs.query_events(Cache())
    assert len(events) == 1
    assert len(calls) == 2
    assert calls[0]["country"] == ["Malaysia"]
    assert calls[0]["alertlevel"] == ["Green;Orange;Red"]
    assert query["completed_by_empty_page"]
    assert query["pages"][-1]["http_status"] == 204


def test_repeated_catalogue_page_is_rejected_instead_of_claiming_complete_coverage():
    class Cache:
        def get(self, url):
            return {"type": "FeatureCollection", "features": [{"properties": {"eventtype": "FL", "eventid": 1}}]}
    with pytest.raises(ValueError, match="pagination"):
        gdacs.query_events(Cache())


def test_http_204_is_a_verified_empty_catalogue_page_and_cached(tmp_path, monkeypatch):
    class Response:
        status_code = 204
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def raise_for_status(self): pass
        def iter_content(self, *args): raise AssertionError("204 has no JSON body")
    calls = []
    monkeypatch.setattr(gdacs.requests, "get", lambda url, **kwargs: calls.append(url) or Response())
    cache = gdacs.PublicCache(tmp_path)
    url = gdacs.API+"Events/geteventlist/search?pageNumber=2"
    assert cache.get(url) == {"type": "FeatureCollection", "features": [], "_http_status": 204}
    assert cache.get(url)["features"] == []
    assert len(calls) == 1


def test_default_anchors_use_same_bounded_bigquery_reader(monkeypatch):
    calls = []
    expected = [anchor()]
    monkeypatch.setattr(gfm, "read_anchors", lambda: calls.append("query") or expected)
    assert gdacs.load_anchors() == expected
    assert calls == ["query"]


def test_frozen_anchors_replay_without_bigquery(tmp_path, monkeypatch):
    path = tmp_path / "anchors.json"
    path.write_text(json.dumps([anchor()]), encoding="utf-8")
    def forbidden(): raise AssertionError("Frozen replay must not query BigQuery")
    monkeypatch.setattr(gfm, "read_anchors", forbidden)
    assert gdacs.load_anchors(path) == [anchor()]


def test_cli_help_does_not_require_ignored_frozen_input_files():
    path = Path(__file__).resolve().parents[1] / "scripts/fetch_gdacs_flood_context.py"
    result = subprocess.run([sys.executable, str(path), "--help"], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0
    assert "default reads the bounded BigQuery source" in " ".join(result.stdout.split())
