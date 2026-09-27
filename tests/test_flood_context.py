"""Offline checks for publication-gated flood exposure and unknown-data semantics."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window

from scripts import fetch_flood_context as flood


def scene(sensed="2026-01-09T03:00:00Z", created="2026-01-09T05:00:00Z",
          processed="2026-01-09T04:00:00Z"):
    return {"id": "test-scene", "properties": {
        "datetime": sensed, "created": created, "processing:datetime": processed,
        "flood_members": {"DLR": True, "TUW": True, "LIST": True},
        "proj:bbox": [0, 0, 10000, 10000], "proj:wkt2": "EPSG:32647"},
        "assets": {name: {"href": f"https://data.eodc.eu/collections/GFM/{name}.tif"}
                   for name in flood.ASSETS}}


def anchor():
    return {"population": "callback", "sales_record_id": "synthetic-package",
            "anchor_date": "2026-01-10", "_point_id": 0,
            "_date": datetime(2026, 1, 10).date(),
            "_midnight": datetime(2026, 1, 10, tzinfo=flood.MYT)}


def test_time_gate_uses_malaysian_midnight_and_requires_both_publication_timestamps():
    assert flood.prior_observation(scene(), "2026-01-10")
    # UTC 16:00 is the next local day's midnight, even though its UTC date is prior.
    assert not flood.prior_observation(scene(created="2026-01-09T16:00:00Z"), "2026-01-10")
    assert not flood.prior_observation(scene(processed="2026-01-09T16:00:00Z"), "2026-01-10")
    assert not flood.prior_observation(scene(sensed="2026-01-09T16:01:00Z"), "2026-01-10")
    with pytest.raises(ValueError, match="timezone"):
        flood.parse_time("2026-01-09T03:00:00")


def test_lookback_includes_day_30_but_excludes_day_31_and_same_day():
    assert flood.prior_observation(scene(sensed="2025-12-11T03:00:00Z"), "2026-01-10")
    assert not flood.prior_observation(scene(sensed="2025-12-10T03:00:00Z"), "2026-01-10")
    assert not flood.prior_observation(scene(sensed="2026-01-10T03:00:00Z"), "2026-01-10")


def test_quality_masks_do_not_encode_excluded_normal_water_or_flagged_pixels_as_dry():
    observed = np.array([1, 0, 1, 1, 1, 255, 2, 1])
    exclusion = np.array([0, 0, 1, 0, 0, 0, 0, 0])
    reference = np.array([0, 0, 0, 1, 0, 0, 0, 0])
    advisory = np.array([0, 0, 0, 0, 2, 0, 0, 0])
    circle = np.array([True] * 7 + [False])
    fraction, valid = flood.buffer_statistics(observed, exclusion, reference, advisory, circle)
    assert fraction is None  # Only two of seven intended pixels are reliable.
    assert valid == pytest.approx(2 / 7)


def test_observed_zero_is_distinct_from_no_reliable_observation():
    zeros = np.zeros(10, dtype=np.uint8)
    circle = np.ones(10, dtype=bool)
    assert flood.buffer_statistics(zeros, zeros, zeros, zeros, circle) == (0.0, 1.0)
    assert flood.buffer_statistics(zeros, np.ones(10), zeros, zeros, circle) == (None, 0.0)
    assert flood.buffer_statistics(np.full(10, 255), zeros, zeros, zeros, circle) == (None, 0.0)


def test_fraction_denominator_uses_reliable_pixels_and_full_buffer_coverage_threshold():
    values = np.array([1, 1, 0, 0, 0, 255, 255, 255, 255, 255])
    zeros = np.zeros(10)
    circle = np.ones(10, dtype=bool)
    assert flood.buffer_statistics(values, zeros, zeros, zeros, circle) == (0.4, 0.5)
    values[4] = 255
    assert flood.buffer_statistics(values, zeros, zeros, zeros, circle) == (None, 0.4)


def test_aggregation_windows_count_observed_dates_once_and_ignore_unavailable_scenes():
    inputs = [(scene("2026-01-09T03:00:00Z"), {"fraction": .1, "valid_fraction": .8}),
              (scene("2026-01-09T05:00:00Z"), {"fraction": .2, "valid_fraction": .9}),
              (scene("2026-01-01T03:00:00Z"), {"fraction": .4, "valid_fraction": .6}),
              (scene("2025-12-20T03:00:00Z"), {"fraction": .5, "valid_fraction": .7}),
              (scene(created="2026-01-11T03:00:00Z"), {"fraction": 1., "valid_fraction": 1.}),
              (scene(), {"fraction": None, "valid_fraction": .3})]
    row = flood.aggregate_anchor(anchor(), inputs, "a" * 64, "2026-01-12T00:00:00Z")
    assert row["gfm_prior_7d_max_flood_fraction_1km"] == .2
    assert row["gfm_prior_14d_max_flood_fraction_1km"] == .4
    assert row["gfm_prior_30d_max_flood_fraction_1km"] == .5
    assert row["gfm_prior_30d_observed_days"] == 3
    assert row["gfm_prior_30d_flood_detected_days"] == 3
    assert row["gfm_days_since_detected_flood_capped_30d"] == 1
    assert row["gfm_prior_30d_max_valid_fraction_1km"] == .9
    assert len(row["flood_anchor_id"]) == 64


def test_unobserved_anchor_keeps_flood_fraction_and_recency_unknown():
    row = flood.aggregate_anchor(anchor(), [(scene(), {"fraction": None, "valid_fraction": .4})],
                                 "a" * 64, "2026-01-12T00:00:00Z")
    assert row["gfm_prior_30d_observed_days"] == 0
    assert row["gfm_prior_30d_flood_detected_days"] == 0
    for name in flood.FEATURES:
        if "days" not in name or "since" in name:
            assert row[name] is None
    assert row["gfm_last_observation_at"] is None
    assert row["gfm_last_available_at"] is None


def test_observed_dry_context_has_zero_detections_and_censored_recency():
    row = flood.aggregate_anchor(anchor(), [(scene(), {"fraction": 0., "valid_fraction": .8})],
                                 "a" * 64, "2026-01-12T00:00:00Z")
    assert row["gfm_prior_30d_observed_days"] == 1
    assert row["gfm_prior_30d_flood_detected_days"] == 0
    assert row["gfm_days_since_detected_flood_capped_30d"] == 30
    assert row["gfm_days_since_valid_observation"] == 1
    assert row["gfm_prior_30d_max_flood_fraction_1km"] == 0.


def test_download_cache_rejects_unapproved_urls_without_network(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network should not be called")
    monkeypatch.setattr(flood.requests, "get", forbidden)
    cache = flood.DownloadCache(tmp_path, 10)
    for url in ("http://data.eodc.eu/collections/GFM/test.tif",
                "https://private.invalid/collections/GFM/test.tif",
                "https://data.eodc.eu/not-gfm/test.tif"):
        with pytest.raises(ValueError, match="Unapproved"):
            cache.get(url)


def test_download_cache_respects_global_budget_and_reuses_exact_url(tmp_path, monkeypatch):
    class Response:
        headers = {"Content-Length": "8", "ETag": "fixture"}
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def raise_for_status(self): pass
        def iter_content(self, *args): return iter([b"1234", b"5678"])
    calls = []
    monkeypatch.setattr(flood.requests, "get", lambda url, **kwargs: calls.append(url) or Response())
    cache = flood.DownloadCache(tmp_path, 10)
    url = "https://data.eodc.eu/collections/GFM/test.tif"
    destination = cache.get(url)
    assert destination.read_bytes() == b"12345678"
    assert cache.downloaded_bytes == 8
    assert cache.get(url) == destination
    assert len(calls) == 1
    with pytest.raises(RuntimeError, match="ceiling"):
        cache.get(url.replace("test.tif", "other.tif"))
    assert cache.downloaded_bytes == 8


def make_rasters(directory):
    paths = {}
    for name in flood.ASSETS:
        path = directory / f"{name}.tif"
        with rasterio.open(path, "w", driver="GTiff", width=500, height=500, count=1,
                           dtype="uint8", nodata=255, crs="EPSG:32647",
                           transform=from_origin(0, 10000, 20, 20)) as dataset:
            dataset.write(np.zeros((500, 500), dtype=np.uint8), 1)
        paths[name] = path
    return paths


def test_scene_cache_is_invalidated_when_coordinates_or_assets_change(tmp_path, monkeypatch):
    monkeypatch.setattr(flood, "CACHE", tmp_path)
    (tmp_path / "observations").mkdir()
    paths = make_rasters(tmp_path)
    class Cache:
        def __init__(self): self.calls = 0
        def get(self, url):
            self.calls += 1
            return paths[Path(url).stem]
    cache = Cache()
    item = scene()
    coords = [(3.0, 101.0)]
    projected = {"EPSG:32647": [(5000, 5000)]}
    first = flood.scene_observations(item, [anchor()], coords, projected, cache)
    assert first["0"] == {"fraction": 0.0, "valid_fraction": 1.0}
    assert cache.calls == 4
    assert flood.scene_observations(item, [anchor()], coords, projected, cache) == first
    assert cache.calls == 4
    flood.scene_observations(item, [anchor()], [(3.1, 101.1)], projected, cache)
    assert cache.calls == 8
    revised = deepcopy(item)
    revised["assets"]["ensemble_flood_extent"]["revision"] = "new"
    flood.scene_observations(revised, [anchor()], coords, projected, cache)
    assert cache.calls == 12


def test_single_algorithm_scene_is_not_read_or_counted_as_observed():
    item = scene()
    item["properties"]["flood_members"] = {"DLR": True, "TUW": False, "LIST": False}
    class Cache:
        def get(self, url): raise AssertionError("Single-member output must not be read")
    assert flood.scene_observations(item, [anchor()], [(3., 101.)],
                                    {"EPSG:32647": [(5000, 5000)]}, Cache()) == {}


def test_misaligned_quality_rasters_fail_instead_of_pairing_wrong_pixels(tmp_path, monkeypatch):
    monkeypatch.setattr(flood, "CACHE", tmp_path)
    (tmp_path / "observations").mkdir()
    paths = make_rasters(tmp_path)
    with rasterio.open(paths["exclusion_mask"], "r+") as dataset:
        dataset.transform = from_origin(20, 10000, 20, 20)
    class Cache:
        def get(self, url): return paths[Path(url).stem]
    with pytest.raises(ValueError, match="not aligned"):
        flood.scene_observations(scene(), [anchor()], [(3., 101.)],
                                 {"EPSG:32647": [(5000, 5000)]}, Cache())


@pytest.mark.parametrize("window", [Window(-3, -2, 8, 7), Window(7, 6, 8, 7),
                                    Window(20, -30, 8, 7)])
def test_fast_window_read_matches_boundless_rasterio_at_edges_and_outside(tmp_path, window):
    path = tmp_path / "small_flood.tif"
    values = np.arange(100, dtype=np.uint8).reshape(10, 10)
    values[1, 1] = 255  # Interior nodata must survive; it must not become a dry pixel.
    with rasterio.open(path, "w", driver="GTiff", width=10, height=10, count=1,
                       dtype="uint8", nodata=255, crs="EPSG:32647",
                       transform=from_origin(0, 200, 20, 20)) as dataset:
        dataset.write(values, 1)
    with rasterio.open(path) as dataset:
        expected = dataset.read(1, window=window, boundless=True, fill_value=255)
        actual = flood.read_buffer(dataset, window)
    np.testing.assert_array_equal(actual, expected)
    assert actual.dtype == values.dtype
    assert actual.shape == (int(window.height), int(window.width))
    assert np.any(actual == 255)


def test_failed_relevant_map_marks_partial_and_unknown_coverage_without_changing_values():
    anchors = [anchor(), anchor()]
    anchors[1]["_point_id"] = 1
    rows = [{"gfm_status": "observed_context", "gfm_prior_30d_observed_days": 1,
             "gfm_prior_30d_max_flood_fraction_1km": 0.0},
            {"gfm_status": "unknown_no_reliable_prior_observation", "gfm_prior_30d_observed_days": 0,
             "gfm_prior_30d_max_flood_fraction_1km": None}]
    affected = flood.mark_source_failures(rows, anchors, [scene()],
        {"EPSG:32647": [(5000, 5000), (6000, 6000)]}, [{"item_id": "test-scene"}])
    assert affected == 2
    assert rows[0]["gfm_status"] == "observed_context_partial_source_errors"
    assert rows[1]["gfm_status"] == "unknown_source_errors"
    assert rows[0]["gfm_prior_30d_max_flood_fraction_1km"] == 0.0
    assert rows[1]["gfm_prior_30d_max_flood_fraction_1km"] is None


@pytest.mark.parametrize("item, projected", [
    (scene(created="2026-01-11T03:00:00Z"), {"EPSG:32647": [(5000, 5000)]}),
    (scene(), {"EPSG:32647": [(15000, 15000)]})])
def test_future_publication_or_irrelevant_tile_failure_does_not_mark_anchor(item, projected):
    rows = [{"gfm_status": "observed_context", "gfm_prior_30d_observed_days": 1}]
    assert flood.mark_source_failures(rows, [anchor()], [item], projected,
                                      [{"item_id": item["id"]}]) == 0
    assert rows[0]["gfm_status"] == "observed_context"


@pytest.mark.parametrize("missing", ["exclusion_mask", "advisory_flags"])
def test_relevant_scene_missing_quality_layer_fails_before_any_download(missing):
    item = scene()
    del item["assets"][missing]
    class Cache:
        def get(self, url): raise AssertionError("Incomplete quality layers must not download")
    with pytest.raises(flood.MissingQualityLayerError, match=missing):
        flood.scene_observations(item, [anchor()], [(3., 101.)],
                                 {"EPSG:32647": [(5000, 5000)]}, Cache())


@pytest.mark.parametrize("item, projected", [
    (scene(created="2026-01-11T03:00:00Z"), {"EPSG:32647": [(5000, 5000)]}),
    (scene(), {"EPSG:32647": [(15000, 15000)]})])
def test_irrelevant_incomplete_quality_scene_skips_without_download(item, projected):
    del item["assets"]["advisory_flags"]
    class Cache:
        def get(self, url): raise AssertionError("Irrelevant scene must not download")
    assert flood.scene_observations(item, [anchor()], [(3., 101.)], projected, Cache()) == {}


def cached_catalogue(anchors, assets):
    return {"query_bbox": [anchors[0]["longitude"]-.1, anchors[0]["latitude"]-.1,
                            anchors[0]["longitude"]+.1, anchors[0]["latitude"]+.1],
            "start": "2025-12-10", "end": "2026-01-10", "requested_assets": assets,
            "features": [scene()]}


def test_complete_query_contract_reuses_catalogue_even_when_source_item_lacks_layer(tmp_path, monkeypatch):
    monkeypatch.setattr(flood, "CACHE", tmp_path)
    anchors = [{"anchor_date": "2026-01-10", "latitude": 3., "longitude": 101.}]
    payload = cached_catalogue(anchors, list(flood.ASSETS))
    del payload["features"][0]["assets"]["advisory_flags"]
    (tmp_path / "catalogue.json").write_text(json.dumps(payload))
    def forbidden(*args, **kwargs): raise AssertionError("Query contract should reuse the cached catalogue")
    monkeypatch.setattr(flood.requests, "get", forbidden)
    assert flood.catalogue(anchors) == payload


def test_old_query_contract_without_advisory_projection_is_refetched(tmp_path, monkeypatch):
    monkeypatch.setattr(flood, "CACHE", tmp_path)
    anchors = [{"anchor_date": "2026-01-10", "latitude": 3., "longitude": 101.}]
    (tmp_path / "catalogue.json").write_text(json.dumps(cached_catalogue(anchors, list(flood.ASSETS[:-1]))))
    calls = []
    class Response:
        content = b"{}"
        def raise_for_status(self): pass
        def json(self): return {"features": [], "links": []}
    monkeypatch.setattr(flood.requests, "get", lambda url, **kwargs: calls.append(kwargs) or Response())
    payload = flood.catalogue(anchors)
    assert len(calls) == 1
    assert "assets.advisory_flags" in calls[0]["params"]["fields"]
    assert payload["requested_assets"] == list(flood.ASSETS)
