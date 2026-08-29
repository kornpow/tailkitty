"""DERP-map fetching with revalidation and stale-cache fallback."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DERP_MAP_URL = "https://tailcat.dev/derpmap.json"
DEFAULT_MAX_AGE = 60 * 60
MAX_DERP_MAP_BYTES = 5 * 1024 * 1024


class DerpMapError(RuntimeError):
    """A DERP map could not be loaded or validated."""


def default_cache_dir() -> Path:
    if value := os.environ.get("XDG_CACHE_HOME"):
        return Path(value) / "tailkitty"
    if os.name == "nt" and (value := os.environ.get("LOCALAPPDATA")):
        return Path(value) / "tailkitty" / "Cache"
    if sys_platform() == "darwin":
        return Path.home() / "Library" / "Caches" / "tailkitty"
    return Path.home() / ".cache" / "tailkitty"


def sys_platform() -> str:
    # Kept behind a function to make platform-specific paths easy to test.
    import sys

    return sys.platform


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    data: bytes
    etag: str
    stored_at: float


class DerpMapCache:
    """Small on-disk HTTP cache following upstream Tailcat's freshness rules."""

    def __init__(self, directory: str | Path | None = None, *, max_age: float = DEFAULT_MAX_AGE):
        self.directory = Path(directory) if directory is not None else default_cache_dir()
        self.max_age = max_age

    def fetch(self, url: str = DEFAULT_DERP_MAP_URL, *, timeout: float = 10.0) -> dict[str, Any]:
        entry = self._read(url)
        now = time.time()
        if entry is not None and now - entry.stored_at < self.max_age:
            return _decode_map(entry.data)

        headers = {"Accept": "application/json", "User-Agent": "tailkitty/0.1"}
        if entry is not None and entry.etag:
            headers["If-None-Match"] = entry.etag
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read(MAX_DERP_MAP_BYTES + 1)
                if len(data) > MAX_DERP_MAP_BYTES:
                    raise DerpMapError("DERP map exceeds the 5 MiB safety limit")
                result = _decode_map(data)
                self._write(url, data, response.headers.get("ETag", ""), now)
                return result
        except urllib.error.HTTPError as exc:
            if exc.code == 304 and entry is not None:
                self._write(url, entry.data, entry.etag, now)
                return _decode_map(entry.data)
            if entry is not None:
                return _decode_map(entry.data)
            raise DerpMapError(f"fetching DERP map returned HTTP {exc.code}") from exc
        except (OSError, ValueError, json.JSONDecodeError, DerpMapError) as exc:
            if entry is not None:
                return _decode_map(entry.data)
            raise DerpMapError(f"could not fetch DERP map: {exc}") from exc

    def _paths(self, url: str) -> tuple[Path, Path]:
        key = hashlib.sha256(url.encode()).hexdigest()
        return self.directory / f"{key}.json", self.directory / f"{key}.meta.json"

    def _read(self, url: str) -> _CacheEntry | None:
        data_path, metadata_path = self._paths(url)
        try:
            data = data_path.read_bytes()
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            _decode_map(data)
            return _CacheEntry(
                data=data,
                etag=str(metadata.get("etag", "")),
                stored_at=float(metadata["stored_at"]),
            )
        except (
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            DerpMapError,
        ):
            return None

    def _write(self, url: str, data: bytes, etag: str, stored_at: float) -> None:
        data_path, metadata_path = self._paths(url)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        _atomic_write(data_path, data)
        metadata = json.dumps({"etag": etag, "stored_at": stored_at}).encode()
        _atomic_write(metadata_path, metadata)


def _atomic_write(path: Path, data: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _decode_map(data: bytes) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except json.JSONDecodeError as exc:
        raise DerpMapError(f"DERP map is not valid JSON: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("Regions"), dict):
        raise DerpMapError("DERP map must contain a Regions object")
    return value
