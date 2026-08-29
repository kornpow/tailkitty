"""Strict structural and integrity checks for a Tailkitty platform wheel."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path, PurePosixPath

from tailkitty.constants import TAILCAT_MODULE, TAILCAT_VERSION

from .targets import get_target


def _record_hash(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"sha256={digest}"


def verify_wheel(path: Path, target_name: str) -> dict[str, object]:
    target = get_target(target_name)
    expected_suffix = f"-py3-none-{target.wheel_platform}.whl"
    if not path.name.endswith(expected_suffix):
        raise RuntimeError(f"wheel {path.name} does not end with {expected_suffix}")
    with zipfile.ZipFile(path) as archive:
        if sum(member.file_size for member in archive.infolist()) > 128 * 1024 * 1024:
            raise RuntimeError("wheel exceeds the 128 MiB uncompressed safety limit")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError("wheel contains duplicate archive entries")
        for name in names:
            member = PurePosixPath(name)
            if member.is_absolute() or ".." in member.parts:
                raise RuntimeError(f"wheel contains unsafe path {name!r}")
        wheel_names = [name for name in names if name.endswith(".dist-info/WHEEL")]
        if len(wheel_names) != 1:
            raise RuntimeError(
                f"wheel must contain exactly one WHEEL metadata file, found {len(wheel_names)}"
            )
        wheel_name = wheel_names[0]
        wheel_metadata = archive.read(wheel_name).decode()
        if "Root-Is-Purelib: false" not in wheel_metadata:
            raise RuntimeError("platform wheel is incorrectly marked as pure Python")
        if f"Tag: py3-none-{target.wheel_platform}" not in wheel_metadata:
            raise RuntimeError("platform wheel metadata contains the wrong compatibility tag")
        manifest_name = "tailkitty/bin/manifest.json"
        binary_name = f"tailkitty/bin/{target.executable}"
        if "tailkitty/py.typed" not in names:
            raise RuntimeError("wheel does not contain its PEP 561 py.typed marker")
        manifest = json.loads(archive.read(manifest_name))
        binary = archive.read(binary_name)
        if manifest["target"] != target.name:
            raise RuntimeError("bundle manifest target does not match wheel target")
        expected_manifest = {
            "schema": 1,
            "wheel_platform": target.wheel_platform,
            "filename": target.executable,
            "tailcat_module": TAILCAT_MODULE,
            "tailcat_version": TAILCAT_VERSION,
        }
        for field, expected in expected_manifest.items():
            if manifest.get(field) != expected:
                raise RuntimeError(f"bundle manifest {field} does not match wheel build inputs")
        if manifest["size"] != len(binary):
            raise RuntimeError("bundle size does not match wheel executable")
        if manifest["sha256"] != hashlib.sha256(binary).hexdigest():
            raise RuntimeError("bundle checksum does not match wheel executable")
        if not any(binary.startswith(magic) for magic in target.magic):
            raise RuntimeError("bundled file does not have the target executable format")
        record_names = [name for name in names if name.endswith(".dist-info/RECORD")]
        if len(record_names) != 1:
            raise RuntimeError(
                f"wheel must contain exactly one RECORD file, found {len(record_names)}"
            )
        record_name = record_names[0]
        rows = list(csv.reader(io.StringIO(archive.read(record_name).decode())))
        if any(len(row) != 3 for row in rows):
            raise RuntimeError("wheel RECORD contains a malformed row")
        records = {name: (digest, size) for name, digest, size in rows}
        if set(records) != set(names):
            raise RuntimeError("wheel RECORD entries do not exactly match archive members")
        for name in names:
            if name == record_name:
                continue
            digest, size = records[name]
            data = archive.read(name)
            if digest != _record_hash(data) or size != str(len(data)):
                raise RuntimeError(f"RECORD integrity mismatch for {name}")
    return {
        "wheel": path.name,
        "target": target.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size": path.stat().st_size,
        "entries": len(names),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    result = verify_wheel(args.wheel, args.target)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
