"""Integrity validation for an executable embedded in a Tailkitty platform wheel."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .constants import TAILCAT_MODULE, TAILCAT_VERSION


class BundleError(RuntimeError):
    """A bundled executable or its manifest is missing or invalid."""


MAX_BUNDLE_SIZE = 100 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class BundleManifest:
    schema: int
    target: str
    wheel_platform: str
    filename: str
    sha256: str
    size: int
    tailcat_module: str
    tailcat_version: str
    go_version: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> BundleManifest:
        try:
            manifest = cls(
                schema=int(value["schema"]),
                target=str(value["target"]),
                wheel_platform=str(value["wheel_platform"]),
                filename=str(value["filename"]),
                sha256=str(value["sha256"]),
                size=int(value["size"]),
                tailcat_module=str(value["tailcat_module"]),
                tailcat_version=str(value["tailcat_version"]),
                go_version=str(value["go_version"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BundleError(f"invalid bundle manifest: {exc}") from exc
        if manifest.schema != 1:
            raise BundleError(f"unsupported bundle manifest schema {manifest.schema}")
        if manifest.tailcat_version != TAILCAT_VERSION:
            raise BundleError(
                f"bundle contains Tailcat {manifest.tailcat_version}, expected {TAILCAT_VERSION}"
            )
        if manifest.tailcat_module != TAILCAT_MODULE:
            raise BundleError(f"bundle contains unexpected module {manifest.tailcat_module!r}")
        if Path(manifest.filename).name != manifest.filename:
            raise BundleError("bundle manifest filename must not contain a path")
        if len(manifest.sha256) != 64 or any(
            character not in "0123456789abcdef" for character in manifest.sha256
        ):
            raise BundleError("bundle manifest contains an invalid SHA-256 digest")
        if manifest.size <= 0 or manifest.size > MAX_BUNDLE_SIZE:
            raise BundleError("bundle manifest contains an invalid executable size")
        return manifest


@dataclass(frozen=True, slots=True)
class VerifiedBundle:
    executable: Path
    manifest: BundleManifest


def runtime_target() -> str:
    """Return the bundle target name compatible with this interpreter."""
    system = {"darwin": "macos", "linux": "linux", "win32": "windows"}.get(sys.platform)
    machine = platform.machine().lower()
    architecture = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "arm64",
        "aarch64": "aarch64" if system == "linux" else "arm64",
    }.get(machine)
    if system is None or architecture is None:
        raise BundleError(f"unsupported runtime platform: {sys.platform}/{platform.machine()}")
    return f"{system}-{architecture}"


def bundle_directory() -> Path:
    return Path(__file__).resolve().parent / "bin"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=4)
def verify_bundle(directory: Path | None = None) -> VerifiedBundle | None:
    root = directory or bundle_directory()
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleError(f"cannot read bundle manifest: {exc}") from exc
    if not isinstance(raw, dict):
        raise BundleError("bundle manifest must contain a JSON object")
    manifest = BundleManifest.from_dict(raw)
    expected_target = runtime_target()
    if manifest.target != expected_target:
        raise BundleError(
            f"bundle target {manifest.target!r} is incompatible with runtime {expected_target!r}"
        )
    executable = root / manifest.filename
    if executable.is_symlink():
        raise BundleError("bundled executable must not be a symbolic link")
    if not executable.is_file():
        raise BundleError(f"bundled executable is missing: {executable}")
    if executable.stat().st_size != manifest.size:
        raise BundleError("bundled executable size does not match its manifest")
    if _sha256(executable) != manifest.sha256:
        raise BundleError("bundled executable checksum does not match its manifest")
    if os.name != "nt" and not os.access(executable, os.X_OK):
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return VerifiedBundle(executable, manifest)


def clear_bundle_cache() -> None:
    verify_bundle.cache_clear()
