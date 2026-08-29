"""Hatch hook that turns a source bundle into a correctly tagged platform wheel."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name != "wheel":
            return
        configured_bundle = os.environ.get("TAILKITTY_BUNDLE_DIR")
        bundle = (
            Path(configured_bundle).resolve()
            if configured_bundle
            else Path(self.root) / "src" / "tailkitty" / "bin"
        )
        manifest_path = bundle / "manifest.json"
        if not manifest_path.is_file():
            return
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        filename = str(manifest["filename"])
        if Path(filename).name != filename:
            raise RuntimeError("bundle manifest filename must not contain a path")
        binary = bundle / filename
        if not binary.is_file():
            raise RuntimeError(f"bundle manifest references missing executable: {binary}")
        if binary.is_symlink():
            raise RuntimeError("bundle executable must not be a symbolic link")
        data = binary.read_bytes()
        if len(data) > 100 * 1024 * 1024:
            raise RuntimeError("bundle executable exceeds the 100 MiB safety limit")
        if len(data) != manifest["size"]:
            raise RuntimeError("bundle executable size does not match manifest")
        if hashlib.sha256(data).hexdigest() != manifest["sha256"]:
            raise RuntimeError("bundle executable checksum does not match manifest")
        expected_tag = f"py3-none-{manifest['wheel_platform']}"
        requested_tag = os.environ.get("TAILKITTY_WHEEL_TAG", expected_tag)
        if requested_tag != expected_tag:
            raise RuntimeError(
                f"wheel tag {requested_tag!r} does not match bundle {expected_tag!r}"
            )
        build_data["pure_python"] = False
        build_data["tag"] = requested_tag
        build_data["force_include"][str(binary)] = f"tailkitty/bin/{binary.name}"
        build_data["force_include"][str(manifest_path)] = "tailkitty/bin/manifest.json"
