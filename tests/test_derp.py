from __future__ import annotations

import json
import time
import urllib.error
from io import BytesIO

import pytest

from tailkitty.derp import DerpMapCache, DerpMapError

MAP = {"Regions": {"1": {"RegionID": 1, "Nodes": []}}}


class Response(BytesIO):
    def __init__(self, data: bytes, etag: str = "") -> None:
        super().__init__(data)
        self.headers = {"ETag": etag}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_cache_avoids_second_network_request(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fetch(request, timeout):
        nonlocal calls
        calls += 1
        return Response(json.dumps(MAP).encode(), '"v1"')

    monkeypatch.setattr("urllib.request.urlopen", fetch)
    cache = DerpMapCache(tmp_path)
    assert cache.fetch()["Regions"]["1"]["RegionID"] == 1
    assert cache.fetch() == MAP
    assert calls == 1


def test_stale_cache_is_fallback_on_network_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = DerpMapCache(tmp_path, max_age=-1)
    url = "https://example.invalid/map"
    cache._write(url, json.dumps(MAP).encode(), '"v1"', time.time() - 100)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )
    assert cache.fetch(url) == MAP


def test_invalid_uncached_map_raises(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout: Response(b'{"not": "a map"}')
    )
    with pytest.raises(DerpMapError, match="Regions"):
        DerpMapCache(tmp_path).fetch()
