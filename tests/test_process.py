from __future__ import annotations

import asyncio
import stat

import pytest

from tailkitty import AsyncServerProcess, ServerProcess, run, run_async

TOKEN = "tcomFwWCCcjS5nKNqAod034nWoJZW0LZqDhhC8U_dKdnDRYQ8uNGFpGQEu"


@pytest.fixture
def fake_backend(tmp_path, monkeypatch: pytest.MonkeyPatch):
    executable = tmp_path / "tailcat-go"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import os, pathlib, signal, sys, time\n"
        "if len(sys.argv) > 1 and sys.argv[1] == 'echo':\n"
        "    sys.stdout.write(' '.join(sys.argv[2:])); raise SystemExit\n"
        "if len(sys.argv) > 1 and sys.argv[1].startswith('tc'):\n"
        "    sys.stdout.buffer.write(sys.stdin.buffer.read()); raise SystemExit\n"
        f"pathlib.Path(os.environ['TAILCAT_ADDR_FILE']).write_text('{TOKEN}\\n')\n"
        "signal.signal(signal.SIGTERM, lambda *_: sys.exit())\n"
        "while True: time.sleep(1)\n",
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("TAILKITTY_BACKEND", str(executable))
    return executable


def test_run_infers_text(fake_backend) -> None:
    result = run(["echo", "hello"], capture_output=True, check=True)
    assert result.stdout == "hello"


def test_client_sync_and_async_requests(fake_backend) -> None:
    from tailkitty import AsyncClient, Client

    assert Client(TOKEN).request("hello") == b"hello"
    result = Client(TOKEN).run("status")
    assert result.returncode == 0
    assert result.stdout == b"status"

    async def exercise() -> None:
        assert await AsyncClient(TOKEN).request(b"async") == b"async"
        result = await AsyncClient(TOKEN).run(b"status")
        assert result.returncode == 0
        assert result.stdout == b"status"

    asyncio.run(exercise())


def test_client_rejects_invalid_port(fake_backend) -> None:
    from tailkitty import Client

    with pytest.raises(ValueError, match="between 0 and 65535"):
        Client(TOKEN).request(b"", port=65_536)


def test_server_process_captures_token_without_consuming_stdout(fake_backend) -> None:
    with ServerProcess(serve=[80, 443]) as server:
        assert server.token == TOKEN
        assert server.is_running
        assert server.arguments == ["--serve=80,443"]
    assert not server.is_running


def test_empty_allow_means_allow_none(fake_backend) -> None:
    server = ServerProcess(allow=[])
    assert server.arguments == ["--allow=none"]


def test_async_apis(fake_backend) -> None:
    async def exercise() -> None:
        result = await run_async(["echo", "async"])
        assert result.stdout == b"async"
        async with AsyncServerProcess() as server:
            assert server.token == TOKEN
            assert server.is_running

    asyncio.run(exercise())


def test_unstarted_token_raises() -> None:
    with pytest.raises(RuntimeError, match="has not started"):
        _ = ServerProcess().token
