"""Structured Tailkitty runtime diagnostics."""

from __future__ import annotations

import os
import platform
import sys
from typing import Any

from .backend import inspect_backend
from .constants import TAILKITTY_VERSION


def diagnostics() -> dict[str, Any]:
    info = inspect_backend()
    result: dict[str, Any] = {
        "tailkitty_version": TAILKITTY_VERSION,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": sys.platform,
        "machine": platform.machine(),
        "backend": {
            "path": str(info.path),
            "source": info.source,
            "executable": os.access(info.path, os.X_OK),
        },
    }
    if manifest := info.manifest:
        result["backend"]["bundle"] = {
            "target": manifest.target,
            "wheel_platform": manifest.wheel_platform,
            "sha256": manifest.sha256,
            "size": manifest.size,
            "tailcat_version": manifest.tailcat_version,
            "go_version": manifest.go_version,
            "verified": True,
        }
    return result
