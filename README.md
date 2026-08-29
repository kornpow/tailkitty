# Tailkitty

[![PyPI](https://img.shields.io/pypi/v/tailkitty.svg)](https://pypi.org/project/tailkitty/)
[![Python](https://img.shields.io/pypi/pyversions/tailkitty.svg)](https://pypi.org/project/tailkitty/)
[![CI](https://github.com/kornpow/tailkitty/actions/workflows/ci.yml/badge.svg)](https://github.com/kornpow/tailkitty/actions/workflows/ci.yml)

Python tooling for [Tailscale Tailcat](https://github.com/tailscale/tailcat): encrypted,
account-free, netcat-style connections over Tailscale's data plane.

Tailkitty implements connection tokens, DNS destination lookup, and DERP-map resolution in
Python. For interoperable network transport, its platform wheels contain a pinned upstream
Tailcat executable whose platform, version, size, and SHA-256 digest are checked before execution.

> [!WARNING]
> Both upstream Tailcat and Tailkitty are experimental. Do not depend on stable token, CLI, or API
> compatibility before a stable release.

## Why use it?

- Inspect, validate, and resolve Tailcat tokens without starting a native process.
- Use typed synchronous and asyncio clients instead of assembling subprocess commands.
- Manage server startup, readiness, timeouts, and cleanup safely from Python.
- Keep upstream CLI compatibility for streaming, forwarding, ping, SOCKS, SSH, and key commands.
- Install a self-contained platform wheel with runtime bundle-integrity checks.
- Reproduce releases with pinned Python, Go, uv, Tailcat, and cross-platform build inputs.

## Contents

- [Install](#install)
- [Quickstart](#quickstart)
- [CLI](#cli)
- [Python API](#python-api)
- [How it works](#how-it-works)
- [Security](#security)
- [Compatibility and limitations](#compatibility-and-limitations)
- [Development](#development)

## Install

### Install a bundled wheel

For the command-line tool:

```console
uv tool install tailkitty
tailkitty doctor
```

For library use inside a project:

```console
uv add tailkitty
```

To build and install the host wheel from this checkout instead:

```console
mise install
uv sync --all-groups --locked
mise run wheel
uv tool install --force ./dist/tailkitty-0.1.0-py3-none-<platform>.whl
```

A bundled wheel does not require Go at runtime. It provides the `tailkitty` command plus `tailcat`
as an upstream-compatible alias. See the [platform matrix](#supported-platform-wheels) for tags.

### Work from this checkout

Install [mise](https://mise.jdx.dev/), then run:

```console
mise install
mise run setup
uv run tailkitty doctor
```

This installs Python 3.13.11, Go 1.26.5, and uv 0.12.7; synchronizes the uv environment; and
builds the pinned development backend at `.tools/bin/tailcat`.

### Use only the Python functionality

Token parsing, token resolution, DERP caching, and DNS destination lookup are pure Python. They can
be used from a binary-free source installation. Network commands and `Client`/`ServerProcess`
still require either a bundled wheel or an executable selected by `TAILKITTY_BACKEND`.

## Quickstart

The following example creates an ephemeral, one-shot byte stream between two machines. Both need
the `tailkitty` command from a bundled wheel or configured backend.

On the receiving machine:

```console
tailkitty --key=new < /dev/null
# 🐈 Server listening with new address: tc...
```

Copy the complete `tc...` address to the sending machine:

```console
printf 'hello from tailcat\n' | tailkitty --key=new 'tc...'
```

The message appears on the receiving terminal. The server accepts one connection and exits.
Tailcat is full-duplex; remove `< /dev/null` if you also want to type a response on the server.

The PowerShell equivalents are:

```powershell
$null | tailkitty --key=new
'hello from tailcat' | tailkitty --key=new 'tc...'
```

> [!IMPORTANT]
> A server allows any client by default. For controlled access, generate a client key with
> `tailkitty genkey --client` and start the server with `--allow=<client-public-key>`. See
> [Security](#security) before exposing a service.

## CLI

Three commands are implemented natively in Python:

```console
tailkitty parse 'tc...'             # decode and validate a token as JSON
tailkitty resolve 'tc...'           # embed the referenced DERP region
tailkitty doctor                    # show the selected backend and provenance
tailkitty doctor --json             # machine-readable diagnostics
```

Every other argument sequence is passed unchanged to the upstream-compatible data plane:

```console
tailkitty --serve=8080,8443
tailkitty 'tc...' 8080
tailkitty ping 'tc...'
tailkitty ssh 'tc...'
tailkitty socks 'tc...' curl http://server.tailcat:8080/
tailkitty genkey --client
```

Run `tailkitty --help` for the Python command summary. Upstream commands retain their own help, for
example `tailkitty genkey --help`.

Destinations may be literal connection tokens or DNS names with a TXT record of the form:

```dns
server.example.com. 300 IN TXT "tailcat=tc..."
```

## Python API

### Inspect tokens without the native backend

```python
from tailkitty import parse_token, resolve_token

info = parse_token("tc...")
print(info.server_public.hex())
print(info.region_id)

# Fetch and embed the referenced DERP region. Cached maps are revalidated with ETags.
self_contained_token = resolve_token("tc...")
```

Malformed tokens raise `TokenError`. DNS lookup raises `DestinationError`, and DERP-map failures
raise `DerpMapError` or are translated to `TokenError` by `resolve_token()`.

### Send a finite request

```python
import subprocess

from tailkitty import Client

client = Client("tc...")  # A DNS name with a tailcat= TXT record also works.

# request() checks the exit status and returns stdout bytes.
response = client.request(b"GET / HTTP/1.0\r\n\r\n", port=8080, timeout=30)

# run() preserves status, stdout, and stderr; checking is opt-in.
result = client.run(b"hello", timeout=30, check=False)
if result.returncode:
    raise subprocess.CalledProcessError(
        result.returncode, result.args, result.stdout, result.stderr
    )
```

Use `Client.connect()` when a long-lived, full-duplex `subprocess.Popen` stream is needed. DNS
results are cached on each client; call `client.refresh()` to resolve the destination again.

### Manage a server

```python
from tailkitty import ServerProcess

with ServerProcess(serve=[8080, 8443], key="new", allow=["nodekey:..."]) as server:
    print(f"share this address with the allowed client: {server.token}")
    print(f"native process id: {server.process.pid}")
    # The context remains active while the remote client uses the forwarded ports.
```

`ServerProcess.start()` waits up to 20 seconds by default for a validated connection token. The
context manager terminates the server and escalates to a kill if it does not stop within its grace
period. `allow=[]` means `--allow=none`; `allow=None` preserves upstream's allow-all default.

### Use asyncio

```python
import asyncio

from tailkitty import AsyncClient, AsyncServerProcess


async def main() -> None:
    response = await AsyncClient("tc...").request(b"hello", timeout=30)
    print(response)

    async with AsyncServerProcess(serve=8080, key="new", allow=[]) as server:
        print(server.token)  # Starts successfully, but rejects all clients.


asyncio.run(main())
```

Cancellation and timeout paths kill and reap their native child process before propagating the
exception.

### API behavior at a glance

| API | Backend needed? | Result |
| --- | --- | --- |
| `parse_token(token)` | No | Typed `ConnInfo` |
| `resolve_token(token)` | No | Self-contained token string |
| `resolve_destination(name)` | No | Validated token string |
| `Client.request(data, ...)` | Yes | Response `bytes`; raises on non-zero exit |
| `Client.run(data, ...)` | Yes | `subprocess.CompletedProcess[bytes]` |
| `Client.connect(...)` | Yes | Streaming `subprocess.Popen[bytes]` |
| `ServerProcess(...)` | Yes | Managed synchronous server |
| `AsyncClient` / `AsyncServerProcess` | Yes | Asyncio equivalents |
| `run(arguments, ...)` / `run_async(arguments, ...)` | Yes | Low-level upstream command execution |

The package is marked with `py.typed` and is checked with strict mypy.

## How it works

Tailcat's connection-token format is CBOR encoded as unpadded base64url after a `tc` prefix. That
wire format and the lightweight control-plane operations are implemented in Python. The encrypted
transport remains upstream because it depends on Tailscale's Go implementations of magicsock,
userspace WireGuard, DERP routing, and gVisor netstack.

```text
Python caller / CLI
        |
        +-- token.py -------- CBOR token codec (pure Python)
        +-- destination.py -- token or DNS TXT resolution (pure Python)
        +-- derp.py --------- DERP-map cache and HTTP revalidation (pure Python)
        +-- client.py ------- typed sync/async client facade
        +-- process.py ------ managed server and subprocess lifecycle
        |
        +-- backend.py ------ backend discovery and command execution
                |
                +-- verified wheel bundle, development build, or explicit executable
```

Backend discovery is deterministic and fail-closed:

1. Executable named by `TAILKITTY_BACKEND`; an invalid path is an error.
2. Platform-compatible bundled executable with a valid integrity manifest.
3. Development executable at `.tools/bin/tailcat` (then the legacy `tailcat-go` filename).
4. A `tailcat-go` executable on `PATH`.

If a bundled executable is present but fails validation, Tailkitty reports an integrity error
instead of silently selecting another backend. `tailkitty doctor --json` shows the selected source,
target, upstream revision, compiler, size, and digest.

DERP maps use a one-hour disk cache by default, ETag revalidation, a 5 MiB response limit, atomic
cache writes, and stale-cache fallback when a refresh fails.

## Security

- Tailcat traffic uses upstream's encrypted Tailscale data plane, but authorization is a separate
  choice: omitting `--allow` allows every client that can reach the server.
- A connection token contains routing information and a server public key, not the server's private
  key. Nevertheless, avoid publishing an active unrestricted server address.
- Use `tailkitty genkey --client`, then pass its public key through `--allow` or `allow=[...]` for
  restricted access. Passing an empty Python list denies every client.
- `TAILKITTY_BACKEND` is an explicit code-execution override. Tailkitty verifies that it is
  executable but cannot prove the provenance of a user-selected file.
- Bundled executables are checked against their manifest for schema, upstream module and revision,
  runtime platform, filename safety, symlinks, size, and SHA-256 before use.
- Do not include active addresses, saved private keys, or verbose networking logs in public bug
  reports without reviewing them first.

Read [SECURITY.md](SECURITY.md) for the bundle trust model and reporting guidance.

## Compatibility and limitations

### Supported platform wheels

| Operating system | Architecture | Wheel platform tag |
| --- | --- | --- |
| macOS 12 or newer | arm64 | `macosx_12_0_arm64` |
| macOS 12 or newer | x86-64 | `macosx_12_0_x86_64` |
| Linux, glibc 2.17 or newer | x86-64 | `manylinux_2_17_x86_64` |
| Linux, glibc 2.17 or newer | arm64 | `manylinux_2_17_aarch64` |
| Windows | x86-64 | `win_amd64` |

Python 3.11 and newer is supported. Wheels use the `py3-none-<platform>` tag because the Python
modules are not tied to a CPython ABI; the embedded executable is still platform-specific.

Current limitations:

- There is no pure-Python network data plane. A binary-free install supports control-plane APIs
  only.
- Public DERP relays are rate-limited external infrastructure with no uptime guarantee. A relay
  timeout does not necessarily indicate a local packaging or token error.
- Upstream Tailcat is experimental and its token and CLI interfaces can change.
- Only the five targets above are built. Other platforms may use an explicitly supplied compatible
  backend, but are not release-tested here.

See [COMPARISON.md](COMPARISON.md) for a feature-by-feature comparison with the existing PyPI
project.

## Development

The normal contributor loop is:

```console
mise install
uv sync --all-groups --locked
mise run test
```

Useful build and verification commands:

```console
mise run backend          # development helper in .tools/bin
mise run bundle           # host helper in src/tailkitty/bin
mise run bundle-verify    # verify the host bundle manifest
mise run wheel            # build the host platform wheel
mise run wheels           # cross-build and verify all five wheels

# Install and inspect a newly built host wheel in isolation:
uv run python -m scripts.smoke_wheel dist/wheels/<host-wheel>.whl

# Exercise the minimum supported Python version:
uv run --isolated --python 3.11 --all-groups pytest
```

Generated executables, manifests, wheel files, and source archives are build artifacts; do not edit
them manually. The release pin is defined in `src/tailkitty/constants.py`, and Go must match the
version in `.mise.toml` exactly.

Additional documentation:

- [BUILDING.md](BUILDING.md) — reproducible binary and wheel pipeline
- [SECURITY.md](SECURITY.md) — integrity checks and trust boundaries
- [COMPARISON.md](COMPARISON.md) — differences from the existing PyPI package
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — bundled upstream licensing
- [CHANGELOG.md](CHANGELOG.md) — release history
- [ITERATIONS.md](ITERATIONS.md) — the initial 100-pass implementation audit

Coding agents and automated contributors must also follow [AGENTS.md](AGENTS.md).

## License and relationship to Tailscale

This project is licensed under the BSD 3-Clause License. Bundled wheels contain upstream Tailcat
and its Go dependencies; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Tailcat and Tailscale are trademarks of Tailscale Inc. This project is not an official Tailscale
product.
