from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator

import pytest

from tailkitty import MAX_UDP_PAYLOAD, AsyncClient, Client, UDPError
from tailkitty.udp import _decode_datagram, _encode_address

TOKEN = "tcomFwWCCcjS5nKNqAod034nWoJZW0LZqDhhC8U_dKdnDRYQ8uNGFpGQEu"


def _read_exact(stream: socket.socket, size: int) -> bytes:
    result = bytearray()
    while len(result) < size:
        result.extend(stream.recv(size - len(result)))
    return bytes(result)


@pytest.fixture
def fake_socks_proxy(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    tcp = socket.socket()
    tcp.bind(("127.0.0.1", 0))
    tcp.listen()
    udp = socket.socket(type=socket.SOCK_DGRAM)
    udp.bind(("127.0.0.1", 0))
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            control, _ = tcp.accept()
            with control:
                assert _read_exact(control, 3) == b"\x05\x01\x00"
                control.sendall(b"\x05\x00")
                assert _read_exact(control, 10) == b"\x05\x03\x00\x01\x00\x00\x00\x00\x00\x00"
                host, port = udp.getsockname()
                control.sendall(b"\x05\x00\x00" + _encode_address(host, port))
                packet, source = udp.recvfrom(MAX_UDP_PAYLOAD + 262)
                udp.sendto(packet, source)
                while control.recv(1):
                    pass
        except AssertionError as exc:
            errors.append(exc)
        except OSError as exc:
            if udp.fileno() != -1:
                errors.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    processes: list[subprocess.Popen[bytes]] = []

    def start_proxy(token: str, timeout: float) -> tuple[subprocess.Popen[bytes], str, int]:
        assert token == TOKEN
        assert timeout > 0
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes.append(process)
        host, port = tcp.getsockname()
        return process, host, port

    monkeypatch.setattr("tailkitty.udp._start_socks_proxy", start_proxy)
    yield
    tcp.close()
    udp.close()
    thread.join(timeout=1)
    for process in processes:
        if process.poll() is None:
            process.kill()
            process.wait()
    assert not errors


def test_sync_udp_preserves_datagram(fake_socks_proxy) -> None:
    with Client(TOKEN).connect_udp(53, timeout=1) as connection:
        reply = connection.request(b"hello", timeout=1)
        assert reply.data == b"hello"
        assert reply.host == "server.tailcat"
        assert reply.port == 53
        assert not connection.closed
    assert connection.closed


def test_async_udp_preserves_datagram(fake_socks_proxy) -> None:
    async def exercise() -> None:
        async with await AsyncClient(TOKEN).connect_udp(53, timeout=1) as connection:
            reply = await connection.request(b"async", timeout=1)
            assert reply.data == b"async"
            assert reply.host == "server.tailcat"
            assert reply.port == 53

    asyncio.run(exercise())


def test_udp_rejects_oversized_payload(fake_socks_proxy) -> None:
    with (
        Client(TOKEN).connect_udp(53, timeout=1) as connection,
        pytest.raises(ValueError, match="maximum is 1232"),
    ):
        connection.send(b"x" * (MAX_UDP_PAYLOAD + 1))


def test_udp_address_codecs() -> None:
    assert _encode_address("192.0.2.1", 53) == b"\x01\xc0\x00\x02\x01\x005"
    assert _encode_address("server.tailcat", 53).startswith(b"\x03\x0eserver.tailcat")
    with pytest.raises(ValueError, match="between 0 and 65535"):
        _encode_address("server.tailcat", -1)
    with pytest.raises(UDPError, match="fragmented"):
        _decode_datagram(b"\x00\x00\x01\x01\xc0\x00\x02\x01\x005payload")


def test_udp_receive_timeout(fake_socks_proxy) -> None:
    with Client(TOKEN).connect_udp(53, timeout=1) as connection:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            connection.receive(timeout=0.05)
        assert time.monotonic() - started < 1
