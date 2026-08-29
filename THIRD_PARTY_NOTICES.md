# Third-party notices

Platform wheels contain an executable built from
[`github.com/tailscale/tailcat`](https://github.com/tailscale/tailcat) and its
Go module dependencies. Tailcat is distributed under the BSD 3-Clause License.

The exact Tailcat module version, Go version, reproducibility flags, executable
size, and SHA-256 digest are recorded in `tailkitty/bin/manifest.json` inside
each platform wheel. The complete dependency versions are determined by the
pinned Tailcat module's `go.mod` and `go.sum` files.

Tailcat and Tailscale are trademarks of Tailscale Inc. This project is not an
official Tailscale product.
