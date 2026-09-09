# Building Tailkitty

Tailkitty builds one upstream Tailcat executable per supported target, records its provenance in a
manifest, and packages it in a platform-specific Python wheel. Source distributions remain
binary-free.

For the end-to-end publication checklist, see [RELEASING.md](RELEASING.md).

## Pinned environment

Mise is the source of truth for build tools:

| Tool | Pin |
| --- | --- |
| Python | 3.13.11 |
| Go | 1.27.1 |
| uv | 0.12.7 |
| Tailcat | `v0.6.0` |

Install and synchronize them with:

```console
mise install
uv sync --all-groups --locked
```

The builder sets `GOTOOLCHAIN=local` and rejects any Go version other than the exact pin. When
running a Python build module directly, enter mise's environment:

```console
mise exec -- uv run python -m scripts.build_wheels --target linux-x86_64
```

Using plain `uv run` can select an unrelated system Go compiler.

## Canonical tasks

```console
mise run test             # Ruff, formatting, strict mypy, pytest
mise run backend          # source-checkout backend under .tools/bin
mise run bundle           # host bundle under src/tailkitty/bin
mise run bundle-verify    # verify the host bundle and manifest
mise run wheel            # package the host bundle
mise run wheels           # build and verify all six platform wheels
mise run upstream-check   # compare the Tailcat pin with the latest stable release
```

Generated content under `.tools/bin/`, `src/tailkitty/bin/`, and `dist/` is ignored and must not be
edited or committed.

## Build pipeline

`scripts.build_binary` performs these steps:

1. Resolve the requested target.
2. Verify the exact Go compiler.
3. Download `github.com/tailscale/tailcat@<immutable-pin>` through the Go module system.
4. Copy the source into a temporary writable workspace.
5. Check and apply every lexically sorted patch under `patches/`.
6. Read upstream's release build tags from `build-tags.txt`.
7. Cross-compile `./cmd/tailcat` with the reproducibility and compatibility settings below.
8. Check the executable header and minimum plausible size.
9. Atomically place the executable and write `manifest.json`.

The build uses:

- `CGO_ENABLED=0`
- `GOTOOLCHAIN=local`
- `GOAMD64=v1`
- `GOARM64=v8.0`
- `-trimpath`
- `-buildvcs=false`
- stripped symbols
- an empty Go build ID
- upstream's official release omission tags

Module downloads have three bounded attempts with short exponential backoff for transient failures.
Build failures are not silently converted into old or partial bundles.

## Bundle manifest

Each generated bundle contains its executable and a schema-1 JSON manifest. The manifest records:

- Internal target name and wheel platform tag.
- Executable filename, size, and SHA-256.
- Tailcat module and immutable version.
- Applied patch filenames and SHA-256 values.
- Go compiler version.
- Reproducibility flags and release build tags.
- CGO policy.

Build-time verification rechecks those inputs. Runtime verification additionally requires the
manifest target to match the current interpreter platform, rejects path-containing filenames and
symlinks, and refuses size or digest mismatches.

## Wheel matrix

| Build target | Go target | Wheel tag | Executable |
| --- | --- | --- | --- |
| `macos-arm64` | `darwin/arm64` | `macosx_12_0_arm64` | Mach-O `tailcat` |
| `macos-x86_64` | `darwin/amd64` | `macosx_12_0_x86_64` | Mach-O `tailcat` |
| `linux-x86_64` | `linux/amd64` | `manylinux_2_17_x86_64` | ELF `tailcat` |
| `linux-aarch64` | `linux/arm64` | `manylinux_2_17_aarch64` | ELF `tailcat` |
| `windows-x86_64` | `windows/amd64` | `win_amd64` | PE `tailcat.exe` |
| `windows-arm64` | `windows/arm64` | `win_arm64` | PE `tailcat.exe` |

Build one target:

```console
mise exec -- uv run python -m scripts.build_wheels \
  --target windows-arm64 \
  --output dist/wheels
```

Build all targets:

```console
mise run wheels
```

Each target uses a separate temporary bundle directory. Environment variables tell the Hatch build
hook which bundle and exact tag to include. This prevents one architecture's executable from
leaking into another wheel.

## Wheel verification

`scripts.verify_wheel` opens the wheel as an archive and checks:

- The filename and `WHEEL` metadata carry the expected platform tag.
- The wheel is marked non-pure.
- Archive members are unique and cannot escape through absolute or `..` paths.
- Total uncompressed content is bounded.
- `py.typed`, the manifest, and the one expected executable are present.
- Manifest target, module, Tailcat pin, patch set, tags, size, and digest match build inputs.
- The executable begins with the expected Mach-O, ELF, or PE magic.
- Every non-`RECORD` member has the exact hash and size recorded in `RECORD`.
- `RECORD` names exactly the archive contents.

Cross-compiled executables cannot be run on the build host, so this structural verification is
paired with native CI builds and the host smoke test.

## Host smoke test

Build or select the current host wheel, then run:

```console
uv run python -m scripts.smoke_wheel dist/wheels/<host-wheel>.whl
```

The smoke test:

1. Creates a temporary isolated Python environment.
2. Installs only the selected wheel and its dependencies.
3. Runs `tailkitty doctor --json` and confirms the bundled backend is selected.
4. Starts an isolated local DERP/STUN relay through Tailcat's test mode.
5. Starts a peer and performs an actual encrypted ping.
6. Sends and receives a real application UDP datagram through the same isolated relay.
7. Applies five-second startup and client bounds, followed by bounded termination.

It does not depend on public relay availability and does not touch saved developer keys.

## Source distribution

Build a source archive after removing any generated host bundle:

```console
mise run bundle-clean
uv build --sdist --out-dir dist/release
```

The Hatch sdist configuration includes Python source, scripts, tests, patches, documentation, lock
and tool configuration, but excludes generated executables and manifests. A source installation can
use pure-Python address functionality immediately; networking requires a separately built or
configured backend.

## Reproducibility scope

Tailkitty pins the compiler, module version, build tags, target baseline, and flags that commonly
introduce host or VCS variation. The manifest makes every shipped executable auditable. Byte-for-byte
reproduction can still depend on the Go module proxy serving the same immutable module contents and
on the pinned tool downloads remaining available.

`SOURCE_DATE_EPOCH` is set during matrix wheel builds so archive metadata is stable. Reproducibility
does not mean one binary can be relabeled for another platform; each wheel is built and verified for
exactly one target.

## Upstream updates

```console
mise run upstream-check
```

This bounded GitHub API check fails when a newer stable Tailcat release exists. A daily scheduled
workflow runs the same command. Before updating the pin, review:

- Upstream changelog and security notes.
- `wire.go` for address fields and validation changes.
- CLI help and command ownership conflicts.
- `build-tags.txt` and Go version.
- New platform requirements.
- Whether local patches are now upstream or no longer apply.

Do not silently pin `main`. An immutable pseudo-version is acceptable only as an explicit,
documented compatibility decision.

## Common build failures

| Failure | Likely cause | Action |
| --- | --- | --- |
| Wrong Go version | Command ran outside mise | Prefix the direct command with `mise exec --` |
| Patch check fails | Upstream source changed | Review and update or remove the patch; never force it |
| One wheel expected, several found | Output contains another artifact with the same version/tag | Use a clean release directory |
| Wrong executable magic | Target or output staging mismatch | Inspect target selection; do not relabel the wheel |
| Host smoke timeout | Backend did not advertise or handshake in bounds | Inspect local relay logs and process cleanup |
| Public DERP timeout | External relay availability | Reproduce with the isolated smoke test |

More user-facing failures are covered in [docs/troubleshooting.md](docs/troubleshooting.md).
