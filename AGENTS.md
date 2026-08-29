# Repository instructions for coding agents

These instructions apply to the entire repository. They supplement the user request; they do not
override it.

## Start here

Read these files before making architectural, packaging, security, or release changes:

1. `README.md` for the product boundary and public behavior.
2. `SECURITY.md` for executable trust and authorization concerns.
3. `BUILDING.md` for the reproducible bundle and wheel pipeline.
4. `pyproject.toml` and `.mise.toml` for supported versions and canonical tasks.

Do not confuse Tailkitty with the separate `pytailcat` distribution on PyPI. This checkout is the
source of truth for Tailkitty; upstream Tailcat remains the data-plane source of truth.

## Architecture and non-negotiable boundaries

The project intentionally has two layers:

- The control plane is Python: token encoding/decoding, validation, DNS TXT lookup, DERP-map
  resolution/cache, typed clients, diagnostics, and process lifecycle.
- The network data plane is the pinned upstream Go Tailcat executable: magicsock, userspace
  WireGuard, DERP transport, and gVisor netstack.

Do not replace the data plane with a Python-only protocol that interoperates only with itself. Do
not silently fall back from a corrupt bundled executable to an unverified backend. Wire
compatibility and fail-closed bundle discovery are core requirements.

## Repository map

| Path | Responsibility |
| --- | --- |
| `src/tailkitty/token.py` | Tailcat CBOR/base64url wire format and DERP embedding |
| `src/tailkitty/destination.py` | Literal-token and DNS TXT destination resolution |
| `src/tailkitty/derp.py` | Validated, bounded, atomic DERP-map caching |
| `src/tailkitty/backend.py` | Backend precedence and command execution |
| `src/tailkitty/bundle.py` | Runtime manifest and executable integrity checks |
| `src/tailkitty/client.py` | Sync and asyncio client APIs |
| `src/tailkitty/process.py` | Managed server processes and low-level async execution |
| `src/tailkitty/cli.py` | Python-native commands and upstream pass-through |
| `src/tailkitty/constants.py` | Package, Go, module, and upstream Tailcat pins |
| `scripts/targets.py` | Supported build targets and wheel tags |
| `scripts/build_binary.py` | Reproducible cross-compilation and manifest creation |
| `scripts/build_wheels.py` | Isolated five-target wheel orchestration |
| `scripts/verify_wheel.py` | Wheel metadata, archive, binary, and RECORD verification |
| `hatch_build.py` | Platform-wheel build hook |
| `tests/` | Unit and subprocess behavior tests |

Public imports are curated in `src/tailkitty/__init__.py`. Adding a public API requires updating
that file, type annotations, tests, and README documentation.

## Environment and canonical commands

Use mise and uv; do not introduce a parallel virtualenv, dependency manager, or ad hoc Go version.

```console
mise install
uv sync --all-groups --locked
mise run test
```

`mise run test` is the required local quality gate. It runs Ruff linting, Ruff formatting checks,
strict mypy, and pytest. During iteration, run the narrowest relevant test first, then run the full
gate before declaring completion.

Packaging changes also require:

```console
mise run bundle
mise run bundle-verify
mise run wheels
uv run python -m scripts.smoke_wheel dist/wheels/<host-wheel>.whl
```

For Python-version compatibility changes, test the minimum version:

```console
uv run --isolated --python 3.11 --all-groups pytest
```

Public DERP relays are external and can be unavailable or rate-limited. Keep unit tests deterministic
and do not make the default test suite depend on a live relay. Report live integration timeouts
honestly rather than treating them as proof of a local regression or success.

## Version and build invariants

- `TAILKITTY_VERSION` must match `[project].version` in `pyproject.toml`.
- `GO_VERSION` must match `[tools].go` in `.mise.toml` exactly.
- `TAILCAT_VERSION` must remain an immutable upstream version or pseudo-version.
- Bundle builds must use the exact Go toolchain with `GOTOOLCHAIN=local`.
- Keep `CGO_ENABLED=0`, `-trimpath`, `-buildvcs=false`, the empty build ID, stripped symbols, and
  baseline CPU feature levels unless a documented compatibility decision changes them.
- Every platform wheel must be non-pure and tagged for exactly one supported target.
- Source distributions and pure-Python fallback wheels must contain no generated executable or
  bundle manifest.
- Do not invent a platform tag. Update `scripts/targets.py`, build validation, CI, tests, and docs as
  one change when adding a target.

## Backend and security invariants

Backend priority is:

1. `TAILKITTY_BACKEND`, which must be executable or fail immediately.
2. A verified, runtime-compatible bundled executable.
3. `.tools/bin/tailcat`, followed by the legacy `.tools/bin/tailcat-go` path.
4. `tailcat-go` on `PATH`.

Preserve these behaviors:

- A present but invalid bundle is an integrity error; it must not trigger fallback.
- Manifest filenames cannot contain paths, and bundled executables cannot be symlinks.
- Runtime checks cover schema, module, revision, platform, size, and SHA-256.
- `allow=None` preserves upstream's allow-all behavior; `allow=[]` must become `--allow=none`.
- Timeout and cancellation paths must terminate and reap child processes.
- Cache files remain bounded, private, atomically replaced, and safe to use stale after refresh
  failure.
- Never log saved private keys or embed real active connection addresses in fixtures or docs.

## CLI compatibility

The Python CLI owns only `parse`, `resolve`, `doctor`, `--version`, and top-level help. All other
argument sequences must pass unchanged to the upstream executable, including no arguments.

When changing command dispatch, test both the Python-native commands and an arbitrary upstream
argument sequence. Do not add a Python subcommand whose name silently shadows an upstream command
without an explicit compatibility decision.

## Code and test conventions

- Support Python 3.11 and newer.
- Keep complete annotations and strict-mypy compatibility.
- Prefer standard-library types and small typed dataclasses over untyped dictionaries at public
  boundaries.
- Keep synchronous and asyncio behavior aligned, especially timeout, cancellation, and cleanup.
- Validate external input early with domain-specific exceptions (`TokenError`, `DestinationError`,
  `DerpMapError`, `BundleError`, or `BackendNotFound`).
- Add regression tests for bug fixes. Avoid weakening a safety check merely to satisfy a fixture.
- Use temporary directories in tests; never depend on or overwrite a developer's saved Tailcat
  keys, cache, bundle, or configured backend.
- Keep Ruff's 100-character line length and run formatting rather than hand-aligning code.

## Generated files and release safety

Do not manually edit or commit generated files under:

- `src/tailkitty/bin/`
- `dist/`
- `.tools/bin/`
- cache, virtualenv, or `__pycache__` directories

Use the scripts and mise tasks that own those artifacts. Publish only the `tailkitty` distribution;
the `pytailcat` name belongs to another project. Before a release, verify project URLs and the `pypi`
GitHub environment, build all five wheels plus the source distribution, smoke-test the host wheel,
and retain checksums and provenance attestations.

## Definition of done

A change is complete when:

1. The implementation respects the Python/native boundary and security invariants.
2. Focused regression tests cover new behavior or the repaired failure.
3. Public behavior and types are documented where users will find them.
4. `mise run test` passes.
5. Packaging changes pass the full wheel matrix and host installation smoke test.
6. Remaining external limitations or unverified assumptions are stated explicitly.
