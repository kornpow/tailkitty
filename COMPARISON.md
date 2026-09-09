# Tailkitty and `pytailcat`

Tailkitty and the separate [`pytailcat`](https://pypi.org/project/pytailcat/) distribution are
independent Python projects built around upstream
[Tailscale Tailcat](https://github.com/tailscale/tailcat). They are not rename-compatible packages:
install and import the one you intend.

This comparison was checked on 2026-09-08 against `pytailcat` 0.1.4 and Tailkitty 0.2.2.

## Summary

- Choose Tailkitty for current Tailcat behavior, pure-Python address tooling, asyncio, managed
  lifecycle, fail-closed bundle verification, and reproducible release evidence.
- Choose `pytailcat` when Python 3.8–3.10 or older macOS deployment targets are required.
- Choose upstream Tailcat directly when no Python API or Python packaging is needed.

## Feature comparison

| Capability | `pytailcat` 0.1.4 | Tailkitty 0.2.2 |
| --- | --- | --- |
| Distribution/import | `pytailcat` | `tailkitty` |
| Upstream data plane | Bundled Tailcat executable | Pinned Tailcat v0.6.0 executable |
| Upstream revision | Pre-release commit `c04c5af` | Signed stable tag `v0.6.0` |
| CLI compatibility | `tailcat` wrapper | `tailkitty` plus `tailcat` alias |
| Address parsing | Delegated to executable | Typed pure-Python `ConnInfo` model |
| Modern address fields | Depends on older bundled executable | Disco key and WireGuard PSK validated and preserved |
| Future address fields | Depends on executable | Unknown root and nested extensions round-trip losslessly |
| DERP expansion | Delegated to executable | Pure Python with bounded ETag cache and stale fallback |
| DNS destinations | Delegated to executable | Pure-Python sync and asyncio resolution |
| Client API | Thin synchronous process wrapper | Typed finite, streaming, sync, and asyncio clients |
| Server API | Synchronous `ServerProcess` | Managed sync/async servers with typed v0.6 options |
| Lifecycle cleanup | Basic process management | Bounded startup, terminate/kill escalation, reaping |
| Bundle verification | Package transport integrity | Runtime target, schema, size, and SHA-256 verification |
| Invalid bundle policy | Not documented as fail-closed | Explicit fail-closed behavior |
| Build environment | uv-based | mise + uv with exact Python, Go, and Tailcat pins |
| Wheel checks | Prebuilt wheel matrix | Archive, manifest, binary magic, and every `RECORD` entry |
| Data-plane smoke test | Server lifecycle startup | Real encrypted peer handshake through local DERP/STUN |
| Platforms | Five wheel targets | Six wheel targets, including Windows ARM64 |
| Python requirement | 3.8+ | 3.11+ |
| macOS floor | Older Intel/ARM targets | macOS 12+ |
| Project license | BSD-3-Clause | MIT; bundled Tailcat remains BSD-3-Clause |

Both projects retain the correct architectural boundary: the complex, interoperable network data
plane is native Go. Tailkitty's “pure Python” claim applies to address parsing, DNS lookup, and DERP
resolution—not to WireGuard, NAT traversal, or relay transport.

## What Tailkitty deliberately does not claim

- Tailkitty is not an official Tailscale product.
- It is not a pure-Python VPN or a replacement Tailscale control plane.
- It has not demonstrated a general throughput advantage over `pytailcat`; both ultimately depend
  on Tailcat and network path behavior.
- More validation does not replace PyPI/package-manager trust or an upstream security review.
- Newer Python and macOS minimums are real compatibility costs, not hidden implementation details.

## Why a separate name exists

The `pytailcat` name belongs to another project. Tailkitty uses distinct distribution, import, and
primary CLI names to avoid dependency confusion and accidental replacement. The optional `tailcat`
command is only a compatibility alias inside an environment where Tailkitty was deliberately
installed.

For architectural details, see [docs/architecture.md](docs/architecture.md). For the exact current
platform matrix, see [README.md](README.md#supported-wheels).
