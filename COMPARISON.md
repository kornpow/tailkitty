# Tailkitty compared with the existing PyPI project

Both projects expose the upstream Tailcat command through Python and use an upstream-compatible
native data plane. The existing [`pytailcat`](https://pypi.org/project/pytailcat/) primarily ships
prebuilt executables with a small process wrapper. This implementation adds substantial Python-side
functionality and a more inspectable supply chain under the distinct Tailkitty name.

| Capability | Existing PyPI project | This implementation |
| --- | --- | --- |
| Upstream-compatible data plane | Bundled executable | Pinned, verified bundled executable |
| Token parsing and validation | Delegated to executable | Native Python typed models |
| DERP resolution and caching | Delegated to executable | Native Python with ETag/stale fallback |
| DNS `tailcat=` destination lookup | Delegated to executable | Sync and async Python APIs |
| Process API | Thin synchronous wrapper | Sync/async clients and managed servers |
| Bundle integrity | Package-manager transport integrity | Runtime manifest, target, size, and SHA-256 checks |
| Reproducible local toolchain | Not the focus | mise + uv + exact Go compiler and revision |
| Release evidence | Prebuilt wheels | Matrix verification, checksums, and provenance workflow |

The remaining architectural boundary is intentional: reimplementing Tailscale magicsock,
userspace WireGuard, DERP routing, and gVisor netstack faithfully in pure Python would be a separate
networking stack and would create interoperability and security risk. The control-plane and wire
format are Python; the interoperable encrypted transport stays upstream.
