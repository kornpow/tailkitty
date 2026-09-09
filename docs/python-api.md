# Python API guide

Tailkitty's public Python API combines pure-Python address tooling with managed access to the
bundled Tailcat data plane. The package includes a `py.typed` marker and is checked with strict
mypy on Python 3.11 and 3.13.

```console
uv add tailkitty
```

## Choose the right API

| Need | API |
| --- | --- |
| Decode or validate an address | `parse_token()` |
| Expand a short address | `resolve_token()` |
| Accept an address or DNS name | `resolve_destination()` |
| Send one finite request | `Client.request()` |
| Keep exit status and stderr | `Client.run()` |
| Stream in both directions | `Client.connect()` |
| Exchange UDP datagrams | `Client.connect_udp()` |
| Send bytes with a one-line helper | `send()` |
| Run a managed server | `ServerProcess` |
| Do the same work with asyncio | `AsyncClient`, `AsyncServerProcess` |
| Invoke an arbitrary Tailcat command | `run()`, `run_async()` |
| Inspect the selected backend | `inspect_backend()`, `diagnostics()` |

Only the address, DNS, and DERP functions are binary-free. Client, server, execution, and
diagnostic APIs require a bundled or configured native backend.

## Addresses

### Parse and validate

```python
from tailkitty import TokenError, parse_token

try:
    info = parse_token("tc...")
except TokenError as exc:
    print(f"invalid address: {exc}")
else:
    print(info.server_public.hex())
    print(info.server_disco_public.hex() if info.server_disco_public else None)
    print(info.region_id)
```

`parse_token()` checks base64url, CBOR framing, key lengths, signed integer ranges, and embedded DERP
field types. By default it represents only values physically present in the address. Pass
`restore_implicit=True` to reconstruct compact region and node values needed for operational use:

```python
info = parse_token("tc...", restore_implicit=True)
```

The returned dataclasses are:

```text
ConnInfo
├── server_public: bytes
├── server_disco_public: bytes | None
├── preshared_key: bytes | None
├── regions: list[DerpRegion]
├── region_id: int
└── extensions: dict[Any, Any]

DerpRegion
├── region_id, region_code, region_name
├── nodes: list[DerpNode]
└── extensions

DerpNode
├── name, region_id, hostname, cert_name
├── ipv4, ipv6, stun_port, derp_port, insecure_for_tests
└── extensions
```

Unknown CBOR fields survive a `parse_token()` / `to_token()` round trip through the `extensions`
mappings. Reserved known keys cannot be inserted as extensions.

### Expand a short address

```python
from tailkitty import TokenError, resolve_token

try:
    full_address = resolve_token("tc...", timeout=10)
except TokenError as exc:
    print(f"resolution failed: {exc}")
```

A short address contains a DERP region ID. `resolve_token()` fetches a DERP map, embeds up to two
relay nodes from that region, clears the numeric reference, and preserves security and extension
fields. An already self-contained address is returned unchanged.

Use a dedicated cache or custom map when needed:

```python
from pathlib import Path

from tailkitty import DerpMapCache, resolve_token

cache = DerpMapCache(Path("./private-cache"), max_age=300)
full_address = resolve_token(
    "tc...",
    derp_map_url="https://derp.example/derpmap.json",
    timeout=5,
    cache=cache,
)
```

The cache has a 5 MiB response limit, private file permissions, atomic replacement, ETag
revalidation, and stale fallback after refresh failures.

### Resolve an address or DNS destination

```python
from tailkitty import resolve_destination

address = resolve_destination("service.example.com", timeout=5)
```

The DNS name must have a TXT record whose concatenated content starts with `tailcat=`. The returned
address is validated before use. The asynchronous equivalent is
`await resolve_destination_async(...)`.

DNS records are public. DNS lookup provides naming, not authorization.

## Synchronous client

`Client` accepts either a literal address or a DNS destination. Resolution is cached on that client
instance until `refresh()` is called.

### Finite request and response

```python
from tailkitty import Client

client = Client("tc...", dns_timeout=5)
reply = client.request(b"hello", port=8080, timeout=30)
```

`request()` closes stdin after sending the payload, waits for completion, raises
`subprocess.CalledProcessError` for a non-zero exit, and returns stdout as bytes.

Use `run()` when status and stderr matter:

```python
result = client.run(b"hello", port=8080, timeout=30, check=False)
print(result.returncode)
print(result.stdout)
print(result.stderr)
```

String payloads are UTF-8 encoded. Ports must be between 0 and 65535. Port `0` omits the explicit
port argument and selects Tailcat's default one-shot port.

### Streaming connection

```python
import subprocess

from tailkitty import Client

process = Client("tc...").connect(
    port=8080,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
try:
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(b"request")
    process.stdin.close()
    response = process.stdout.read()
finally:
    if process.poll() is None:
        process.terminate()
    process.wait(timeout=2)
```

`connect()` returns the underlying `subprocess.Popen[bytes]`. The caller owns its I/O, timeout,
termination, and reaping.

For a minimal one-shot exchange, `send(destination, data, port=0, timeout=None)` is a convenience
wrapper around `Client(destination).request(...)`.

## UDP datagrams

`connect_udp()` returns a managed connection that keeps datagram boundaries intact:

```python
from tailkitty import Client, MAX_UDP_PAYLOAD

with Client("tc...").connect_udp(5353, timeout=10) as connection:
    connection.send(b"first datagram")
    response = connection.receive(timeout=3)
    print(response.data, response.host, response.port)

    second = connection.request(b"second datagram", timeout=3)
    assert len(second.data) <= MAX_UDP_PAYLOAD
```

Each `send()` transmits one datagram and each `receive()` returns one immutable `Datagram` with
`data`, `host`, and `port` fields. `request()` is a send followed by one receive; UDP itself does
not guarantee that the response corresponds to the request. A receive timeout raises
`TimeoutError` (`socket.timeout` in synchronous code).

The default target host, `server.tailcat`, means the named Tailcat server. Set `host` to an IP or
hostname only when the server is intentionally configured as an exit node:

```python
connection = Client("tc...").connect_udp(53, host="192.0.2.53")
```

Tailcat's IPv6 tunnel MTU makes 1232 bytes the largest safe UDP payload. Tailkitty rejects larger
writes rather than relying on fragmentation. SOCKS5 fragmentation is not supported. Each
connection owns a private loopback-only SOCKS5 proxy and native Tailcat process; use a context
manager or call `close()`.

The asyncio API has matching semantics:

```python
from tailkitty import AsyncClient

async with await AsyncClient("tc...").connect_udp(5353, timeout=10) as connection:
    response = await connection.request(b"datagram", timeout=3)
    print(response.data)
```

On the server, start the UDP application on localhost first, then expose the matching port:

```python
from tailkitty import ServerProcess

with ServerProcess(udp=[5353, 9000], key="new", allow=["nodekey:..."]) as server:
    print(server.token)
    input("Press Enter to stop the UDP tunnel... ")
```

`udp` accepts one integer or an iterable of integers. It is opt-in and independent of TCP `serve`;
the bundled backend forwards only the selected Tailcat UDP ports to the same ports on `127.0.0.1`.
This server feature is a Tailkitty patch to the pinned executable. An unpatched external backend
selected through `TAILKITTY_BACKEND` may reject `--udp`.

## Managed synchronous server

```python
from tailkitty import ServerProcess

server = ServerProcess(
    serve=[8080, 8443],
    key="new",
    allow=["nodekey:..."],
    full_address=False,
    use_preshared_key=True,
)

try:
    address = server.start(timeout=20)
    print(address)
    print(server.process.pid)
finally:
    server.stop(grace_period=2)
```

Prefer the context-manager form:

```python
with ServerProcess(serve=8080, key="new", allow=[]) as server:
    print(server.token)
    assert server.is_running
```

`allow=None` preserves Tailcat's allow-all default. `allow=[]` becomes `--allow=none`. They are not
equivalent.

### Server options

| Argument | Meaning |
| --- | --- |
| `serve` | Port, service name, or iterable; for example `8080` or `[80, "ssh"]` |
| `key` | `new`, a saved key name, or a private key path |
| `allow` | Client node public keys; `None` allows all and `[]` denies all |
| `verbose` | Enable upstream network logging |
| `full_address` | Embed DERP details in the advertised address |
| `derp_map_url` | Override the DERP map URL |
| `use_preshared_key` | Explicitly enable or disable address PSKs; `None` uses upstream default |
| `files` | File-service root and optional mode suffix |
| `ssh_authorized_keys` | One source or a sequence of files, literal keys, or `user@github` values |
| `udp` | UDP port or iterable forwarded to matching localhost UDP ports |
| `extra_args` | Escape hatch for upstream flags not modeled yet |
| `stdin`, `stdout`, `stderr` | Synchronous child-process stream targets |
| `env` | Environment additions for the child process |

The implementation uses Tailcat's `TAILCAT_ADDR_FILE` mechanism so startup does not consume
stdout. `start()` polls that private temporary file until a valid address appears, the child exits,
or the timeout expires. Failure paths terminate and reap the process.

File and authenticated SSH example:

```python
from pathlib import Path

from tailkitty import ServerProcess

with ServerProcess(
    serve=["files", "ssh"],
    files=Path("/srv/share"),
    ssh_authorized_keys=["alice@github", "/etc/ssh/authorized_keys"],
    allow=["nodekey:..."],
) as server:
    print(server.token)
```

## Asyncio client and server

```python
import asyncio

from tailkitty import AsyncClient, AsyncServerProcess


async def main() -> None:
    client = AsyncClient("tc...")
    reply = await client.request(b"hello", port=8080, timeout=30)
    print(reply)

    async with AsyncServerProcess(serve=8080, key="new", allow=[]) as server:
        print(server.token)


asyncio.run(main())
```

`AsyncClient.connect()` returns `asyncio.subprocess.Process`. `AsyncClient.run()` mirrors the sync
finite-exchange result. Timeout and cancellation paths kill and reap the client process before
propagating the exception. `AsyncServerProcess.stop()` first terminates, then kills after its grace
period.

Call `AsyncClient.refresh()` after a DNS record changes. The next operation performs another async
lookup.

## Low-level Tailcat commands

Use `run()` for an upstream command that does not yet have a typed facade:

```python
from tailkitty import run

result = run(
    ["ping", "--until-direct", "--timeout=10s", "tc..."],
    capture_output=True,
    text=True,
    check=False,
    timeout=15,
)
print(result.stdout, result.stderr, result.returncode)
```

The asynchronous equivalent always captures stdout and stderr:

```python
from tailkitty import run_async

result = await run_async(["parse", "tc..."], timeout=10)
```

`run()` follows `subprocess.run()` conventions and accepts additional keyword arguments. Do not
pass mutually incompatible subprocess options such as both `capture_output=True` and an explicit
`stdout`.

## Backend inspection

```python
from tailkitty import diagnostics, inspect_backend

backend = inspect_backend()
print(backend.path)
print(backend.source)  # environment, bundle, development, or path

report = diagnostics()
print(report["backend"])
```

`diagnostics()` requires a usable backend. When it selects a wheel bundle, the report includes the
target, wheel tag, Tailcat version, compiler version, size, digest, and verified status.
`inspect_backend()` returns `BackendInfo`; verified bundle metadata is represented by
`BundleManifest`. Both are immutable dataclasses. The package version is available as
`tailkitty.__version__`.

## Exceptions

| Exception | Raised by |
| --- | --- |
| `TokenError` | Address parsing and resolution |
| `DestinationError` | DNS/literal destination lookup |
| `DerpMapError` | Direct DERP cache use |
| `BackendNotFound` | Backend discovery and integrity translation |
| `BundleError` | Direct bundle validation |
| `ServerStartError` | Managed server exits before advertising an address |
| `UDPError` | SOCKS5 negotiation, framing, subprocess, or closed-connection failure |
| `TimeoutError` | Managed startup or async operation timeout |
| `subprocess.TimeoutExpired` | Synchronous finite client timeout |
| `subprocess.CalledProcessError` | Checked client or low-level command fails |

Public symbols are curated in `tailkitty.__all__`. Import public APIs from `tailkitty`, not from
private implementation modules unless you are contributing to Tailkitty itself.

## Related documentation

- [Recipes](recipes.md)
- [Troubleshooting](troubleshooting.md)
- [Architecture](architecture.md)
- [Security policy](../SECURITY.md)
