from __future__ import annotations

import pytest

from scripts.targets import TARGETS, get_target, host_target


def test_supported_target_matrix_is_unique() -> None:
    assert len(TARGETS) == 5
    assert len({target.wheel_platform for target in TARGETS.values()}) == 5


def test_host_target_is_supported() -> None:
    assert host_target() in TARGETS.values()


def test_unknown_target_lists_choices() -> None:
    with pytest.raises(ValueError, match="choose from"):
        get_target("plan9-cat")
