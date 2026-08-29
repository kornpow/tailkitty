"""Managed synchronous and asynchronous Tailcat processes."""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import time
import weakref
from collections.abc import Iterable, Sequence
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Protocol, Self

from .backend import find_backend
from .client import Client
from .token import parse_token


class ServerStartError(RuntimeError):
    """A Tailcat server could not become ready."""


class _Finalizer(Protocol):
    def detach(self) -> object: ...


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    """Best-effort finalizer used if a server owner forgets to stop it."""
    if process.poll() is None:
        try:
            process.terminate()
        except OSError:
            pass


def _serve_value(value: str | int | Iterable[str | int] | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int)):
        return str(value)
    return ",".join(str(item) for item in value)


def _server_args(
    serve: str | int | Iterable[str | int] | None,
    key: str | None,
    allow: Sequence[str] | None,
    verbose: bool,
    full_address: bool,
    extra_args: Sequence[str],
) -> list[str]:
    args: list[str] = []
    if (value := _serve_value(serve)) is not None:
        args.append(f"--serve={value}")
    if key:
        args.append(f"--key={key}")
    if allow is not None:
        args.append("--allow=" + (",".join(allow) if allow else "none"))
    if verbose:
        args.append("--verbose")
    if full_address:
        args.append("--full-address")
    args.extend(extra_args)
    return args


class ServerProcess:
    """A managed Tailcat server with race-free connection-token capture.

    The token is received through Tailcat's ``TAILCAT_ADDR_FILE`` mechanism,
    leaving stdout available for tunneled data. Startup uses polling rather
    than blocking ``readline()``, so its timeout is real even if the child is
    alive but never emits output.
    """

    def __init__(
        self,
        serve: str | int | Iterable[str | int] | None = None,
        *,
        key: str | None = None,
        allow: Sequence[str] | None = None,
        verbose: bool = False,
        full_address: bool = False,
        extra_args: Sequence[str] = (),
        stdin: int | IO[Any] | None = subprocess.DEVNULL,
        stdout: int | IO[Any] | None = subprocess.PIPE,
        stderr: int | IO[Any] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.arguments = _server_args(serve, key, allow, verbose, full_address, extra_args)
        self.stdin = stdin
        self.stdout_target = stdout
        self.stderr_target = stderr
        self.env = env
        self._process: subprocess.Popen[bytes] | None = None
        self._token: str | None = None
        self._token_dir: tempfile.TemporaryDirectory[str] | None = None
        self._finalizer: _Finalizer | None = None

    @property
    def token(self) -> str:
        if self._token is None:
            raise ServerStartError("server has not started")
        return self._token

    @property
    def process(self) -> subprocess.Popen[bytes]:
        if self._process is None:
            raise ServerStartError("server has not started")
        return self._process

    @property
    def stdout(self) -> IO[bytes] | None:
        return self._process.stdout if self._process is not None else None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self, timeout: float = 20.0) -> str:
        if self.is_running:
            return self.token
        self._token_dir = tempfile.TemporaryDirectory(prefix="tailkitty-")
        token_path = Path(self._token_dir.name) / "address"
        child_env = os.environ.copy()
        child_env.update(self.env or {})
        child_env["TAILCAT_ADDR_FILE"] = str(token_path)
        try:
            self._process = subprocess.Popen(
                [find_backend(), *self.arguments],
                stdin=self.stdin,
                stdout=self.stdout_target,
                stderr=self.stderr_target,
                env=child_env,
            )
        except BaseException:
            self._token_dir.cleanup()
            self._token_dir = None
            raise
        self._finalizer = weakref.finalize(self, _terminate_process, self._process)
        try:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                return_code = self._process.poll()
                if return_code is not None:
                    raise ServerStartError(
                        f"tailcat server exited before startup (code {return_code})"
                    )
                try:
                    candidate = token_path.read_text(encoding="utf-8").strip()
                except FileNotFoundError:
                    candidate = ""
                if candidate:
                    parse_token(candidate)
                    self._token = candidate
                    return candidate
                time.sleep(0.025)
            raise TimeoutError(f"tailcat server did not become ready within {timeout:g}s")
        except BaseException:
            self.stop()
            raise

    def stop(self, grace_period: float = 2.0) -> None:
        process, self._process = self._process, None
        if self._finalizer is not None:
            self._finalizer.detach()
            self._finalizer = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=grace_period)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        self._token = None
        if self._token_dir is not None:
            self._token_dir.cleanup()
            self._token_dir = None

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()


class AsyncServerProcess:
    """Asyncio counterpart to :class:`ServerProcess`."""

    def __init__(
        self,
        serve: str | int | Iterable[str | int] | None = None,
        *,
        key: str | None = None,
        allow: Sequence[str] | None = None,
        verbose: bool = False,
        full_address: bool = False,
        extra_args: Sequence[str] = (),
        env: dict[str, str] | None = None,
    ) -> None:
        self.arguments = _server_args(serve, key, allow, verbose, full_address, extra_args)
        self.env = env
        self.process: asyncio.subprocess.Process | None = None
        self._token: str | None = None
        self._token_dir: tempfile.TemporaryDirectory[str] | None = None
        self._finalizer: _Finalizer | None = None

    @property
    def token(self) -> str:
        if self._token is None:
            raise ServerStartError("server has not started")
        return self._token

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    async def start(self, timeout: float = 20.0) -> str:
        if self.is_running:
            return self.token
        self._token_dir = tempfile.TemporaryDirectory(prefix="tailkitty-")
        token_path = Path(self._token_dir.name) / "address"
        child_env = os.environ.copy()
        child_env.update(self.env or {})
        child_env["TAILCAT_ADDR_FILE"] = str(token_path)
        try:
            self.process = await asyncio.create_subprocess_exec(
                find_backend(),
                *self.arguments,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                env=child_env,
            )
            self._finalizer = weakref.finalize(self, self.process.terminate)
            deadline = asyncio.get_running_loop().time() + timeout
            while asyncio.get_running_loop().time() < deadline:
                if self.process.returncode is not None:
                    code = self.process.returncode
                    raise ServerStartError(f"tailcat server exited before startup (code {code})")
                try:
                    candidate = token_path.read_text(encoding="utf-8").strip()
                except FileNotFoundError:
                    candidate = ""
                if candidate:
                    parse_token(candidate)
                    self._token = candidate
                    return candidate
                await asyncio.sleep(0.025)
            raise TimeoutError(f"tailcat server did not become ready within {timeout:g}s")
        except BaseException:
            await self.stop()
            raise

    async def stop(self, grace_period: float = 2.0) -> None:
        process, self.process = self.process, None
        if self._finalizer is not None:
            self._finalizer.detach()
            self._finalizer = None
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=grace_period)
            except TimeoutError:
                process.kill()
                await process.wait()
        self._token = None
        if self._token_dir is not None:
            self._token_dir.cleanup()
            self._token_dir = None

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.stop()


async def run_async(
    arguments: Sequence[str],
    *,
    input: bytes | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run Tailcat without blocking the asyncio event loop."""
    process = await asyncio.create_subprocess_exec(
        find_backend(),
        *arguments,
        stdin=asyncio.subprocess.PIPE if input is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(input), timeout=timeout)
    except (TimeoutError, asyncio.CancelledError):
        process.kill()
        await process.wait()
        raise
    return subprocess.CompletedProcess(
        args=[find_backend(), *arguments],
        returncode=process.returncode or 0,
        stdout=stdout,
        stderr=stderr,
    )


def send(token: str, data: str | bytes, *, port: int = 0, timeout: float | None = None) -> bytes:
    """Send data to a Tailcat server and return its response bytes."""
    return Client(token).request(data, port=port, timeout=timeout)
