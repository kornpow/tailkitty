"""Build and verify the complete platform-wheel matrix."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .build_binary import build
from .targets import TARGETS, get_target
from .verify_wheel import verify_wheel

ROOT = Path(__file__).resolve().parents[1]


def build_wheels(
    target_names: list[str],
    output_dir: Path,
    *,
    go: str = "go",
    uv: str = "uv",
) -> list[dict[str, object]]:
    """Build isolated bundles, package wheels, and verify every artifact."""
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="tailkitty-wheel-matrix-") as temporary:
        staging_root = Path(temporary)
        for target_name in target_names:
            target = get_target(target_name)
            bundle = staging_root / target.name
            build(target, bundle, go=go)
            environment = os.environ.copy()
            environment["TAILKITTY_BUNDLE_DIR"] = str(bundle)
            environment["TAILKITTY_WHEEL_TAG"] = f"py3-none-{target.wheel_platform}"
            environment.setdefault("SOURCE_DATE_EPOCH", "1580601600")
            subprocess.run(
                [uv, "build", "--wheel", "--out-dir", str(output_dir)],
                cwd=ROOT,
                env=environment,
                check=True,
            )
            wheels = sorted(output_dir.glob(f"*-py3-none-{target.wheel_platform}.whl"))
            if len(wheels) != 1:
                raise RuntimeError(f"expected one wheel for {target.name}, found {len(wheels)}")
            results.append(verify_wheel(wheels[0], target.name))
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", action="append", choices=tuple(TARGETS), dest="targets")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "wheels")
    parser.add_argument("--go", default=shutil.which("go") or "go")
    parser.add_argument("--uv", default=shutil.which("uv") or "uv")
    args = parser.parse_args()
    results = build_wheels(args.targets or list(TARGETS), args.output, go=args.go, uv=args.uv)
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
