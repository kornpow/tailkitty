# Tailkitty compared with the existing PyPI project

Both projects expose the upstream Tailcat command through Python and use an upstream-compatible
native data plane. As of 2026-09-04, the existing
[`pytailcat 0.1.4`](https://pypi.org/project/pytailcat/0.1.4/) primarily ships
prebuilt executables with a small process wrapper. This implementation adds substantial Python-side
functionality and a more inspectable supply chain under the distinct Tailkitty name.

| Capability | Existing PyPI project | This implementation |
| --- | --- | --- |
| Upstream-compatible data plane | Bundled executable | Pinned, verified bundled executable |
| Tailcat revision | Pre-release commit `c04c5af` | Tagged Tailcat v0.6.0 |
| Modern addresses | Delegated to older executable | Separate discovery key and WireGuard PSK preserved in Python |
| Token parsing and validation | Delegated to executable | Native Python typed models |
| DERP resolution and caching | Delegated to executable | Native Python with ETag/stale fallback |
| DNS `tailcat=` destination lookup | Delegated to executable | Sync and async Python APIs |
| Process API | Thin synchronous wrapper | Sync/async clients and managed servers |
| Bundle integrity | Package-manager transport integrity | Runtime manifest, target, size, and SHA-256 checks |
| Reproducible local toolchain | Not the focus | mise + uv + exact Go compiler and revision |
| Data-plane testing | Server-start lifecycle test | Bounded real peer-handshake wheel smoke test |
| Release evidence | Prebuilt wheels | Matrix verification, checksums, and provenance workflow |

`pytailcat` supports Python 3.8+ and older macOS deployment targets, while Tailkitty currently
supports Python 3.11+ and macOS 12+. Those are meaningful compatibility advantages for
`pytailcat`; Tailkitty prioritizes typed APIs, modern upstream behavior, and stricter provenance.

The remaining architectural boundary is intentional: reimplementing Tailscale magicsock,
userspace WireGuard, DERP routing, and gVisor netstack faithfully in pure Python would be a separate
networking stack and would create interoperability and security risk. The control-plane and wire
format are Python; the interoperable encrypted transport stays upstream.
