"""High-level synchronous and asynchronous Tailcat clients."""

from __future__ import annotations

import asyncio
import subprocess
from typing import Self

from .backend import find_backend
from .destination import resolve_destination, resolve_destination_async


def _port_argument(port: int) -> list[str]:
    if not 0 <= port <= 65535:
        raise ValueError(f"port must be between 0 and 65535, got {port}")
    return [] if port == 0 else [str(port)]


class Client:
    """A reusable Tailcat destination with process and request helpers."""

    def __init__(self, destination: str, *, dns_timeout: float = 5.0) -> None:
        self.destination = destination
        self.dns_timeout = dns_timeout
        self._token: str | None = None

    @property
    def token(self) -> str:
        if self._token is None:
            self._token = resolve_destination(self.destination, timeout=self.dns_timeout)
        return self._token

    def connect(
        self,
        port: int = 0,
        *,
        stdin: int = subprocess.PIPE,
        stdout: int = subprocess.PIPE,
        stderr: int = subprocess.PIPE,
    ) -> subprocess.Popen[bytes]:
        """Start a streaming connection and return its process handles."""
        return subprocess.Popen(
            [find_backend(), self.token, *_port_argument(port)],
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        )

    def request(
        self,
        data: str | bytes = b"",
        *,
        port: int = 0,
        timeout: float | None = None,
    ) -> bytes:
        """Send a finite payload, close stdin, and return response bytes."""
        return self.run(data, port=port, timeout=timeout, check=True).stdout

    def run(
        self,
        data: str | bytes = b"",
        *,
        port: int = 0,
        timeout: float | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[bytes]:
        """Run a finite exchange and retain status, stdout, and stderr."""
        payload = data.encode() if isinstance(data, str) else data
        return subprocess.run(
            [find_backend(), self.token, *_port_argument(port)],
            input=payload,
            capture_output=True,
            check=check,
            timeout=timeout,
        )

    def refresh(self) -> Self:
        """Discard a cached DNS result so the next operation resolves it again."""
        self._token = None
        return self


class AsyncClient:
    """Asyncio Tailcat client."""

    def __init__(self, destination: str, *, dns_timeout: float = 5.0) -> None:
        self.destination = destination
        self.dns_timeout = dns_timeout
        self._token: str | None = None

    async def resolve(self) -> str:
        if self._token is None:
            self._token = await resolve_destination_async(
                self.destination, timeout=self.dns_timeout
            )
        return self._token

    async def connect(self, port: int = 0) -> asyncio.subprocess.Process:
        token = await self.resolve()
        return await asyncio.create_subprocess_exec(
            find_backend(),
            token,
            *_port_argument(port),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def request(
        self,
        data: str | bytes = b"",
        *,
        port: int = 0,
        timeout: float | None = None,
    ) -> bytes:
        """Send a finite payload and return response bytes."""
        return (await self.run(data, port=port, timeout=timeout, check=True)).stdout

    async def run(
        self,
        data: str | bytes = b"",
        *,
        port: int = 0,
        timeout: float | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[bytes]:
        """Async finite exchange retaining status, stdout, and stderr."""
        payload = data.encode() if isinstance(data, str) else data
        backend = find_backend()
        token = await self.resolve()
        command = [backend, token, *_port_argument(port)]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(payload), timeout=timeout)
        except (TimeoutError, asyncio.CancelledError):
            process.kill()
            await process.wait()
            raise
        if check and process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
        return subprocess.CompletedProcess(command, process.returncode or 0, stdout, stderr)

    def refresh(self) -> Self:
        self._token = None
        return self
