# Tailkitty security policy

Tailkitty is experimental networking software. Use defense in depth, keep addresses and private
keys out of public reports, and verify the selected backend with `tailkitty doctor`.

## Reporting a vulnerability

Do not open a public issue containing:

- A live Tailcat address.
- A saved private key file.
- PyPI, GitHub, SSH, or other credentials.
- Unredacted verbose network logs.
- Private IP, DNS, or infrastructure details you do not intend to disclose.

Until a private reporting address is configured, open a minimal GitHub issue asking the maintainer
for a private contact channel. Include no exploit details or secrets in that issue.

In a private report, provide the affected Tailkitty and Tailcat versions, platform, installation
method, impact, minimal reproduction, and whether the issue exists with an official upstream
Tailcat build.

## Security model

Tailkitty protects three different things with different mechanisms:

| Concern | Mechanism |
| --- | --- |
| Traffic confidentiality and peer transport | Upstream WireGuard-based Tailcat data plane |
| Who may reach a server | Tailcat address possession, PSK, and optional `--allow` client keys |
| Which native code executes | Pinned wheel bundle and runtime integrity manifest |

Encryption is not the same as application authorization. A tunnel can be confidential while the
service behind it still accepts every holder of the address.

## Addresses are capability material

Tailcat v0.6 addresses can contain:

- The server's WireGuard public key.
- A distinct discovery public key.
- A WireGuard pre-shared key.
- DERP region or relay routing details.

The address contains no server private key, but the default PSK makes possession of the complete
address part of connection authorization. Treat it like a bearer capability:

- Share it only with intended clients.
- Do not paste it into public issues, CI logs, screenshots, analytics, or chat rooms.
- Do not assume an ephemeral address remains safe after accidental disclosure; stop the server and
  generate a new one.
- Rotate a disclosed persistent server key/address rather than relying on obscurity.

Tailkitty preserves current security fields and unknown future fields while parsing and resolving
addresses. This prevents a Python transformation from silently weakening a newer address format.

## Client authorization

Without `--allow`, Tailcat accepts every client that can use the address. For controlled access:

```console
# On the client
tailkitty genkey --client --key=client-default
# prints nodekey:...

# On the server
tailkitty serve --allow='nodekey:...' 8080
```

The public client key may be shared with the server. Its saved private key must remain on the
client.

In Python:

- `allow=None` preserves upstream allow-all behavior.
- `allow=["nodekey:..."]` allows the named clients.
- `allow=[]` becomes `--allow=none` and denies every client.

Do not change `allow=[]` to `None` as a convenience when debugging; that changes the security
policy.

## Public DNS

A DNS TXT record is public, world-readable, cacheable, and routinely scanned. Publishing
`tailcat=tc...` gives the address to everyone. A DNS-named service must authenticate independently:

- Use tunnel-level `--allow` for known Tailcat client identities.
- For SSH, also use `--ssh-authorized-keys` when appropriate.
- Use application authentication behind forwarded HTTP, database, or administrative ports.

Never publish an unrestricted `no-auth-ssh` address. That grants a shell as the account running the
server to anyone who reads the record.

DNS provides naming, not secrecy or identity verification. DNSSEC can authenticate DNS data but
does not make the address private.

## SSH, files, and exit nodes

These services have broader consequences than a one-shot byte stream:

- `serve ssh` runs a shell as the operating-system user running Tailcat. Require valid SSH keys and
  consider a tunnel allow-list as a second layer.
- `serve no-auth-ssh` trusts address possession unless `--allow` is set. Avoid it for persistent or
  DNS-named services.
- `serve files` confines SFTP paths to its configured root, but `:rw` permits modification and
  `:wo+` permits directory creation. Choose the narrowest mode.
- `recv` is a write-only drop box, but incoming files are still untrusted input. Scan or sandbox
  downstream processing.
- `serve exit-node` lets an allowed client reach networks visible to the server. Protect it with
  client keys and network-level controls.
- `forward --bind=0.0.0.0` exposes a client-side listener to other hosts. The default localhost bind
  is safer.

Tailkitty does not add authentication to the application behind a served port.

## Bundle trust model

Platform wheels contain an executable built from the immutable Tailcat pin. The build manifest
records:

- Target and wheel platform.
- Module and Tailcat version.
- Go compiler and release build tags.
- Applied patch digests.
- Executable filename, size, and SHA-256.

The build hook refuses a missing, path-escaping, symlinked, oversized, size-mismatched, or
digest-mismatched bundle. Runtime discovery repeats schema, module, version, platform, filename,
size, and SHA-256 checks.

If a bundle is present but invalid, Tailkitty fails closed. It does not silently run a development
or PATH executable instead.

Package-manager and PyPI transport integrity remain part of the trust chain. The internal manifest
detects post-build changes and target mix-ups; it is not an independent signature from a separate
trust authority.

## Explicit external backend

`TAILKITTY_BACKEND` has highest priority and is deliberate code-execution authority:

```console
export TAILKITTY_BACKEND=/absolute/path/to/tailcat
```

Tailkitty verifies only that this path is an executable file. It cannot prove who built it, whether
it matches the pinned version, or whether it is malicious. Use an absolute path and establish its
provenance separately.

An invalid explicit path fails immediately; it does not fall through to the verified wheel bundle.

## DERP and network metadata

Tailcat traffic remains end-to-end encrypted through DERP, but relays and network observers can
learn connection metadata such as timing, volume, public endpoints, and selected relay region.
Tailkitty does not provide anonymity.

The Python DERP-map fetcher bounds responses, validates the top-level structure, uses private and
atomic cache files, revalidates with ETags, and can use the last valid cache after a refresh error.
A custom DERP map or relay is an additional infrastructure trust and availability decision.

Public relays are rate-limited external infrastructure with no Tailkitty uptime guarantee. A relay
failure is an availability event, not evidence that encryption was bypassed.

## Logs and diagnostics

`tailkitty doctor --json` is designed for support, but still review paths, platform details, and
digests before posting it. Upstream `--verbose` output may reveal:

- Active addresses.
- Public and private endpoints.
- Relay region and path decisions.
- Key identifiers and local topology.

Collect the shortest useful interval, redact carefully, and stop verbose logging after diagnosis.

## Key storage

Upstream Tailcat controls saved key locations and formats. Tailkitty does not copy or parse saved
private key files. Protect them with operating-system file permissions, backups appropriate for
their sensitivity, and separation from source repositories.

Deleting a saved key makes its persistent address unusable after the running server stops. A key
printed with `genkey --client` outputs only the public key, but the corresponding private JSON file
must remain secret.

## Release security

Release automation is designed for least-privilege GitHub permissions, isolated matrix builds,
artifact checksums, provenance attestations, and PyPI OIDC Trusted Publishing. Trusted Publishing
requires a matching publisher configured on PyPI; an `invalid-publisher` failure must be fixed in
the external project settings rather than bypassed by weakening workflow permissions.

A local project-token publication is an explicit fallback described in [RELEASING.md](RELEASING.md).
Tokens must never appear in commands, logs, or repository files.

## Out of scope and limitations

- Tailkitty does not audit or replace upstream Tailcat cryptography.
- Tailkitty cannot establish provenance for `TAILKITTY_BACKEND`.
- Tailkitty does not make public DNS secret.
- Tailkitty does not authenticate applications behind forwarded ports.
- Tailkitty does not guarantee public DERP availability or direct peer connectivity.
- Tailcat and Tailkitty are experimental and do not promise stable pre-1.0 APIs.

See [docs/architecture.md](docs/architecture.md) for component ownership and
[docs/troubleshooting.md](docs/troubleshooting.md) for safe diagnostic steps.
