# Changelog

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
