"""Datagram-preserving UDP connections over Tailcat's SOCKS5 relay."""

from __future__ import annotations

import asyncio
import ipaddress
import queue
import re
import socket
import struct
import subprocess
import threading
import time
import weakref
from contextlib import suppress
from dataclasses import dataclass
from types import TracebackType
from typing import Self
from urllib.parse import urlsplit

from .backend import find_backend

MAX_UDP_PAYLOAD = 1232
"""Largest UDP payload that fits Tailcat's tunnel MTU without fragmentation."""

_MAX_SOCKS_PACKET = MAX_UDP_PAYLOAD + 262
_SOCKS_ADDRESS = re.compile(r"\bSOCKS running at (socks5h?://\S+)")
_TOKEN = re.compile(r"\btc[A-Za-z0-9_-]+")


class UDPError(RuntimeError):
    """Tailkitty could not establish or use a UDP relay."""


@dataclass(frozen=True, slots=True)
class Datagram:
    """One received UDP datagram and the source reported by SOCKS5."""

    data: bytes
    host: str
    port: int


def _validate_port(port: int) -> None:
    if not 0 <= port <= 65535:
        raise ValueError(f"port must be between 0 and 65535, got {port}")


def _encode_address(host: str, port: int) -> bytes:
    _validate_port(port)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        encoded = host.encode("idna")
        if not encoded or len(encoded) > 255:
            raise ValueError("UDP destination hostname must contain between 1 and 255 bytes")
        return b"\x03" + bytes([len(encoded)]) + encoded + struct.pack("!H", port)
    if isinstance(address, ipaddress.IPv4Address):
        return b"\x01" + address.packed + struct.pack("!H", port)
    return b"\x04" + address.packed + struct.pack("!H", port)


def _decode_address(packet: bytes, offset: int) -> tuple[str, int, int]:
    if offset >= len(packet):
        raise UDPError("truncated SOCKS5 address")
    address_type = packet[offset]
    offset += 1
    if address_type == 1:
        end = offset + 4
        if end > len(packet):
            raise UDPError("truncated SOCKS5 IPv4 address")
        host = str(ipaddress.IPv4Address(packet[offset:end]))
    elif address_type == 4:
        end = offset + 16
        if end > len(packet):
            raise UDPError("truncated SOCKS5 IPv6 address")
        host = str(ipaddress.IPv6Address(packet[offset:end]))
    elif address_type == 3:
        if offset >= len(packet):
            raise UDPError("truncated SOCKS5 domain length")
        length = packet[offset]
        offset += 1
        end = offset + length
        if end > len(packet):
            raise UDPError("truncated SOCKS5 domain")
        try:
            host = packet[offset:end].decode("idna")
        except UnicodeError as exc:
            raise UDPError("invalid SOCKS5 domain") from exc
    else:
        raise UDPError(f"unsupported SOCKS5 address type {address_type}")
    if end + 2 > len(packet):
        raise UDPError("truncated SOCKS5 port")
    port = struct.unpack("!H", packet[end : end + 2])[0]
    return host, port, end + 2


def _read_exact(stream: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = stream.recv(size - len(chunks))
        if not chunk:
            raise UDPError("SOCKS5 proxy closed during negotiation")
        chunks.extend(chunk)
    return bytes(chunks)


def _read_socks_address(stream: socket.socket) -> tuple[str, int]:
    address_type = _read_exact(stream, 1)[0]
    if address_type == 1:
        address = _read_exact(stream, 4)
    elif address_type == 4:
        address = _read_exact(stream, 16)
    elif address_type == 3:
        address = _read_exact(stream, _read_exact(stream, 1)[0])
    else:
        raise UDPError(f"unsupported SOCKS5 address type {address_type}")
    port = struct.unpack("!H", _read_exact(stream, 2))[0]
    if address_type == 1:
        return str(ipaddress.IPv4Address(address)), port
    if address_type == 4:
        return str(ipaddress.IPv6Address(address)), port
    try:
        return address.decode("idna"), port
    except UnicodeError as exc:
        raise UDPError("invalid SOCKS5 relay domain") from exc


def _stop_process(process: subprocess.Popen[bytes], grace_period: float = 2.0) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except OSError:
        return
    try:
        process.wait(timeout=grace_period)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _close_resources(
    process: subprocess.Popen[bytes], control: socket.socket, datagrams: socket.socket
) -> None:
    datagrams.close()
    control.close()
    _stop_process(process)


def _start_socks_proxy(token: str, timeout: float) -> tuple[subprocess.Popen[bytes], str, int]:
    if timeout <= 0:
        raise ValueError("UDP connection timeout must be greater than zero")
    process = subprocess.Popen(
        [find_backend(), "socks", "--listen=127.0.0.1:0", token],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    results: queue.Queue[str] = queue.Queue(maxsize=1)
    recent_errors: list[str] = []

    def read_logs() -> None:
        assert process.stderr is not None
        for raw_line in process.stderr:
            line = raw_line.decode(errors="replace").strip()
            recent_errors.append(_TOKEN.sub("tc…", line))
            del recent_errors[:-8]
            if match := _SOCKS_ADDRESS.search(line):
                try:
                    results.put_nowait(match.group(1))
                except queue.Full:
                    pass

    threading.Thread(target=read_logs, daemon=True, name="tailkitty-udp-proxy-log").start()
    deadline = time.monotonic() + timeout
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Tailcat UDP proxy did not become ready within {timeout:g}s")
            try:
                proxy_url = results.get(timeout=min(remaining, 0.05))
                break
            except queue.Empty:
                if (code := process.poll()) is not None:
                    detail = "; ".join(filter(None, recent_errors))
                    suffix = f": {detail}" if detail else ""
                    raise UDPError(f"Tailcat UDP proxy exited during startup (code {code}){suffix}")
        parsed = urlsplit(proxy_url)
        if parsed.hostname is None or parsed.port is None:
            raise UDPError(f"Tailcat returned an invalid SOCKS5 address: {proxy_url!r}")
        return process, parsed.hostname, parsed.port
    except BaseException:
        _stop_process(process)
        raise


def _decode_datagram(packet: bytes) -> Datagram:
    if len(packet) < 4 or packet[:2] != b"\x00\x00":
        raise UDPError("invalid SOCKS5 UDP response header")
    if packet[2] != 0:
        raise UDPError("fragmented SOCKS5 UDP datagrams are not supported")
    host, port, payload_offset = _decode_address(packet, 3)
    return Datagram(packet[payload_offset:], host, port)


class UDPConnection:
    """A connected, datagram-preserving Tailcat UDP flow.

    Create this through :meth:`tailkitty.Client.connect_udp`. The connection owns a private
    loopback SOCKS5 relay and its Tailcat subprocess; closing it cleans up both.
    """

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        control: socket.socket,
        datagrams: socket.socket,
        target: bytes,
    ) -> None:
        self._process = process
        self._control = control
        self._datagrams = datagrams
        self._target = target
        self._send_lock = threading.Lock()
        self._receive_lock = threading.Lock()
        self._closed = False
        self._finalizer = weakref.finalize(
            self, _close_resources, self._process, self._control, self._datagrams
        )

    @classmethod
    def open(
        cls,
        token: str,
        port: int,
        *,
        host: str = "server.tailcat",
        timeout: float = 20.0,
    ) -> Self:
        """Start a UDP flow to a server port or an exit-node destination."""
        target = _encode_address(host, port)
        process, proxy_host, proxy_port = _start_socks_proxy(token, timeout)
        control: socket.socket | None = None
        datagrams: socket.socket | None = None
        try:
            control = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
            control.sendall(b"\x05\x01\x00")
            if _read_exact(control, 2) != b"\x05\x00":
                raise UDPError("SOCKS5 proxy rejected unauthenticated negotiation")
            control.sendall(b"\x05\x03\x00\x01\x00\x00\x00\x00\x00\x00")
            version, status, reserved = _read_exact(control, 3)
            if version != 5 or reserved != 0:
                raise UDPError("invalid SOCKS5 UDP association response")
            if status != 0:
                raise UDPError(f"SOCKS5 UDP association failed with status {status}")
            relay_host, relay_port = _read_socks_address(control)
            try:
                if ipaddress.ip_address(relay_host).is_unspecified:
                    relay_host = proxy_host
            except ValueError:
                pass
            family, socktype, protocol, _, relay = socket.getaddrinfo(
                relay_host, relay_port, type=socket.SOCK_DGRAM
            )[0]
            datagrams = socket.socket(family, socktype, protocol)
            datagrams.connect(relay)
            control.settimeout(None)
            return cls(process, control, datagrams, target)
        except BaseException:
            if datagrams is not None:
                datagrams.close()
            if control is not None:
                control.close()
            _stop_process(process)
            raise

    @property
    def closed(self) -> bool:
        return self._closed

    def _ensure_open(self) -> None:
        if self._closed:
            raise UDPError("UDP connection is closed")
        if (code := self._process.poll()) is not None:
            raise UDPError(f"Tailcat UDP proxy exited (code {code})")

    def send(self, data: bytes | bytearray | memoryview) -> None:
        """Send exactly one UDP datagram."""
        self._ensure_open()
        payload = bytes(data)
        if len(payload) > MAX_UDP_PAYLOAD:
            raise ValueError(f"UDP payload is {len(payload)} bytes; maximum is {MAX_UDP_PAYLOAD}")
        with self._send_lock:
            sent = self._datagrams.send(b"\x00\x00\x00" + self._target + payload)
        expected = 3 + len(self._target) + len(payload)
        if sent != expected:
            raise UDPError(f"short UDP write: sent {sent} of {expected} bytes")

    def receive(self, *, timeout: float | None = None) -> Datagram:
        """Receive exactly one UDP datagram, with an optional timeout."""
        self._ensure_open()
        if timeout is not None and timeout < 0:
            raise ValueError("UDP receive timeout must not be negative")
        with self._receive_lock:
            previous = self._datagrams.gettimeout()
            self._datagrams.settimeout(timeout)
            try:
                packet = self._datagrams.recv(_MAX_SOCKS_PACKET)
            finally:
                self._datagrams.settimeout(previous)
        return _decode_datagram(packet)

    def request(
        self, data: bytes | bytearray | memoryview, *, timeout: float | None = None
    ) -> Datagram:
        """Send one datagram and wait for one response."""
        self.send(data)
        return self.receive(timeout=timeout)

    def close(self, grace_period: float = 2.0) -> None:
        """Close sockets and terminate the owned Tailcat subprocess."""
        if self._closed:
            return
        self._closed = True
        self._finalizer.detach()
        self._datagrams.close()
        self._control.close()
        _stop_process(self._process, grace_period)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class AsyncUDPConnection:
    """Asyncio wrapper for a :class:`UDPConnection`."""

    def __init__(self, connection: UDPConnection) -> None:
        self._connection = connection
        self._connection._datagrams.setblocking(False)

    @classmethod
    async def open(
        cls,
        token: str,
        port: int,
        *,
        host: str = "server.tailcat",
        timeout: float = 20.0,
    ) -> Self:
        """Start a UDP flow without blocking the event loop."""
        task = asyncio.create_task(
            asyncio.to_thread(UDPConnection.open, token, port, host=host, timeout=timeout)
        )
        try:
            connection = await asyncio.shield(task)
        except asyncio.CancelledError:
            with suppress(Exception):
                connection = await task
                await asyncio.to_thread(connection.close)
            raise
        return cls(connection)

    @property
    def closed(self) -> bool:
        return self._connection.closed

    async def send(self, data: bytes | bytearray | memoryview) -> None:
        """Send exactly one UDP datagram."""
        self._connection._ensure_open()
        payload = bytes(data)
        if len(payload) > MAX_UDP_PAYLOAD:
            raise ValueError(f"UDP payload is {len(payload)} bytes; maximum is {MAX_UDP_PAYLOAD}")
        packet = b"\x00\x00\x00" + self._connection._target + payload
        await asyncio.get_running_loop().sock_sendall(self._connection._datagrams, packet)

    async def receive(self, *, timeout: float | None = None) -> Datagram:
        """Receive exactly one UDP datagram, with an optional timeout."""
        self._connection._ensure_open()
        if timeout is not None and timeout < 0:
            raise ValueError("UDP receive timeout must not be negative")
        operation = asyncio.get_running_loop().sock_recv(
            self._connection._datagrams, _MAX_SOCKS_PACKET
        )
        packet = await asyncio.wait_for(operation, timeout=timeout)
        return _decode_datagram(packet)

    async def request(
        self, data: bytes | bytearray | memoryview, *, timeout: float | None = None
    ) -> Datagram:
        """Send one datagram and wait for one response."""
        await self.send(data)
        return await self.receive(timeout=timeout)

    async def close(self, grace_period: float = 2.0) -> None:
        """Close sockets and terminate the owned Tailcat subprocess."""
        await asyncio.to_thread(self._connection.close, grace_period)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
