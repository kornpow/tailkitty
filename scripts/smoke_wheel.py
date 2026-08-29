"""Install a host wheel into isolation and exercise its bundled executable."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .targets import host_target


def smoke_wheel(wheel: Path, *, uv: str = "uv") -> dict[str, object]:
    target = host_target()
    if not wheel.name.endswith(f"-py3-none-{target.wheel_platform}.whl"):
        raise RuntimeError(f"{wheel.name} is not a wheel for this host ({target.name})")
    with tempfile.TemporaryDirectory(prefix="tailkitty-wheel-smoke-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        subprocess.run([uv, "venv", "--python", sys.executable, str(environment)], check=True)
        interpreter = environment / (
            "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        )
        subprocess.run(
            [uv, "pip", "install", "--python", str(interpreter), str(wheel.resolve())], check=True
        )
        completed = subprocess.run(
            [str(interpreter), "-m", "tailkitty", "doctor", "--json"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        report = json.loads(completed.stdout)
        bundle = report["backend"]["bundle"]
        if report["backend"]["source"] != "bundle" or bundle["target"] != target.name:
            raise RuntimeError("installed wheel did not discover its verified host bundle")
        return {
            "wheel": wheel.name,
            "target": target.name,
            "backend": report["backend"]["path"],
            "tailcat_version": bundle["tailcat_version"],
            "verified": bundle["verified"],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--uv", default="uv")
    args = parser.parse_args()
    print(json.dumps(smoke_wheel(args.wheel, uv=args.uv), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
