# 100-iteration improvement ledger

Each checkbox is a distinct implementation, hardening, verification, or documentation pass. Items
are marked only after their stated evidence exists.

## 001-010 — reproducible environment

- [x] 001. Update and pin uv to 0.12.7 with mise.
- [x] 002. Pin Python 3.13.11 with mise.
- [x] 003. Pin Go 1.26.5 with mise.
- [x] 004. Keep the virtual environment driven by uv.
- [x] 005. Lock all Python runtime dependencies.
- [x] 006. Lock all Python development dependencies.
- [x] 007. Add a one-command mise setup task.
- [x] 008. Add a locked CI dependency-sync step.
- [x] 009. Move package, Tailcat, and Go pins into central constants.
- [x] 010. Test that project metadata and runtime versions agree.

## 011-020 — Python-native control plane

- [x] 011. Decode Tailcat CBOR tokens in Python.
- [x] 012. Model connection data with typed dataclasses.
- [x] 013. Validate token prefixes and base64 payloads.
- [x] 014. Validate node-key length and structure.
- [x] 015. Validate DERP region fields.
- [x] 016. Re-encode resolved Tailcat tokens in Python.
- [x] 017. Resolve DERP maps without invoking Go.
- [x] 018. Cache DERP maps on disk with a bounded lifetime.
- [x] 019. Revalidate DERP caches with HTTP ETags.
- [x] 020. Fall back to stale DERP data during network failure.

## 021-030 — Python APIs and process safety

- [x] 021. Resolve DNS `tailcat=` TXT destinations synchronously.
- [x] 022. Resolve DNS destinations asynchronously.
- [x] 023. Add a typed synchronous client.
- [x] 024. Add an asyncio client.
- [x] 025. Add a managed synchronous server process.
- [x] 026. Add a managed asyncio server process.
- [x] 027. Capture server readiness without blocking stdout.
- [x] 028. Clean up forgotten child processes at interpreter shutdown.
- [x] 029. Preserve exit status and stderr for non-raising calls.
- [x] 030. Translate an empty allow-list to the secure `--allow=none` value.

## 031-040 — pinned binary construction

- [x] 031. Pin the exact upstream Tailcat pseudo-version.
- [x] 032. Fetch the command package rather than an ambiguous module root.
- [x] 033. Build inside an isolated temporary Go module.
- [x] 034. Disable CGO for portable cross-compilation.
- [x] 035. Strip source paths with `-trimpath`.
- [x] 036. Disable VCS stamping.
- [x] 037. Remove the Go build ID.
- [x] 038. Strip symbols and debug tables.
- [x] 039. Set baseline amd64 and arm64 CPU levels.
- [x] 040. Retry transient module-download failures with a bounded backoff.

## 041-050 — target matrix and build safety

- [x] 041. Model build targets with immutable typed records.
- [x] 042. Support macOS arm64.
- [x] 043. Support macOS x86-64.
- [x] 044. Support Linux x86-64.
- [x] 045. Support Linux arm64.
- [x] 046. Support Windows x86-64.
- [x] 047. Normalize common machine-architecture aliases.
- [x] 048. Detect and reject unsupported build hosts.
- [x] 049. Validate Mach-O, ELF, and PE executable headers.
- [x] 050. Replace completed binaries atomically and remove stale opposite-OS files.

## 051-060 — platform-wheel packaging

- [x] 051. Migrate to Hatchling for a programmable wheel hook.
- [x] 052. Mark binary wheels as non-pure.
- [x] 053. Emit exact Python/ABI/platform wheel tags.
- [x] 054. Use a correct macOS 12 deployment floor.
- [x] 055. Use conservative manylinux 2.17 Linux tags.
- [x] 056. Force-include only the selected staged executable.
- [x] 057. Force-include its matching integrity manifest.
- [x] 058. Reject a caller-supplied tag that disagrees with the bundle.
- [x] 059. Keep generated binaries out of source distributions.
- [x] 060. Retain a pure-Python wheel fallback when no bundle is staged.

## 061-070 — runtime integrity and discovery

- [x] 061. Define a versioned JSON bundle-manifest schema.
- [x] 062. Record target, platform tag, module, revision, compiler, size, and SHA-256.
- [x] 063. Reject unsupported manifest schemas.
- [x] 064. Reject module or upstream-version mismatches.
- [x] 065. Reject path traversal and symlinked executables.
- [x] 066. Reject invalid digests and implausible bundle sizes.
- [x] 067. Recompute size and SHA-256 before execution.
- [x] 068. Reject a valid bundle copied to an incompatible runtime platform.
- [x] 069. Restore a missing POSIX user-execute bit after integrity validation.
- [x] 070. Cache successful verification while preserving explicit cache invalidation for tests.

## 071-080 — diagnostics and artifact verification

- [x] 071. Give `TAILKITTY_BACKEND` explicit, fail-closed priority.
- [x] 072. Prefer verified wheel bundles over development and PATH helpers.
- [x] 073. Preserve a migration fallback for the former `tailcat-go` development filename.
- [x] 074. Expose backend path, source, version, and manifest metadata.
- [x] 075. Add human-readable `tailcat doctor` output.
- [x] 076. Add machine-readable `tailcat doctor --json` output.
- [x] 077. Reject unsafe or duplicate wheel archive paths.
- [x] 078. Verify WHEEL purity and compatibility metadata.
- [x] 079. Verify the embedded executable and manifest together.
- [x] 080. Verify every wheel `RECORD` digest, size, and member mapping.

## 081-090 — automation, metadata, and supply chain

- [x] 081. Add unit coverage for bundle corruption and backend precedence.
- [x] 082. Run Ruff, formatting, strict mypy, and pytest from one mise task.
- [x] 083. Add a five-target CI wheel matrix.
- [x] 084. Add isolated host-wheel installation smoke testing in CI.
- [x] 085. Add binary-free source-distribution CI.
- [x] 086. Add checksums and GitHub build-provenance attestations.
- [x] 087. Add OIDC trusted-publishing automation with least-privilege permissions.
- [x] 088. Pin third-party GitHub Actions to immutable commits.
- [x] 089. Add PEP 561 typing metadata, classifiers, URLs, and third-party notices.
- [x] 090. Document building, security, architecture boundaries, and the existing-project comparison.

## 091-100 — real artifact and integration validation

- [x] 091. Cross-compile and structurally verify all five real platform wheels locally.
- [x] 092. Install the host wheel into an isolated environment and discover its verified bundle.
- [x] 093. Rebuild identical host binaries and prove byte-for-byte reproducibility.
- [x] 094. Detect and close Go's silent automatic-toolchain substitution path.
- [x] 095. Build and inspect the no-bundle pure-Python wheel fallback.
- [x] 096. Build and inspect the binary-free source distribution.
- [x] 097. Run the full suite on the minimum supported Python 3.11.
- [x] 098. Repeat live encrypted transfer testing and capture the current external DERP timeout
  after earlier successful bundled transfers.
- [x] 099. Rebuild final artifacts and pass the complete lint, type, test, and integrity audit.
- [x] 100. Audit this ledger against the workspace and deliver the handoff.
