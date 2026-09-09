# Tailkitty

[![PyPI](https://img.shields.io/pypi/v/tailkitty.svg)](https://pypi.org/project/tailkitty/)
[![Python](https://img.shields.io/pypi/pyversions/tailkitty.svg)](https://pypi.org/project/tailkitty/)
[![CI](https://github.com/kornpow/tailkitty/actions/workflows/ci.yml/badge.svg)](https://github.com/kornpow/tailkitty/actions/workflows/ci.yml)

Python tooling and verified platform wheels for
[Tailscale Tailcat](https://github.com/tailscale/tailcat): encrypted, account-free connections over
Tailscale's data plane.

Tailkitty gives Python users two things:

- Pure-Python tools for Tailcat addresses, DNS destinations, and DERP-map resolution.
- A pinned Tailcat v0.6.0 executable for the interoperable WireGuard, DERP, NAT-traversal, and
  userspace-networking data plane.

The executable in each platform wheel is checked for its target, version, size, and SHA-256 digest
before Tailkitty runs it. You do not need Go, root access, a Tailscale account, or a Tailscale
control server.

> [!WARNING]
> Tailcat and Tailkitty are experimental. Their address, CLI, and Python APIs may change before a
> stable release.

## Start here

| Goal | Start with |
| --- | --- |
| Send bytes between two computers | [One-shot pipe](#one-shot-pipe) |
| Reach a remote web app or database | [Forward a port](#forward-a-port) |
| Exchange UDP datagrams | [Typed UDP](#typed-udp) |
| Use Tailcat from Python | [Python quickstart](#python-quickstart) |
| Transfer files or use SSH | [Recipes](https://github.com/kornpow/tailkitty/blob/main/docs/recipes.md) |
| Diagnose an installation | [Troubleshooting](https://github.com/kornpow/tailkitty/blob/main/docs/troubleshooting.md) |
| Understand the trust boundary | [Security](https://github.com/kornpow/tailkitty/blob/main/SECURITY.md) |
| Develop or package Tailkitty | [Contributing](https://github.com/kornpow/tailkitty/blob/main/CONTRIBUTING.md) |

## Install

Install the command-line application with uv:

```console
uv tool install tailkitty
tailkitty doctor
```

Add the typed Python library to a project with:

```console
uv add tailkitty
```

`pip install tailkitty` also works. A supported platform receives a self-contained wheel with both
the `tailkitty` command and a `tailcat` compatibility alias. Confirm what will run with:

```console
tailkitty --version
tailkitty doctor
tailkitty version
```

These report the Tailkitty version, verified backend provenance, and upstream Tailcat version,
respectively.

### Supported wheels

| Operating system | Architecture | Wheel platform tag |
| --- | --- | --- |
| macOS 12+ | Apple Silicon | `macosx_12_0_arm64` |
| macOS 12+ | Intel x86-64 | `macosx_12_0_x86_64` |
| Linux, glibc 2.17+ | x86-64 | `manylinux_2_17_x86_64` |
| Linux, glibc 2.17+ | ARM64 | `manylinux_2_17_aarch64` |
| Windows | x86-64 | `win_amd64` |
| Windows | ARM64 | `win_arm64` |

Python 3.11 and newer is supported. The Python code is ABI-independent, but the bundled executable
is platform-specific. Unsupported systems can use the pure-Python control-plane features or set
`TAILKITTY_BACKEND` to a compatible Tailcat executable.

## Quickstart

Both machines need Tailkitty installed. A `tc...` address is case-sensitive; copy it exactly and
quote it in shell commands.

### One-shot pipe

On the receiving machine:

```console
tailkitty --key=new < /dev/null
# 🐈 Server listening with new address: tc...
```

On the sending machine, paste the complete address:

```console
printf 'hello from Tailkitty\n' | tailkitty --key=new 'tc...'
```

The receiver prints the message and both processes exit. This mode carries one finite byte stream;
use port serving or `Client.connect()` for a long-lived connection.

PowerShell equivalents:

```powershell
$null | tailkitty --key=new
'hello from Tailkitty' | tailkitty --key=new 'tc...'
```

### Forward a port

Suppose a web application is listening on port 8080 of the server. Start Tailkitty there:

```console
tailkitty serve 8080
# 🐈 Server listening with new address: tc...
```

On the client, expose it on local port 18080:

```console
tailkitty forward 'tc...' 18080:8080
```

Open `http://127.0.0.1:18080/`. The forwarder binds to localhost by default and runs until you
press Ctrl-C.

> [!IMPORTANT]
> Anyone who has an unrestricted server address can connect. Use client keys and `--allow` for
> controlled access; do not treat WireGuard encryption as authorization. See
> [Protect a server](https://github.com/kornpow/tailkitty/blob/main/docs/recipes.md#protect-a-server-with-client-keys).

### Python quickstart

On the server:

```python
import time

from tailkitty import ServerProcess

# This allows anyone with the secret address to connect. See the security note below.
with ServerProcess(serve=8080, key="new", allow=None) as server:
    print(server.token, flush=True)
    while True:
        time.sleep(60)
```

On the client, after receiving the complete address:

```python
from tailkitty import Client

response = Client("tc...").request(
    b"GET / HTTP/1.0\r\nHost: localhost\r\n\r\n",
    port=8080,
    timeout=30,
)
print(response.decode(errors="replace"))
```

The context manager waits for a validated address, then terminates and reaps the native process on
exit. See the [Python API guide](https://github.com/kornpow/tailkitty/blob/main/docs/python-api.md)
for asyncio, streaming, token handling, server
options, exceptions, and low-level execution.

### Typed UDP

Tailkitty preserves application datagram boundaries instead of treating UDP as a byte stream. On
the server, bind your UDP application to localhost and opt in to the same Tailcat port:

```python
from tailkitty import ServerProcess

with ServerProcess(udp=5353, key="new") as server:
    print(server.token)
    input("Press Enter to stop the UDP tunnel... ")
```

On the client:

```python
from tailkitty import Client

with Client("tc...").connect_udp(5353, timeout=10) as connection:
    reply = connection.request(b"one datagram", timeout=3)
    print(reply.data)
```

`send()` and `receive()` each handle exactly one datagram. Payloads are limited to
`MAX_UDP_PAYLOAD` (1232 bytes), the safe size for Tailcat's tunnel MTU. Asyncio equivalents are
available through `AsyncClient.connect_udp()`.

## CLI model

Tailkitty owns a small Python-native command surface:

```console
tailkitty parse 'tc...'            # validate and decode an address as JSON
tailkitty resolve 'tc...'          # embed the referenced DERP relay details
tailkitty doctor                   # inspect backend selection and provenance
tailkitty doctor --json            # machine-readable diagnostics
tailkitty --version                # Tailkitty package version
```

Everything else passes unchanged to the pinned Tailcat executable:

```console
tailkitty serve --help
tailkitty ping --until-direct 'tc...'
tailkitty forward 'tc...' 18080:8080
tailkitty recv ~/inbox
tailkitty cp report.pdf 'tc...':
tailkitty serve --ssh-authorized-keys=alice@github ssh
tailkitty ssh 'tc...'
tailkitty socks 'tc...' curl http://server.tailcat:8080/
tailkitty genkey --client --key=client-default
```

Run `tailkitty readme` for the documentation embedded in the bundled Tailcat version. Tailkitty's
typed UDP API uses Tailcat v0.6's SOCKS5 UDP association and an auditable bundled patch that adds
opt-in `127.0.0.1` UDP serving to the CLI.

## Addresses and DNS

A Tailcat address starts with `tc` and contains a CBOR document encoded as unpadded base64url. A
current address can contain:

- The server's WireGuard public key.
- A separate discovery public key.
- A WireGuard pre-shared key.
- Either a DERP region ID or embedded relay details.

Tailkitty parses and validates those fields in Python. Unknown future CBOR fields are retained in
the `extensions` mappings on `ConnInfo`, `DerpRegion`, and `DerpNode`, preventing resolution from
silently stripping new upstream fields.

Tailcat commands and `Client` also accept a DNS name with a TXT record like:

```dns
service.example.com. 300 IN TXT "tailcat=tc..."
```

> [!CAUTION]
> DNS is public. Publishing an address removes its normal secrecy. A DNS-named server must
> authenticate clients independently with `--allow`, SSH authorized keys, or both. Never publish
> an unrestricted service, especially `no-auth-ssh`.

Short addresses refer to a DERP region by ID. `tailkitty resolve` expands one into a self-contained
address using a bounded, validated DERP-map cache:

```console
tailkitty parse 'tc...'
tailkitty resolve 'tc...' > full-address.txt
```

## Python API overview

| API | Native backend? | Purpose |
| --- | --- | --- |
| `parse_token(token)` | No | Decode and validate an address into `ConnInfo` |
| `resolve_token(token)` | No | Embed DERP relay details in a short address |
| `resolve_destination(value)` | No | Resolve a literal address or DNS TXT destination |
| `DerpMapCache` | No | Bounded HTTP cache with ETag and stale fallback |
| `Client.request(...)` | Yes | Finite request/response exchange |
| `Client.run(...)` | Yes | Finite exchange with exit status and stderr |
| `Client.connect(...)` | Yes | Full-duplex `subprocess.Popen` connection |
| `Client.connect_udp(...)` | Yes | Datagram-preserving UDP connection |
| `ServerProcess` | Yes | Managed synchronous server |
| `AsyncClient` / `AsyncServerProcess` | Yes | Asyncio equivalents, including UDP |
| `run(...)` / `run_async(...)` | Yes | Low-level Tailcat command execution |
| `diagnostics()` | Yes | Structured backend and environment report |

The distribution includes `py.typed` and is checked with strict mypy. Public exceptions and full
examples are documented in the [Python API guide](https://github.com/kornpow/tailkitty/blob/main/docs/python-api.md).

## Security summary

- Addresses are capability material. Current addresses include a pre-shared key; do not post them
  in logs, screenshots, issues, or public DNS unless another authorization layer is active.
- A server allows every client by default. Generate a client identity with `tailkitty genkey
  --client --key=client-default`, then supply its printed public key with `--allow`.
- `allow=None` in Python preserves the upstream allow-all default. `allow=[]` becomes
  `--allow=none` and denies every client.
- `TAILKITTY_BACKEND` is explicit code-execution authority. Tailkitty checks that the path is
  executable but cannot prove the provenance of a user-selected binary.
- Bundled executables fail closed: a present but invalid bundle raises an integrity error instead
  of falling back to an unverified executable.

Read the [security policy](https://github.com/kornpow/tailkitty/blob/main/SECURITY.md) before
exposing SSH, files, an exit node, or a DNS-named service.

## How it works

```text
Python caller or tailkitty CLI
        |
        +-- token.py -------- address codec and validation (pure Python)
        +-- destination.py -- literal or DNS TXT lookup (pure Python)
        +-- derp.py --------- validated DERP-map cache (pure Python)
        +-- client.py ------- sync and asyncio client facade
        +-- process.py ------ managed server and subprocess lifecycle
        |
        +-- backend.py ------ deterministic backend discovery
                |
                +-- verified wheel bundle
                +-- development build
                +-- explicitly configured upstream executable
```

The encrypted data plane stays upstream because it depends on Tailscale's Go implementations of
magicsock, userspace WireGuard, DERP, and gVisor netstack. Reimplementing only part of that stack in
Python would lose interoperability and security properties. See
[architecture guide](https://github.com/kornpow/tailkitty/blob/main/docs/architecture.md) for the
detailed boundary and data flows.

## Backend selection

Tailkitty selects exactly one backend in this order:

1. `TAILKITTY_BACKEND`, if explicitly set; an invalid path fails immediately.
2. The verified, runtime-compatible executable bundled in the installed wheel.
3. `.tools/bin/tailcat`, then the legacy `.tools/bin/tailcat-go`, in a source checkout.
4. `tailcat-go` on `PATH`.

An installed `tailcat` command is not searched on `PATH` because Tailkitty itself provides that
alias and recursive execution must be avoided. Use `TAILKITTY_BACKEND=/path/to/tailcat` for an
external upstream binary.

## Development

The repository uses mise for tool versions and uv for Python environments:

```console
mise install
mise run setup
mise run test
```

Useful tasks:

```console
mise run backend          # build the pinned development backend
mise run bundle           # build the host bundle
mise run bundle-verify    # verify its manifest and executable
mise run wheel            # build the host wheel
mise run wheels           # build and verify all six wheels
mise run upstream-check   # compare the pin with the latest stable Tailcat release
```

Start with [CONTRIBUTING.md](https://github.com/kornpow/tailkitty/blob/main/CONTRIBUTING.md).
Packaging and release details are in
[BUILDING.md](https://github.com/kornpow/tailkitty/blob/main/BUILDING.md) and
[RELEASING.md](https://github.com/kornpow/tailkitty/blob/main/RELEASING.md). Coding agents must
also follow [AGENTS.md](https://github.com/kornpow/tailkitty/blob/main/AGENTS.md).

## Documentation

- [Recipes](https://github.com/kornpow/tailkitty/blob/main/docs/recipes.md) — pipes, ports, files, SSH, SOCKS, DNS, and key management
- [Python API](https://github.com/kornpow/tailkitty/blob/main/docs/python-api.md) — typed sync/async usage and behavior
- [Troubleshooting](https://github.com/kornpow/tailkitty/blob/main/docs/troubleshooting.md) — bounded diagnostics and common failures
- [Architecture](https://github.com/kornpow/tailkitty/blob/main/docs/architecture.md) — component boundaries, data flows, and invariants
- [Security policy](https://github.com/kornpow/tailkitty/blob/main/SECURITY.md) — threats, authorization, bundle trust, and reporting
- [Building](https://github.com/kornpow/tailkitty/blob/main/BUILDING.md) — reproducible native and wheel builds
- [Releasing](https://github.com/kornpow/tailkitty/blob/main/RELEASING.md) — versioning, verification, publication, and rollback constraints
- [Comparison](https://github.com/kornpow/tailkitty/blob/main/COMPARISON.md) — Tailkitty versus the separate `pytailcat` package
- [Changelog](https://github.com/kornpow/tailkitty/blob/main/CHANGELOG.md) — user-visible release history

## License and relationship to Tailscale

Tailkitty is licensed under the MIT License. Bundled wheels contain upstream Tailcat under its BSD
3-Clause License and other Go dependencies; see
[THIRD_PARTY_NOTICES.md](https://github.com/kornpow/tailkitty/blob/main/THIRD_PARTY_NOTICES.md).

Tailcat and Tailscale are trademarks of Tailscale Inc. Tailkitty is not an official Tailscale
product.
