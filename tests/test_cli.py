from __future__ import annotations

import json

from tailkitty import cli
from tailkitty.cli import main

README_TOKEN = "tcomFwWCCcjS5nKNqAod034nWoJZW0LZqDhhC8U_dKdnDRYQ8uNGFpGQEu"


def test_parse_command(capsys) -> None:
    assert main(["parse", README_TOKEN]) == 0
    output = capsys.readouterr().out
    assert '"RegionID": 302' in output
    assert "nodekey:9c8d2e" in output


def test_doctor_json_is_machine_readable(capsys, monkeypatch) -> None:
    report = {
        "tailkitty_version": "0.1.1",
        "python_version": "3.13.11",
        "machine": "arm64",
        "backend": {"path": "/bundle/tailcat", "source": "bundle", "executable": True},
    }
    monkeypatch.setattr(cli, "diagnostics", lambda: report)
    assert main(["doctor", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == report
