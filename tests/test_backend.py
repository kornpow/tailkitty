from __future__ import annotations

import stat
from pathlib import Path

import pytest

from tailkitty import backend
from tailkitty.backend import BackendNotFound
from tailkitty.bundle import BundleError


def executable(path: Path) -> Path:
    path.write_bytes(b"backend")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return path


def test_environment_backend_has_highest_priority(tmp_path, monkeypatch) -> None:
    configured = executable(tmp_path / "configured")
    monkeypatch.setenv("TAILKITTY_BACKEND", str(configured))
    monkeypatch.setattr(backend, "verify_bundle", lambda: pytest.fail("bundle checked first"))
    info = backend.inspect_backend()
    assert info.path == configured
    assert info.source == "environment"


def test_invalid_environment_backend_fails_closed(tmp_path, monkeypatch) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setenv("TAILKITTY_BACKEND", str(missing))
    with pytest.raises(BackendNotFound, match="not executable"):
        backend.inspect_backend()


def test_development_backend_follows_absent_bundle(tmp_path, monkeypatch) -> None:
    development = executable(tmp_path / "tailcat")
    monkeypatch.delenv("TAILKITTY_BACKEND", raising=False)
    monkeypatch.setattr(backend, "verify_bundle", lambda: None)
    monkeypatch.setattr(backend, "project_backend", lambda: development)
    info = backend.inspect_backend()
    assert info.path == development
    assert info.source == "development"


def test_find_backend_explains_corrupt_bundle(monkeypatch) -> None:
    monkeypatch.delenv("TAILKITTY_BACKEND", raising=False)

    def corrupt_bundle():
        raise BundleError("checksum mismatch")

    monkeypatch.setattr(backend, "verify_bundle", corrupt_bundle)
    with pytest.raises(BackendNotFound, match="integrity checks: checksum mismatch"):
        backend.find_backend()
