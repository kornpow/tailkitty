# Releasing Tailkitty

This checklist keeps the repository, Git tag, GitHub release, PyPI files, and embedded version pins
consistent. PyPI artifacts are immutable: if an upload is wrong, release a new version rather than
trying to replace it.

## Preconditions

- `main` is clean and synchronized with `origin/main`.
- The latest CI run is green.
- The intended Tailcat version is an immutable stable tag or pseudo-version.
- `.mise.toml` contains the exact required Go version.
- The PyPI `tailkitty` project and GitHub `pypi` environment are configured for Trusted Publishing,
  or a project-scoped local PyPI token is available for the documented fallback.
- The release directory is new or contains no artifacts from another version.

Never upload the separate `pytailcat` distribution name.

## 1. Choose and record the version

Update all release metadata in one commit:

- `[project].version` in `pyproject.toml`.
- `TAILKITTY_VERSION` in `src/tailkitty/constants.py`.
- The top `Unreleased` heading in `CHANGELOG.md`, including the release date.
- Any intentionally versioned examples.
- `uv.lock` by running `uv lock`.

The project test enforces agreement between the Python constant and package metadata.

## 2. Verify source and upstream status

```console
mise install
uv sync --all-groups --locked
mise run upstream-check
mise run test
uv run --isolated --python 3.11 --all-groups pytest
```

An upstream drift failure is a review prompt, not permission to pin a moving branch automatically.
Read the new Tailcat changelog, wire types, CLI changes, build tags, Go version, and security notes.

## 3. Build into a clean release directory

Use a dedicated directory so the upload command cannot include an older release accidentally:

```console
mise exec -- uv run python -m scripts.build_wheels --output dist/release
uv build --sdist --out-dir dist/release
uvx --from twine twine check dist/release/*
```

Expected contents are six wheels and one source distribution:

```text
tailkitty-X.Y.Z-py3-none-macosx_12_0_arm64.whl
tailkitty-X.Y.Z-py3-none-macosx_12_0_x86_64.whl
tailkitty-X.Y.Z-py3-none-manylinux_2_17_aarch64.whl
tailkitty-X.Y.Z-py3-none-manylinux_2_17_x86_64.whl
tailkitty-X.Y.Z-py3-none-win_amd64.whl
tailkitty-X.Y.Z-py3-none-win_arm64.whl
tailkitty-X.Y.Z.tar.gz
```

The source distribution must contain no generated executable or manifest.

## 4. Smoke-test the host wheel

Select the wheel for the build host and run:

```console
uv run python -m scripts.smoke_wheel dist/release/<host-wheel>.whl
```

This creates an isolated environment, verifies bundle discovery, and completes a real encrypted
peer handshake through a controlled local DERP/STUN relay. It has bounded startup and ping timeouts.

## 5. Commit and tag

```console
git add <release-metadata-files>
git commit -m "Release Tailkitty X.Y.Z"
git push origin main
git tag -a vX.Y.Z -m "Tailkitty vX.Y.Z"
git push origin vX.Y.Z
```

Do not move a tag after publishing. Confirm the tag resolves to the release commit before upload.

## 6. Publish

### Preferred: GitHub Trusted Publishing

The release workflow rebuilds the matrix, generates checksums, produces build-provenance
attestations, and requests a PyPI OIDC token from the `pypi` environment.

PyPI must have a publisher with these exact claims:

| Field | Value |
| --- | --- |
| Owner | `kornpow` |
| Repository | `tailkitty` |
| Workflow | `release.yml` |
| Environment | `pypi` |

An `invalid-publisher` error means those external PyPI settings do not match; rebuilding artifacts
will not fix it.

### Fallback: local project token

Use only when Trusted Publishing is unavailable and the release directory has already passed every
check above:

```console
uvx --from twine twine upload --non-interactive dist/release/*
```

Twine reads the configured project-scoped credential without printing it. Do not place tokens on a
command line, in shell history, or in repository files.

If the automated release is still running, do not race it with a local upload. Cancel or disable
the redundant publisher first so one path owns publication.

## 7. Verify the GitHub release

After Trusted Publishing succeeds, the workflow creates the GitHub Release and attaches the same
seven artifacts plus `SHA256SUMS`. It verifies that the tag already exists before creating the
release. Confirm those eight assets are present.

For a controlled local fallback when automation was not used:

```console
gh release create vX.Y.Z \
  --title "Tailkitty vX.Y.Z" \
  --generate-notes \
  dist/release/* \
  checksums/SHA256SUMS
```

## 8. Verify from the public index

Wait for PyPI's index to expose the release, then install without using local caches:

```console
uv venv --python 3.11 /tmp/tailkitty-release-check
uv pip install \
  --python /tmp/tailkitty-release-check/bin/python \
  --no-cache \
  tailkitty==X.Y.Z
/tmp/tailkitty-release-check/bin/tailkitty doctor --json
```

On Windows, the environment command lives under `Scripts` rather than `bin`.

Verify that PyPI lists exactly seven filenames and that the GitHub release points to the intended
tag. Check the README rendering on PyPI as part of the release, not only on GitHub.

## Failure handling

- Build or test failure: fix it before tagging.
- Trusted Publishing claim failure: correct PyPI publisher configuration; do not weaken workflow
  permissions.
- Partial PyPI upload: never overwrite existing files; verify what exists and publish only missing,
  unique filenames if their local build set is exactly the verified release set.
- Bad published artifact or metadata: yank if appropriate and issue a new patch release.
- Public relay timeout: distinguish external availability from the bounded local handshake test.
- GitHub release failure after successful PyPI upload: create the release from the same immutable
  tag and already-verified artifacts.

## Post-release

- Add a new `Unreleased` section to the changelog when development resumes.
- Confirm `main` CI remains green.
- Confirm `mise run upstream-check` still describes the pin accurately.
- Keep generated release files out of Git.
