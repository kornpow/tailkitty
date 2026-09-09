"""Check whether Tailkitty's immutable Tailcat pin matches the latest stable release."""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from typing import Any

from tailkitty.constants import TAILCAT_VERSION

RELEASE_URL = "https://api.github.com/repos/tailscale/tailcat/releases/latest"
MAX_RESPONSE_BYTES = 1_048_576
VERSION_PATTERN = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class UpstreamCheckError(RuntimeError):
    """The upstream release status could not be established."""


def parse_stable_version(value: str) -> tuple[int, int, int]:
    """Parse the stable Tailcat tag format used by release pins."""
    match = VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise UpstreamCheckError(f"expected a stable vMAJOR.MINOR.PATCH tag, got {value!r}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def compare_release(current: str, latest: str) -> str:
    """Return a status message, raising when a newer stable release exists."""
    current_version = parse_stable_version(current)
    latest_version = parse_stable_version(latest)
    if latest_version > current_version:
        raise UpstreamCheckError(f"Tailcat {latest} is available; Tailkitty is pinned to {current}")
    if latest_version < current_version:
        return f"Tailkitty pin {current} is newer than GitHub's latest stable release {latest}"
    return f"Tailkitty is current with the latest stable Tailcat release ({current})"


def latest_release_tag(*, timeout: float = 10.0) -> str:
    request = urllib.request.Request(
        RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "tailkitty-upstream-check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")
            if content_length is not None and int(content_length) > MAX_RESPONSE_BYTES:
                raise UpstreamCheckError("GitHub release response is unreasonably large")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise UpstreamCheckError(f"could not query the latest Tailcat release: {exc}") from exc
    if len(payload) > MAX_RESPONSE_BYTES:
        raise UpstreamCheckError("GitHub release response is unreasonably large")
    try:
        document: Any = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpstreamCheckError(f"GitHub returned invalid release metadata: {exc}") from exc
    if not isinstance(document, dict):
        raise UpstreamCheckError("GitHub release metadata is not an object")
    tag_name = document.get("tag_name")
    if not isinstance(tag_name, str):
        raise UpstreamCheckError("GitHub release metadata has no string tag_name")
    return tag_name


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=10.0)
    namespace = parser.parse_args(arguments)
    if namespace.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        print(compare_release(TAILCAT_VERSION, latest_release_tag(timeout=namespace.timeout)))
    except UpstreamCheckError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
