"""Discovery and execution of Tailcat's Go data-plane helper."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from .bundle import BundleError, BundleManifest, verify_bundle


class BackendNotFound(RuntimeError):
    """No usable Tailcat data-plane executable was found."""


@dataclass(frozen=True, slots=True)
class BackendInfo:
    path: Path
    source: str
    manifest: BundleManifest | None = None


def project_backend() -> Path:
    return Path(__file__).resolve().parents[2] / ".tools" / "bin" / "tailcat"


def inspect_backend() -> BackendInfo:
    configured = os.environ.get("TAILKITTY_BACKEND")
    if configured:
        path = Path(configured).expanduser().resolve()
        if _is_executable(path):
            return BackendInfo(path, "environment")
        raise BackendNotFound(f"TAILKITTY_BACKEND is not executable: {path}")
    bundle = verify_bundle()
    if bundle is not None:
        return BackendInfo(bundle.executable, "bundle", bundle.manifest)
    development = project_backend()
    if _is_executable(development):
        return BackendInfo(development, "development")
    legacy_development = development.with_name("tailcat-go")
    if _is_executable(legacy_development):
        return BackendInfo(legacy_development, "development")
    if candidate := shutil.which("tailcat-go"):
        return BackendInfo(Path(candidate).resolve(), "path")
    raise BackendNotFound(
        "Tailcat data-plane backend is not installed. Run `mise run backend`, "
        "or set TAILKITTY_BACKEND to an upstream tailcat executable."
    )


def _is_executable(path: Path) -> bool:
    return path.is_file() and (os.name == "nt" or os.access(path, os.X_OK))


def find_backend() -> str:
    try:
        return str(inspect_backend().path)
    except BundleError as exc:
        raise BackendNotFound(f"bundled Tailcat executable failed integrity checks: {exc}") from exc


def exec_backend(arguments: Sequence[str]) -> NoReturn:
    backend = find_backend()
    if os.name == "posix":
        os.execv(backend, [backend, *arguments])
    completed = subprocess.run([backend, *arguments], check=False)
    raise SystemExit(completed.returncode)


def backend_version() -> str:
    info = inspect_backend()
    if info.manifest is not None:
        return info.manifest.tailcat_version
    return "unknown (external executable)"


def run(
    arguments: Sequence[str],
    *,
    input: str | bytes | None = None,
    capture_output: bool = False,
    text: bool | None = None,
    check: bool = False,
    timeout: float | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run an upstream-compatible Tailcat command.

    This deliberately follows :func:`subprocess.run` conventions. ``text`` is
    inferred from the input type when omitted, avoiding the common bytes/text
    mismatch in thin process wrappers.
    """
    if text is None:
        text = not isinstance(input, bytes)
    return subprocess.run(
        [find_backend(), *arguments],
        input=input,
        capture_output=capture_output,
        text=text,
        check=check,
        timeout=timeout,
        **kwargs,
    )
