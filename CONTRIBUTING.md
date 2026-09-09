# Contributing to Tailkitty

Thank you for improving Tailkitty. The project values upstream compatibility, explicit security
boundaries, deterministic tests, and documentation that can be followed without hidden context.

## Before starting

Read:

1. [README.md](README.md) for public behavior.
2. [SECURITY.md](SECURITY.md) for authorization and executable trust.
3. [docs/architecture.md](docs/architecture.md) for the Python/native boundary.
4. [BUILDING.md](BUILDING.md) for packaging changes.

Automated contributors must also follow [AGENTS.md](AGENTS.md).

## Development environment

Install [mise](https://mise.jdx.dev/) and clone the repository, then run:

```console
mise install
mise run setup
mise run test
```

Mise pins Python, Go, and uv. Do not create a second toolchain configuration or commit a local
virtual environment. `mise run setup` synchronizes the uv environment and builds the pinned Tailcat
development backend.

The normal edit loop is:

```console
uv run pytest tests/test_token.py
mise run test
```

Use the narrowest relevant test while iterating, then run the complete quality gate before handing
off a change. The gate includes Ruff linting, Ruff formatting checks, strict mypy, and pytest.

## Change boundaries

Tailkitty owns the Python control plane:

- Address parsing, validation, and resolution.
- DNS TXT destination lookup.
- DERP-map caching.
- Typed sync and asyncio wrappers.
- Process lifecycle and diagnostics.
- Verified distribution of the pinned backend.

Upstream Tailcat owns magicsock, WireGuard, STUN, DERP transport, and gVisor netstack. Do not add a
Python-only transport that only interoperates with itself. If a behavior belongs in Tailcat,
consider an upstream contribution and pin the released result here.

The Python CLI intentionally owns only `parse`, `resolve`, `doctor`, `--version`, and top-level
help. New Python-native subcommands can shadow future Tailcat commands; adding one requires an
explicit compatibility decision.

## Tests

Good tests are:

- Deterministic and independent of public DERP availability.
- Bounded by short, explicit timeouts when processes or networks are involved.
- Isolated from saved user keys, caches, package directories, and configured backends.
- Paired across sync and asyncio APIs when behavior should match.
- Written as regressions for the exact failure being repaired.

Public relays can be slow or unavailable. Default tests must not use them. The wheel smoke test uses
an isolated local DERP/STUN relay and a five-second handshake bound.

For Python compatibility changes, test the minimum supported runtime:

```console
uv run --isolated --python 3.11 --all-groups pytest
```

## Documentation

Update documentation with the same change when public behavior changes:

- README for discovery, installation, quickstarts, and the public boundary.
- `docs/python-api.md` for Python parameters, results, exceptions, and lifecycle.
- `docs/recipes.md` for task-oriented CLI examples.
- `docs/troubleshooting.md` for new failure modes.
- SECURITY for authorization, secrets, and trust changes.
- BUILDING and RELEASING for packaging changes.
- CHANGELOG for user-visible changes.
- AGENTS when repository invariants or canonical workflows change.

Examples must use placeholders, never live addresses or private keys. Keep commands copyable and
state which machine runs each side of a multi-machine example.

## Packaging changes

Changes to bundle building, wheel tags, targets, manifests, dependencies, or build hooks require:

```console
mise run test
mise run bundle
mise run bundle-verify
mise run wheels
uv run python -m scripts.smoke_wheel dist/wheels/<host-wheel>.whl
```

When running a build module directly, keep it inside mise so the exact Go pin is selected:

```console
mise exec -- uv run python -m scripts.build_wheels --target windows-arm64
```

Do not manually edit or commit generated content under `src/tailkitty/bin/`, `dist/`, `.tools/bin/`,
caches, or virtual environments.

## Pull-request checklist

- [ ] The change stays inside the Python/native ownership boundary.
- [ ] Public APIs have complete annotations and root-package exports where appropriate.
- [ ] Tests cover success, validation failure, timeout, and cleanup where relevant.
- [ ] Sync and asyncio behavior remain aligned.
- [ ] Documentation and changelog describe the public result.
- [ ] No active address, private key, credential, or verbose network log is committed.
- [ ] `mise run test` passes.
- [ ] Packaging verification passes when packaging changed.
- [ ] Remaining external limitations are stated explicitly.

## Reporting security issues

Do not open a public report containing secrets, live unrestricted addresses, private key files, or
raw verbose logs. Follow [SECURITY.md](SECURITY.md).
