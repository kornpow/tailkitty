# Troubleshooting Tailkitty

Start with bounded, local checks. Public DERP relays are external infrastructure; a relay timeout
alone does not prove that Tailkitty or its wheel is broken.

## Collect the basic report

```console
tailkitty --version
tailkitty doctor
tailkitty doctor --json
tailkitty version
```

`doctor` identifies the executable Tailkitty selected. For a bundled wheel, it also reports the
platform target, upstream Tailcat version, Go compiler, size, digest, and verification status.

Before sharing JSON or verbose logs, remove active addresses, private key paths, public IPs, and any
other sensitive environment details.

## `tailkitty: command not found`

For a user-level CLI installation:

```console
uv tool install --force tailkitty
uv tool list
```

Make sure uv's tool bin directory is on `PATH`. `uv tool update-shell` can configure it for common
shells; restart the shell afterward.

For a project dependency, commands normally run through the project environment:

```console
uv run tailkitty doctor
```

## No data-plane backend is installed

Symptoms include `BackendNotFound` or a message telling you to run `mise run backend`.

- A wheel from PyPI normally contains a backend for supported platforms.
- A source distribution intentionally contains no executable.
- An editable source checkout needs `mise run setup` or `mise run backend`.
- An unsupported platform needs an external upstream executable selected explicitly.

From a checkout:

```console
mise install
mise run setup
uv run tailkitty doctor
```

To use a separately installed upstream binary:

```console
export TAILKITTY_BACKEND=/absolute/path/to/tailcat
tailkitty doctor
```

On PowerShell:

```powershell
$env:TAILKITTY_BACKEND = 'C:\absolute\path\tailcat.exe'
tailkitty doctor
```

Tailkitty deliberately does not search for `tailcat` on `PATH`, because Tailkitty installs its own
`tailcat` alias and doing so could recurse. It searches for the distinct `tailcat-go` name only.

## Bundle integrity failure

Tailkitty does not fall back when an installed bundle is present but invalid. This is intentional.
Common causes are a modified package directory, an interrupted manual copy, or an environment that
rewrites installed executables.

Reinstall into a clean environment:

```console
uv tool uninstall tailkitty
uv tool install --no-cache tailkitty
tailkitty doctor
```

For a project environment:

```console
uv sync --refresh-package tailkitty
uv run tailkitty doctor
```

Do not bypass the check by setting `TAILKITTY_BACKEND` to the same untrusted file. If the official
wheel repeatedly fails verification, retain the wheel filename and expected/actual digest but do
not publish the executable or active addresses until the cause is understood.

## No matching wheel

Check the runtime:

```console
python -c "import platform,sys; print(sys.version); print(sys.platform, platform.machine())"
```

Tailkitty requires Python 3.11+. Current wheels cover macOS ARM64/x86-64, glibc Linux ARM64/x86-64,
and Windows ARM64/x86-64. Alpine Linux uses musl rather than glibc and does not match the manylinux
wheels.

On an unsupported platform, install the source distribution for pure-Python address functionality
and point `TAILKITTY_BACKEND` at a compatible Tailcat executable for networking.

## Server startup times out

`ServerProcess.start()` waits 20 seconds by default for Tailcat to advertise a valid address. A
timeout can mean:

- The DERP map or selected relay is unreachable.
- DNS, proxy, or firewall policy blocks bootstrap traffic.
- A custom DERP map is invalid or unavailable.
- A requested SSH key source cannot be fetched.
- The backend accepts the command but cannot finish initialization.

Try the upstream command directly with verbose logging and a bounded outer timeout appropriate to
your shell:

```console
tailkitty --verbose serve 8080
```

Stop it with Ctrl-C after collecting the first startup messages. For Python, temporarily increase
the startup budget rather than removing it:

```python
address = server.start(timeout=45)
```

Verbose network logs can contain addresses, endpoints, and topology information. Review them before
sharing.

## Client cannot connect

Check these in order:

1. The complete address was copied without truncation or case changes.
2. The server process is still running; ephemeral addresses die when it exits.
3. The client's saved public node key appears in the server's `--allow` list.
4. The client is using the intended saved identity (`client-default` or `--key=<name>`).
5. The requested port is actually served.
6. Both peers can reach the selected DERP relay.

Validate the address without connecting:

```console
tailkitty parse 'tc...'
```

Then test the encrypted path:

```console
tailkitty ping --timeout=10s 'tc...'
```

If ping works but an application does not, verify the remote application is listening on
`localhost:<served-port>` and that protocol expectations match. Tailcat carries bytes; it does not
turn HTTP into HTTPS or add application authentication.

## Connection uses DERP instead of a direct path

DERP is a valid encrypted fallback. To wait for a direct UDP path:

```console
tailkitty ping --until-direct --timeout=30s 'tc...'
```

Failure to become direct usually points to NAT, firewall, captive-network, or UDP policy. The
connection can still work through DERP. Compare both peers from another network before assuming a
packaging defect.

## DNS destination fails

Inspect the TXT record with a DNS tool:

```console
dig +short TXT service.example.com
```

It must concatenate to exactly one value beginning with `tailcat=` followed by a complete address.
Common failures include publishing only part of a long TXT value, adding whitespace inside the
address, using a stale ephemeral address, or changing letter case.

DNS records are public. If the record resolves but the service is intentionally locked down, make
sure the client uses an allowed node key. Never solve an authorization failure by removing
`--allow` from a public DNS-named server.

## SSH fails

Server-side checks:

- `serve ssh` requires `--ssh-authorized-keys`.
- Every key file must exist and every `user@github` source must be reachable at startup.
- Authorized-key options such as `command=` and `from=` are unsupported in Tailcat v0.6.
- The system account running the server determines shell and filesystem access.

Client-side checks:

- `tailkitty ssh` uses the system `ssh` command.
- `tailkitty cp` uses the system `scp` command.
- The tunnel allow-list and SSH authorized-key list are independent layers; the client may need to
  satisfy both.

Use normal OpenSSH verbosity after the Tailkitty command when supported by the upstream invocation,
but review the output before sharing it.

## File copy fails

- Start `recv` or `serve files` before running `cp`.
- `recv` is flat by default; use `--accept-dirs` before sending a directory tree.
- Read-only roots reject uploads.
- Write-only roots reject listing and downloads by design.
- `cp` needs the system `scp`; `ls` speaks SFTP directly and does not.
- Transfers are not compressed.

Use `tailkitty ls -l 'tc...'` to distinguish tunnel failure from file permission policy when the
server permits listing.

## A build uses the wrong Go version

Directly invoking `uv run python -m scripts.build_wheels` can select a system Go ahead of mise's
pinned toolchain. Enter the mise environment or use its task:

```console
mise install
mise run wheels
```

For one target:

```console
mise exec -- uv run python -m scripts.build_wheels \
  --target linux-x86_64 \
  --output dist/wheels
```

The builder intentionally rejects every Go compiler version except the exact pin.

## Report a problem

Include:

- Tailkitty version and installation method.
- Operating system, architecture, and Python version.
- Sanitized `tailkitty doctor --json` output.
- The shortest command that reproduces the issue.
- Whether `tailkitty parse` and bounded `tailkitty ping` succeed.
- Whether the failure occurs with a local relay test, public DERP, or both.

Do not include private key files, live unrestricted addresses, raw verbose logs, or credentials.
Read the [security policy](../SECURITY.md) before reporting a suspected vulnerability.
