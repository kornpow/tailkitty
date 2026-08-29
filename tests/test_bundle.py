from __future__ import annotations

import hashlib
import json
import stat

import pytest

from tailkitty.bundle import BundleError, clear_bundle_cache, runtime_target, verify_bundle
from tailkitty.constants import TAILCAT_MODULE, TAILCAT_VERSION


def make_bundle(tmp_path, data: bytes = b"\x7fELF" + b"x" * 32):
    target = runtime_target()
    filename = "tailcat.exe" if target.startswith("windows-") else "tailcat"
    binary = tmp_path / filename
    binary.write_bytes(data)
    binary.chmod(stat.S_IRUSR | stat.S_IWUSR)
    manifest = {
        "schema": 1,
        "target": target,
        "wheel_platform": "test_platform",
        "filename": filename,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "tailcat_module": TAILCAT_MODULE,
        "tailcat_version": TAILCAT_VERSION,
        "go_version": "go version go1.26.5 linux/amd64",
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    clear_bundle_cache()
    return binary, manifest


def test_verified_bundle_and_execute_bit_recovery(tmp_path) -> None:
    binary, manifest = make_bundle(tmp_path)
    result = verify_bundle(tmp_path)
    assert result is not None
    assert result.executable == binary
    assert result.manifest.sha256 == manifest["sha256"]
    assert binary.stat().st_mode & stat.S_IXUSR


def test_missing_manifest_means_no_bundle(tmp_path) -> None:
    clear_bundle_cache()
    assert verify_bundle(tmp_path) is None


def test_corrupt_bundle_is_rejected(tmp_path) -> None:
    binary, _ = make_bundle(tmp_path)
    binary.write_bytes(b"corrupt")
    clear_bundle_cache()
    with pytest.raises(BundleError, match="size does not match"):
        verify_bundle(tmp_path)


def test_manifest_cannot_escape_bundle_directory(tmp_path) -> None:
    _, manifest = make_bundle(tmp_path)
    manifest["filename"] = "../tailcat"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    clear_bundle_cache()
    with pytest.raises(BundleError, match="must not contain a path"):
        verify_bundle(tmp_path)


def test_bundle_for_another_platform_is_rejected(tmp_path) -> None:
    _, manifest = make_bundle(tmp_path)
    manifest["target"] = (
        "windows-x86_64" if runtime_target() != "windows-x86_64" else "linux-x86_64"
    )
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    clear_bundle_cache()
    with pytest.raises(BundleError, match="incompatible with runtime"):
        verify_bundle(tmp_path)


def test_manifest_rejects_non_hex_digest(tmp_path) -> None:
    _, manifest = make_bundle(tmp_path)
    manifest["sha256"] = "z" * 64
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    clear_bundle_cache()
    with pytest.raises(BundleError, match="invalid SHA-256"):
        verify_bundle(tmp_path)


def test_manifest_rejects_unexpected_module(tmp_path) -> None:
    _, manifest = make_bundle(tmp_path)
    manifest["tailcat_module"] = "example.invalid/tailcat"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    clear_bundle_cache()
    with pytest.raises(BundleError, match="unexpected module"):
        verify_bundle(tmp_path)


def test_bundle_rejects_symlinked_executable(tmp_path) -> None:
    binary, _ = make_bundle(tmp_path)
    real_binary = tmp_path / "real-tailcat"
    binary.replace(real_binary)
    binary.symlink_to(real_binary)
    clear_bundle_cache()
    with pytest.raises(BundleError, match="symbolic link"):
        verify_bundle(tmp_path)


def test_manifest_rejects_oversized_bundle(tmp_path) -> None:
    _, manifest = make_bundle(tmp_path)
    manifest["size"] = 101 * 1024 * 1024
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    clear_bundle_cache()
    with pytest.raises(BundleError, match="invalid executable size"):
        verify_bundle(tmp_path)
