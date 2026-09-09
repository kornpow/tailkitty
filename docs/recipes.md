# Tailkitty recipes

These recipes target the Tailcat version pinned by the current Tailkitty release. Replace every
`tc...` placeholder with the complete, case-sensitive address printed by the server.

Before troubleshooting a network path, confirm both installations:

```console
tailkitty --version
tailkitty doctor
tailkitty version
```

## One-shot text or byte stream

Start the receiver first:

```console
tailkitty --key=new < /dev/null
# 🐈 Server listening with new address: tc...
```

Then send a finite stream from the other machine:

```console
printf 'hello\n' | tailkitty --key=new 'tc...'
```

The receiver accepts one connection, writes the incoming bytes to stdout, and exits. The address
dies with the ephemeral server process.

For a binary file, redirect rather than using a text command:

```console
# Receiver
tailkitty --key=new > received.bin < /dev/null

# Sender
tailkitty --key=new 'tc...' < original.bin
```

For resumable file operations, directory trees, progress, and safer receive-only permissions, use
the file-service recipes below.

## Protect a server with client keys

Encryption prevents observers from reading traffic. An allow-list controls who may connect.

On each client, create a persistent client identity:

```console
tailkitty genkey --client --key=client-default
# nodekey:...
```

Send only the printed public `nodekey:...` value to the server operator. Do not send the saved
private key file.

On the server, allow that client:

```console
tailkitty serve --allow='nodekey:...' 8080
```

Multiple public keys are comma-separated:

```console
tailkitty serve --allow='nodekey:first,nodekey:second' 8080
```

The magic client key name `client-default` is selected automatically for later client commands.
Use `--key=<name>` when maintaining more than one client identity.

An empty Python `allow=[]` becomes `--allow=none`. At the CLI, spell the equivalent policy
explicitly:

```console
tailkitty serve --allow=none 8080
```

## Forward a remote TCP service

If a service already listens on `localhost:8080` of the server:

```console
# Server
tailkitty serve --allow='nodekey:...' 8080
```

Expose it on `127.0.0.1:18080` of the client:

```console
# Client
tailkitty forward 'tc...' 18080:8080
```

Several mappings can share one tunnel process:

```console
tailkitty forward 'tc...' 18080:8080 15432:5432
```

A one-number mapping uses the same local and remote port. Local port `0` asks the operating system
for a free port and prints the selected listener address:

```console
tailkitty forward 'tc...' 0:8080
```

Forwarders bind to `127.0.0.1` by default. `--bind=0.0.0.0` exposes the local listener to other
machines and should be an explicit security decision.

## Make a write-only file drop box

On the receiver:

```console
tailkitty recv ~/inbox
# 🐈 Server listening with new address: tc...
```

On the sender:

```console
tailkitty cp report.pdf 'tc...':
```

The default drop box does not let a sender list files, read them, replace existing files, or choose
the final stored name. To accept directory trees, use `--accept-dirs`; doing so reveals more
directory metadata to the sender:

```console
tailkitty recv --accept-dirs ~/inbox
tailkitty cp -r photos 'tc...':
```

`tailkitty cp` invokes the system `scp`, so OpenSSH must be installed on the machine running that
command.

## Offer a directory

Serve the current directory read-only:

```console
tailkitty serve files
```

Serve another directory read-write:

```console
tailkitty serve --files=/srv/share:rw files
```

List or download from the client:

```console
tailkitty ls -l 'tc...'
tailkitty cp 'tc...':report.pdf .
```

Available file modes are:

| Suffix | Policy |
| --- | --- |
| `:ro` | Read-only; the default |
| `:rw` | Read and write |
| `:wo` | Flat write-only drop box |
| `:wo+` | Recursive write-only drop box |

The server confines file-service paths to the configured root. File transfers are not compressed;
compress large data before transfer when appropriate.

## Public-key-authenticated SSH

The SSH service can load local authorized-key files, literal OpenSSH public keys, or GitHub user
keys:

```console
tailkitty serve \
  --ssh-authorized-keys="$HOME/.ssh/authorized_keys,alice@github" \
  ssh
```

Connect from the client:

```console
tailkitty ssh 'tc...'
tailkitty ssh 'tc...' uname -a
```

The server fetches `alice@github` from `https://github.com/alice.keys` once during startup. Startup
fails if any source is unavailable or contains invalid keys. Authorized-key options such as
`command=` and `from=` are not supported by Tailcat v0.6.

`tailkitty serve ssh` without `--ssh-authorized-keys` fails deliberately. The separate
`no-auth-ssh` service gives a shell to anyone who possesses the address and should be used only
with an allow-list or another deliberate containment mechanism:

```console
tailkitty serve --allow='nodekey:...' no-auth-ssh
```

Never publish a `no-auth-ssh` address in DNS.

## Use a SOCKS5 proxy

Run one command with a temporary SOCKS proxy. Tailkitty sets `all_proxy` for the child process:

```console
tailkitty socks 'tc...' curl http://server.tailcat:8080/
```

Run the proxy by itself and print its listener address:

```console
tailkitty socks --listen=127.0.0.1:1080 'tc...'
```

`server.tailcat` means the server named by the address argument. Other hostnames require the server
to run as an exit node. Address strings can also appear directly as SOCKS hostnames for CLI tools,
but browsers generally lowercase hostnames and therefore break case-sensitive Tailcat addresses.

## Reach the server's network through an exit node

An exit node can reach arbitrary addresses visible from the server. This is a broad capability;
always protect it with client keys.

```console
# Server
tailkitty serve --allow='nodekey:...' exit-node

# Client: forward local port 13306 to a database visible from the server
tailkitty forward 'tc...' 13306:192.168.1.10:3306
```

The SOCKS proxy can also route ordinary destinations through an exit node:

```console
tailkitty socks 'tc...' curl https://example.com/
```

## Check relay and direct connectivity

One ping reports the path used:

```console
tailkitty ping 'tc...'
```

Wait up to 30 seconds for NAT traversal to establish a direct peer-to-peer path:

```console
tailkitty ping --until-direct --timeout=30s 'tc...'
```

A DERP path is still encrypted and functional; it is normally slower than a direct UDP path.

## Persistent server identity

An ephemeral address changes whenever the server restarts. Generate the magic persistent server
key named `default` when clients or DNS must keep using the same identity:

```console
tailkitty genkey --key=default --fixed-region
```

Subsequent server commands load `default` automatically. List and delete named keys with:

```console
tailkitty genkey --list
tailkitty genkey --delete --key=old-server
```

Treat the saved private JSON files as secrets. Do not copy them into a repository or support log.

## Protected DNS destination

DNS names are convenient but public. First create a persistent server identity and a client
allow-list:

```console
# Client: send the printed public key to the server operator
tailkitty genkey --client --key=client-default

# Server: choose a stable region and require that client
tailkitty genkey --key=default --fixed-region
```

Then start the protected service. A complete SSH server command is:

```console
tailkitty serve \
  --allow='nodekey:...' \
  --ssh-authorized-keys=alice@github \
  ssh
```

Publish the complete address as a TXT record:

```dns
server.example.com. 300 IN TXT "tailcat=tc..."
```

Clients can then use `server.example.com` anywhere an address is accepted. Never publish an address
whose server relies only on possession of that address for authorization.

## Use a private DERP map

Point one invocation at another DERP map:

```console
tailkitty --derpmap-url=https://derp.example/derpmap.json serve 8080
```

Or set the upstream environment variable:

```console
export TAILCAT_DERPMAP_URL=https://derp.example/derpmap.json
tailkitty serve 8080
```

The Python resolver accepts the same URL explicitly:

```python
from tailkitty import resolve_token

full_address = resolve_token(
    "tc...",
    derp_map_url="https://derp.example/derpmap.json",
)
```

Custom DERP infrastructure must be reachable by both peers and must serve a compatible map. Review
its trust and availability separately from Tailkitty's bundled-executable checks.

## Next steps

- [Python API](python-api.md)
- [Troubleshooting](troubleshooting.md)
- [Security policy](../SECURITY.md)
- [Upstream Tailcat documentation](https://github.com/tailscale/tailcat)
