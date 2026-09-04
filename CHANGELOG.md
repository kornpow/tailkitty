# Changelog

## 0.2.0 - 2026-09-04

- Upgrade the bundled data plane from a pre-release Tailcat commit to Tailcat v0.6.0.
- Preserve and display separate discovery keys and WireGuard pre-shared keys in Python token
  parsing and resolution.
- Adopt upstream's smaller official release build tags and remove the now-upstreamed local relay
  patch.
- Gain upstream file transfer, forwarding, UDP, SSH-key authentication, connection reliability,
  and teardown fixes.

## 0.1.1 - 2026-08-29

- Re-license Tailkitty from BSD-3-Clause to MIT. Bundled upstream Tailcat remains BSD-3-Clause.
- Patch and smoke-test Tailcat's controlled relay so wheel CI proves a real peer handshake, not
  merely that the bundled executable starts.

## 0.1.0 - 2026-08-29

- Launch under the Tailkitty distribution, import, and primary CLI name.
- Implement Tailcat token parsing, validation, resolution, DNS destination lookup, and DERP caching
  in Python.
- Add typed synchronous and asyncio client/server process APIs.
- Bundle a pinned upstream data plane in verified wheels for five desktop/server targets.
- Add structured backend diagnostics, reproducible builds, artifact verification, isolated wheel
  smoke tests, CI, release provenance, and trusted-publishing automation.
