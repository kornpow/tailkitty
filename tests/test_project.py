from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

from tailkitty.constants import GO_VERSION, TAILKITTY_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_project_version_has_one_source_of_truth() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert project["project"]["version"] == TAILKITTY_VERSION


def test_distribution_import_and_cli_names_are_tailkitty() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["name"] == "tailkitty"
    assert project["scripts"] == {
        "tailkitty": "tailkitty.cli:main",
        "tailcat": "tailkitty.cli:main",
    }


def test_mise_go_version_matches_bundle_builder() -> None:
    mise = tomllib.loads((ROOT / ".mise.toml").read_text())
    assert mise["tools"]["go"] == GO_VERSION


def test_github_workflows_are_valid_yaml() -> None:
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        assert isinstance(yaml.safe_load(workflow.read_text()), dict)


def test_release_workflow_publishes_then_creates_github_release() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text())
    publish = workflow["jobs"]["publish"]
    assert publish["permissions"]["contents"] == "write"
    steps = publish["steps"]
    publish_index = next(
        index for index, step in enumerate(steps) if str(step.get("uses", "")).startswith("pypa/")
    )
    release_index = next(
        index for index, step in enumerate(steps) if step.get("name") == "Create GitHub release"
    )
    assert publish_index < release_index
    assert "--verify-tag" in steps[release_index]["run"]
    assert "checksums/SHA256SUMS" in steps[release_index]["run"]


def test_package_advertises_typing() -> None:
    assert (ROOT / "src" / "tailkitty" / "py.typed").is_file()
