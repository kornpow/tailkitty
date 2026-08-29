from __future__ import annotations

import subprocess
import sys


def test_module_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tailkitty", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "tailkitty 0.1.1"
