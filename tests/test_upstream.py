from __future__ import annotations

import pytest

from scripts.check_upstream import UpstreamCheckError, compare_release, parse_stable_version


def test_parse_stable_version() -> None:
    assert parse_stable_version("v12.34.56") == (12, 34, 56)


@pytest.mark.parametrize("value", ["0.6.0", "v0.6", "v01.2.3", "v1.2.3-rc.1"])
def test_rejects_non_release_pin(value: str) -> None:
    with pytest.raises(UpstreamCheckError, match="stable"):
        parse_stable_version(value)


def test_current_release_message() -> None:
    assert compare_release("v0.6.0", "v0.6.0") == (
        "Tailkitty is current with the latest stable Tailcat release (v0.6.0)"
    )


def test_new_release_fails_check() -> None:
    with pytest.raises(UpstreamCheckError, match="v0.7.0 is available"):
        compare_release("v0.6.0", "v0.7.0")


def test_pin_ahead_of_release() -> None:
    assert "newer than" in compare_release("v0.7.0", "v0.6.0")
