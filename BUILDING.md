# Building bundled wheels

The environment is fully pinned by mise: Python 3.13.11, Go 1.26.5, and uv 0.12.7.

```console
mise install
uv sync --all-groups --locked
mise run test
mise run wheels
```

`mise run wheels` downloads the exact Tailcat revision in `constants.py`, applies every patch in
`patches/`, and cross-compiles it for five targets. It stages each executable separately, builds a
correctly tagged non-pure wheel, and verifies its archive paths, executable format, bundle digest,
patch digest, and every wheel `RECORD` entry. Build inputs use
`CGO_ENABLED=0`, `-trimpath`, no VCS metadata, no Go build ID, baseline CPU levels, and the exact
mise-managed Go compiler. Dependency downloads receive bounded retries for transient CI failures.

Build one target with:

```console
uv run python -m scripts.build_wheels --target linux-x86_64 --output dist/wheels
```

Install-test the wheel matching the current host with the integrity and real peer-handshake smoke
test:

```console
uv run python -m scripts.smoke_wheel path/to/tailkitty-*.whl
```

The wheel matrix is:

| Build target | Wheel platform tag | Executable |
| --- | --- | --- |
| `macos-arm64` | `macosx_12_0_arm64` | Mach-O |
| `macos-x86_64` | `macosx_12_0_x86_64` | Mach-O |
| `linux-x86_64` | `manylinux_2_17_x86_64` | ELF |
| `linux-aarch64` | `manylinux_2_17_aarch64` | ELF |
| `windows-x86_64` | `win_amd64` | PE |

The release workflow rebuilds the matrix, creates a binary-free source distribution, generates
checksums, creates GitHub build-provenance attestations, and uses PyPI trusted publishing. Configure
the `pypi` GitHub environment before enabling it.
