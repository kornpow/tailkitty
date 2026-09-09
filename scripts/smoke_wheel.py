"""Install a host wheel into isolation and exercise its bundled executable."""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from .targets import host_target

UDP_SMOKE = r"""import socket
import threading

from tailkitty import Client, ServerProcess

sock = socket.socket(type=socket.SOCK_DGRAM)
sock.settimeout(5)
sock.bind(("127.0.0.1", 0))
port = sock.getsockname()[1]

def echo():
    data, source = sock.recvfrom(2048)
    sock.sendto(data, source)

thread = threading.Thread(target=echo, daemon=True)
thread.start()
try:
    server = ServerProcess(
        key="new",
        udp=port,
        env={"TS_DEBUG_TAILCAT_LOCAL_DERP": "1"},
    )
    try:
        server.start(timeout=5)
        with Client(server.token).connect_udp(port, timeout=5) as connection:
            response = connection.request(b"tailkitty-udp-smoke", timeout=3)
            assert response.data == b"tailkitty-udp-smoke"
    finally:
        server.stop(grace_period=2)
    thread.join(timeout=1)
    assert not thread.is_alive()
finally:
    sock.close()
"""


def smoke_data_plane(backend: Path) -> None:
    """Prove the bundled helper can complete a real encrypted peer handshake."""
    environment = os.environ.copy()
    environment["TS_DEBUG_TAILCAT_LOCAL_DERP"] = "1"
    server = subprocess.Popen(
        [str(backend), "--key=new"],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    tokens: queue.Queue[str] = queue.Queue(maxsize=1)

    def find_token() -> None:
        assert server.stderr is not None
        for line in server.stderr:
            match = re.search(r"\btc[A-Za-z0-9_-]+", line)
            if match:
                tokens.put(match.group())
                return

    threading.Thread(target=find_token, daemon=True).start()
    try:
        try:
            token = tokens.get(timeout=5)
        except queue.Empty as exc:
            raise RuntimeError("bundled helper did not advertise within five seconds") from exc
        subprocess.run(
            [str(backend), "--key=new", "ping", "--timeout=3s", token],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


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
        backend = Path(report["backend"]["path"])
        smoke_data_plane(backend)
        subprocess.run(
            [str(interpreter), "-c", UDP_SMOKE],
            cwd=root,
            check=True,
            timeout=15,
        )
        return {
            "wheel": wheel.name,
            "target": target.name,
            "backend": report["backend"]["path"],
            "tailcat_version": bundle["tailcat_version"],
            "data_plane": "verified",
            "udp_data_plane": "verified",
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
