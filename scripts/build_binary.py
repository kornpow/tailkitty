"""Build a reproducible Tailcat executable and its integrity manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import cast

from tailkitty.constants import GO_VERSION, TAILCAT_MODULE, TAILCAT_VERSION

from .targets import TARGETS, Target, get_target, target_dict

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_DIR = ROOT / "src" / "tailkitty" / "bin"
TAILCAT_PATCHES = tuple(sorted((ROOT / "patches").glob("*.patch")))


def download_module(
    go: str, module: str, *, cwd: Path, environment: dict[str, str], attempts: int = 3
) -> dict[str, object]:
    """Download an immutable Go module with bounded transient-failure retries."""
    for attempt in range(1, attempts + 1):
        try:
            completed = subprocess.run(
                [go, "mod", "download", "-json", module],
                cwd=cwd,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            value = json.loads(completed.stdout)
            if not isinstance(value, dict):
                raise TypeError("go mod download returned a non-object")
            return cast(dict[str, object], value)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            if attempt == attempts:
                raise
            time.sleep(2 ** (attempt - 1))
    raise AssertionError("unreachable")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def patch_manifest() -> list[dict[str, str]]:
    return [{"filename": patch.name, "sha256": sha256(patch)} for patch in TAILCAT_PATCHES]


def verify_binary(path: Path, target: Target) -> None:
    if not path.is_file() or path.stat().st_size < 1024 * 1024:
        raise RuntimeError(f"built executable is missing or implausibly small: {path}")
    with path.open("rb") as stream:
        header = stream.read(4)
    if not any(header.startswith(magic) for magic in target.magic):
        raise RuntimeError(f"executable header {header.hex()} does not match {target.name}")


def build(target: Target, output_dir: Path, *, go: str = "go") -> dict[str, object]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / target.executable
    temporary_output = output_dir / f".{target.executable}.tmp"
    temporary_output.unlink(missing_ok=True)
    environment = os.environ.copy()
    environment["GOTOOLCHAIN"] = "local"
    go_version = subprocess.run(
        [go, "version"], capture_output=True, text=True, env=environment, check=True
    ).stdout.strip()
    if not go_version.startswith(f"go version go{GO_VERSION} "):
        raise RuntimeError(
            f"Tailcat bundles require exactly Go {GO_VERSION}; got {go_version!r}. Run `mise install`."
        )
    with tempfile.TemporaryDirectory(prefix="tailkitty-build-") as directory:
        workspace = Path(directory)
        module_info = download_module(
            go,
            f"{TAILCAT_MODULE}@{TAILCAT_VERSION}",
            cwd=workspace,
            environment=environment,
        )
        source = Path(str(module_info["Dir"]))
        module_dir = workspace / "tailcat"
        shutil.copytree(source, module_dir)
        module_dir.chmod(module_dir.stat().st_mode | stat.S_IWUSR)
        for source_path in module_dir.rglob("*"):
            writable = stat.S_IWUSR | (stat.S_IXUSR if source_path.is_dir() else 0)
            source_path.chmod(source_path.stat().st_mode | writable)
        for patch in TAILCAT_PATCHES:
            subprocess.run(
                ["git", "apply", "--check", str(patch)], cwd=module_dir, env=environment, check=True
            )
            subprocess.run(
                ["git", "apply", str(patch)], cwd=module_dir, env=environment, check=True
            )
        release_tags = (module_dir / "build-tags.txt").read_text().strip()
        environment.update(
            {
                "CGO_ENABLED": "0",
                "GOOS": target.goos,
                "GOARCH": target.goarch,
                "GOAMD64": "v1",
                "GOARM64": "v8.0",
            }
        )
        subprocess.run(
            [
                go,
                "build",
                f"-tags={release_tags}",
                "-trimpath",
                "-buildvcs=false",
                "-ldflags=-s -w -buildid=",
                "-o",
                str(temporary_output),
                "./cmd/tailcat",
            ],
            cwd=module_dir,
            env=environment,
            check=True,
        )
    verify_binary(temporary_output, target)
    temporary_output.chmod(
        temporary_output.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    os.replace(temporary_output, destination)
    for stale_name in {"tailcat", "tailcat.exe"} - {target.executable}:
        (output_dir / stale_name).unlink(missing_ok=True)
    manifest: dict[str, object] = {
        "schema": 1,
        "target": target.name,
        "wheel_platform": target.wheel_platform,
        "filename": target.executable,
        "sha256": sha256(destination),
        "size": destination.stat().st_size,
        "tailcat_module": TAILCAT_MODULE,
        "tailcat_version": TAILCAT_VERSION,
        "tailcat_patches": patch_manifest(),
        "go_version": go_version,
        "reproducible_flags": ["-trimpath", "-buildvcs=false", "-ldflags=-s -w -buildid="],
        "release_tags": release_tags,
        "cgo_enabled": False,
    }
    manifest_path = output_dir / "manifest.json"
    temporary_manifest = output_dir / ".manifest.json.tmp"
    temporary_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    os.replace(temporary_manifest, manifest_path)
    return manifest


def verify_bundle(directory: Path) -> dict[str, object]:
    manifest_path = directory / "manifest.json"
    try:
        raw = json.loads(manifest_path.read_text())
        if not isinstance(raw, dict):
            raise TypeError("manifest must contain an object")
        manifest = cast(dict[str, object], raw)
        target = get_target(str(manifest["target"]))
        binary = directory / str(manifest["filename"])
    except (FileNotFoundError, KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"invalid bundle manifest in {directory}: {exc}") from exc
    verify_binary(binary, target)
    expected = {
        "schema": 1,
        "wheel_platform": target.wheel_platform,
        "filename": target.executable,
        "tailcat_module": TAILCAT_MODULE,
        "tailcat_version": TAILCAT_VERSION,
        "tailcat_patches": patch_manifest(),
    }
    for field, expected_value in expected.items():
        if manifest.get(field) != expected_value:
            raise RuntimeError(
                f"bundle manifest {field} is {manifest.get(field)!r}, expected {expected_value!r}"
            )
    if not isinstance(manifest.get("release_tags"), str) or not manifest["release_tags"]:
        raise RuntimeError("bundle manifest has no upstream release build tags")
    if binary.stat().st_size != manifest.get("size"):
        raise RuntimeError("bundled executable size does not match manifest")
    if sha256(binary) != manifest.get("sha256"):
        raise RuntimeError("bundled executable checksum does not match manifest")
    return manifest


def clean_bundle(directory: Path) -> None:
    for name in ("tailcat", "tailcat.exe", "manifest.json"):
        (directory / name).unlink(missing_ok=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("command", choices=("build", "verify", "clean", "targets"))
    result.add_argument("--target", default="host")
    result.add_argument("--output", type=Path, default=DEFAULT_BUNDLE_DIR)
    result.add_argument("--go", default=shutil.which("go") or "go")
    result.add_argument("--json", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "targets":
        value: dict[str, object] | list[dict[str, object]] = [
            target_dict(target) for target in TARGETS.values()
        ]
    elif args.command == "clean":
        clean_bundle(args.output)
        value = {"cleaned": str(args.output)}
    elif args.command == "verify":
        value = verify_bundle(args.output)
    else:
        value = build(get_target(args.target), args.output, go=args.go)
    if args.json:
        print(json.dumps(value, indent=2, sort_keys=True))
    elif isinstance(value, list):
        for item in value:
            print(item)
    else:
        print(f"{args.command}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
