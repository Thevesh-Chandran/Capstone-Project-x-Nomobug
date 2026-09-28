"""Offline checks for bounded COG reading and land-cover missing-data semantics."""

import io
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_worldcover_context as worldcover


def test_tile_selection_handles_grid_boundary():
    assert worldcover.tile_name(2.99999, 101.9) == "N00E099"
    assert worldcover.tile_name(3.0, 102.0) == "N03E102"
    assert worldcover.tile_name(-0.1, -0.1) == "S03W003"


def test_unmapped_pixels_produce_null_features_not_zero_absence():
    complete = worldcover.summarize_pixels(np.array([10, 50, 80, 95]), np.zeros(4), 250)
    assert complete["worldcover_available_250m"]
    assert complete["worldcover_tree_fraction_250m"] == 0.25
    assert complete["worldcover_wetland_fraction_250m"] == 0.25
    assert complete["worldcover_grass_fraction_250m"] == 0.0
    partial = worldcover.summarize_pixels(np.array([0, 0, 80, 10]), np.zeros(4), 250)
    assert partial["worldcover_valid_fraction_250m"] == 0.5
    assert not partial["worldcover_available_250m"]
    assert partial["worldcover_water_fraction_250m"] is None


def test_range_cache_limits_network_and_supports_repeated_random_access(tmp_path, monkeypatch):
    payload = bytes(range(256)) * 600
    requests = []

    class Response(io.BytesIO):
        def __init__(self, body, status, headers):
            super().__init__(body)
            self.status = status
            self.headers = headers

    def fake_urlopen(request, **kwargs):
        requests.append(request)
        if request.get_method() == "HEAD":
            return Response(b"", 200, {"Accept-Ranges": "bytes", "Content-Length": str(len(payload))})
        byte_range = request.headers["Range"].split("=", 1)[1]
        start, end = map(int, byte_range.split("-"))
        return Response(payload[start:end + 1], 206,
                        {"Content-Range": f"bytes {start}-{end}/{len(payload)}"})

    monkeypatch.setattr(worldcover, "urlopen", fake_urlopen)
    budget = worldcover.NetworkBudget(worldcover.BLOCK_BYTES)
    with worldcover.RangeFile("https://public.invalid/test.tif", tmp_path, budget) as reader:
        reader.seek(20)
        assert reader.read(15) == payload[20:35]
        reader.seek(30)
        assert reader.read(25) == payload[30:55]
        assert budget.downloaded == worldcover.BLOCK_BYTES
        reader.seek(worldcover.BLOCK_BYTES + 1)
        with pytest.raises(worldcover.BudgetExceeded):
            reader.read(1)
    assert len(requests) == 2  # One HEAD and one range GET, despite random seeks.


def test_custom_raster_opener_reads_cached_tiff_without_full_download(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    values = np.full((16, 16), 50, dtype="uint8")
    with MemoryFile() as memory:
        with memory.open(driver="GTiff", height=16, width=16, count=1,
                         dtype="uint8", crs="EPSG:4326",
                         transform=from_origin(100, 3, 0.01, 0.01)) as writer:
            writer.write(values, 1)
        payload = memory.read()
    url = "https://public.invalid/cached.tif"
    cache = tmp_path / worldcover.hashlib.sha256(url.encode()).hexdigest()[:20]
    cache.mkdir()
    (cache / "metadata.json").write_text(json.dumps({"url": url, "size": len(payload)}))
    assert len(payload) < worldcover.BLOCK_BYTES
    (cache / "00000000.bin").write_bytes(payload)
    budget = worldcover.NetworkBudget(1)

    def opener(path, mode="rb"):
        if path != "cached.tif":
            raise FileNotFoundError(path)
        return worldcover.RangeFile(url, tmp_path, budget)

    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open("cached.tif", driver="GTiff", opener=opener) as reader:
            assert reader.read(1).tolist() == values.tolist()
    assert budget.downloaded == 0
