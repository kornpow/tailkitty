# Security policy and bundle trust model

Do not report secrets or private Tailcat tokens in a public issue. Until a private reporting
address is configured, open a minimal issue requesting a private contact channel.

Platform wheels contain an executable built from the pinned upstream Tailcat revision. At build
time, the exact Go compiler is enforced and an integrity manifest records the target, wheel tag,
module, revision, size, and SHA-256. The build hook refuses a missing, path-escaping, size-mismatched,
or checksum-mismatched executable. At runtime, Tailkitty repeats manifest, platform, size, and digest
validation before selecting the bundle. `tailkitty doctor --json` exposes the verified provenance.

Tailcat v0.6.0 addresses include a WireGuard pre-shared key and a distinct discovery public key.
Tailkitty's Python parser and resolver preserve both fields. Treat a complete active address as
sensitive capability material even though it contains no server private key.

`TAILKITTY_BACKEND` deliberately overrides the bundled executable. Treat that setting as code
execution authority: Tailkitty checks that the path is executable, but cannot establish the origin
or integrity of a user-supplied backend.

Release automation uses least-privilege workflow permissions, artifact checksums, provenance
attestations, and OIDC trusted publishing. The upstream project is experimental, and public DERP
relays are an external availability dependency.
