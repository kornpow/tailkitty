# Tailkitty architecture

Tailkitty is intentionally a Python control plane around an upstream Tailcat data plane. This
boundary is a product decision, not an unfinished port.

## Component boundary

```text
Application or command line
          |
          v
┌──────────────────────── Tailkitty (Python) ────────────────────────┐
│ CLI dispatch      Python-native commands vs upstream pass-through  │
│ Address model     CBOR/base64url parsing, validation, preservation │
│ Destination       Literal addresses and DNS TXT records            │
│ DERP cache        Bounded fetch, ETag, atomic private cache         │
│ Client facade     Sync and asyncio finite/streaming operations      │
│ Server lifecycle  Startup readiness, timeout, termination, reaping  │
│ Backend trust     Discovery, platform match, manifest verification  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ subprocess / stdio
                               v
┌────────────────────── Tailcat (pinned Go build) ───────────────────┐
│ magicsock │ discovery │ STUN │ DERP │ WireGuard │ gVisor netstack │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ encrypted network traffic
                               v
                         Remote Tailcat peer
```

## Why the data plane is not pure Python

Tailcat interoperability depends on Tailscale's implementations of:

- WireGuard session establishment and encryption.
- Disco-key peer discovery and endpoint exchange.
- STUN-based NAT traversal and UDP hole punching.
- Application UDP flows with preserved datagram boundaries.
- DERP relay transport and path selection.
- A userspace TCP/IP stack based on gVisor netstack.

A simplified Python transport could talk to itself, but it would no longer be Tailcat-compatible.
Recreating the complete stack would substantially increase security and maintenance risk. Tailkitty
therefore implements the inspectable, useful control-plane pieces in Python and pins the upstream
transport that defines network behavior.

Future stable upstream C bindings may permit in-process Python bindings. That would change the
process boundary, not the ownership of the cryptographic and network protocol implementation.

## CLI dispatch

`tailkitty.cli` owns only:

- `parse`
- `resolve`
- `doctor`
- `--version`
- top-level `--help`

Every other argument sequence, including no arguments, is executed unchanged by the selected
Tailcat backend. On POSIX systems Tailkitty uses `execv`, so signals and terminal behavior belong
directly to Tailcat rather than an unnecessary wrapper process.

This small ownership surface prevents Tailkitty's parser from lagging or subtly changing upstream
commands.

## Typed UDP flow

Each `UDPConnection` owns a private loopback SOCKS5 UDP association. Python encodes and validates
the SOCKS5 datagram envelope; the upstream process carries each payload over Tailcat's WireGuard
tunnel without merging datagrams. A small recorded source patch adds opt-in `serve --udp`
forwarding from selected tunnel ports to matching `127.0.0.1` UDP ports.

This keeps the cryptographic and network stack native while exposing typed synchronous and asyncio
lifecycle APIs. Closing a connection closes its sockets and terminates and reaps the owned Tailcat
process. Payloads larger than Tailcat's 1232-byte safe tunnel size are rejected before sending.

## Address flow

```text
literal tc... ───────────────┐
                             ├─> parse_token ─> ConnInfo
DNS name ─> TXT tailcat=tc...┘                     │
                                                   ├─> inspect / validate
short address ─> region ID ─> DERP map cache ─────┴─> resolve_token
                                                        │
                                                        v
                                             self-contained address
```

The address codec validates known fields against upstream wire types. Unknown fields are retained
at connection, region, and node levels so a parse/resolve/re-encode operation does not erase new
upstream semantics.

The Python resolver is deliberately narrow: it embeds relay details for an existing region. It does
not choose a region, generate cryptographic keys, or alter authorization.

## DERP cache flow

1. Hash the requested map URL to derive private cache filenames.
2. Read and validate cached JSON and metadata if both exist.
3. Return immediately while the entry is younger than `max_age`.
4. Otherwise request the map with `If-None-Match` when an ETag exists.
5. Reject responses larger than 5 MiB or documents without a `Regions` object.
6. Atomically replace cache files with mode `0600` in a directory created with mode `0700`.
7. Use the last valid cached value if a refresh fails.

The default cache lifetime is one hour. Cache availability does not override address validation.

## Backend discovery and trust

```text
TAILKITTY_BACKEND set?
  ├─ yes, executable ───────────────> use explicit backend
  ├─ yes, invalid ──────────────────> fail
  └─ no
      │
      v
bundled manifest present?
  ├─ valid + runtime-compatible ────> use verified bundle
  ├─ present but invalid ───────────> fail closed
  └─ absent
      │
      v
source-checkout backend exists? ────> use development backend
      │
      v
tailcat-go on PATH? ────────────────> use external backend
      │
      v
BackendNotFound
```

An explicit backend is a user trust decision. It is checked for executability, not origin or
content. A wheel bundle is verified against its manifest before every uncached selection.

## Bundle production

The builder:

1. Enforces the exact mise-pinned Go compiler with `GOTOOLCHAIN=local`.
2. Downloads the immutable Tailcat module version.
3. Copies it into temporary writable storage.
4. Applies every sorted patch under `patches/`, recording each digest.
5. Reads upstream's official `build-tags.txt`.
6. Cross-compiles with CGO disabled, baseline CPU features, stripped symbols, no VCS metadata, and
   no Go build ID.
7. Checks executable format and minimum plausible size.
8. Writes a manifest containing the build inputs and output digest.
9. Builds one non-pure wheel per target in isolated staging.
10. Verifies wheel paths, metadata, executable format, bundle digest, and every `RECORD` entry.

Cross-compiled binaries are structurally verified. The host wheel additionally performs a bounded
real encrypted peer handshake through an isolated local DERP/STUN relay.

## Managed server lifecycle

`ServerProcess` and `AsyncServerProcess` use Tailcat's `TAILCAT_ADDR_FILE` environment variable to
capture readiness without consuming stdout.

```text
construct arguments
      │
create private temporary address file location
      │
spawn tailcat serve
      │
poll: process exit? valid address? deadline?
      │
return address and running process
      │
context exit / stop / exception / cancellation
      │
terminate ─> bounded grace period ─> kill if needed ─> reap
```

The synchronous API exposes configurable standard streams. The asyncio API uses pipes and mirrors
timeout and cleanup behavior.

## Core invariants

- The data plane stays compatible with the pinned Tailcat revision.
- Address transformations preserve known security fields and unknown extensions.
- A corrupt bundle cannot silently fall back to another executable.
- `allow=None` means upstream allow-all; `allow=[]` means deny all.
- Timeout and cancellation paths terminate and reap child processes.
- External responses and local caches are bounded and validated.
- Generated executables and manifests are never committed.
- Wheels are platform-specific even though Python modules are ABI-independent.

These invariants are repeated in [AGENTS.md](../AGENTS.md) because automated changes must preserve
them as carefully as human contributions.

## Repository map

| Path | Responsibility |
| --- | --- |
| `src/tailkitty/token.py` | Address wire format and models |
| `src/tailkitty/destination.py` | Literal and DNS destination resolution |
| `src/tailkitty/derp.py` | DERP-map fetch and cache |
| `src/tailkitty/client.py` | Sync and asyncio clients |
| `src/tailkitty/process.py` | Managed servers and async command execution |
| `src/tailkitty/backend.py` | Backend discovery and execution |
| `src/tailkitty/bundle.py` | Runtime bundle verification |
| `src/tailkitty/cli.py` | Native commands and upstream dispatch |
| `scripts/` | Build, verification, smoke-test, and release-drift tools |
| `hatch_build.py` | Platform-wheel build hook |
| `tests/` | Deterministic unit and subprocess tests |

## Related documentation

- [Python API](python-api.md)
- [Building](../BUILDING.md)
- [Security](../SECURITY.md)
- [Agent instructions](../AGENTS.md)
