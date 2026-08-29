"""Supported binary and wheel targets."""

from __future__ import annotations

import platform
import sys
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Target:
    name: str
    goos: str
    goarch: str
    wheel_platform: str
    executable: str
    magic: tuple[bytes, ...]


TARGETS = {
    target.name: target
    for target in (
        Target(
            "macos-arm64",
            "darwin",
            "arm64",
            "macosx_12_0_arm64",
            "tailcat",
            (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"),
        ),
        Target(
            "macos-x86_64",
            "darwin",
            "amd64",
            "macosx_12_0_x86_64",
            "tailcat",
            (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"),
        ),
        Target(
            "linux-x86_64",
            "linux",
            "amd64",
            "manylinux_2_17_x86_64",
            "tailcat",
            (b"\x7fELF",),
        ),
        Target(
            "linux-aarch64",
            "linux",
            "arm64",
            "manylinux_2_17_aarch64",
            "tailcat",
            (b"\x7fELF",),
        ),
        Target(
            "windows-x86_64",
            "windows",
            "amd64",
            "win_amd64",
            "tailcat.exe",
            (b"MZ",),
        ),
    )
}


def host_target() -> Target:
    system = {"darwin": "macos", "linux": "linux", "win32": "windows"}.get(sys.platform)
    machine = platform.machine().lower()
    architecture = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "arm64",
        "aarch64": "aarch64" if system == "linux" else "arm64",
    }.get(machine)
    name = f"{system}-{architecture}"
    if system is None or architecture is None or name not in TARGETS:
        raise RuntimeError(f"unsupported build host: {sys.platform}/{platform.machine()}")
    return TARGETS[name]


def get_target(name: str) -> Target:
    if name == "host":
        return host_target()
    try:
        return TARGETS[name]
    except KeyError as exc:
        choices = ", ".join(["host", *TARGETS])
        raise ValueError(f"unknown target {name!r}; choose from {choices}") from exc


def target_dict(target: Target) -> dict[str, object]:
    value = asdict(target)
    value["magic"] = [item.hex() for item in target.magic]
    return value
