"""Tailkitty Python tooling for Tailcat."""

from .constants import TAILKITTY_VERSION

__version__ = TAILKITTY_VERSION

from .backend import BackendInfo, BackendNotFound, inspect_backend, run
from .bundle import BundleError, BundleManifest
from .client import AsyncClient, Client
from .derp import DerpMapCache, DerpMapError
from .destination import DestinationError, resolve_destination, resolve_destination_async
from .diagnostics import diagnostics
from .process import AsyncServerProcess, ServerProcess, ServerStartError, run_async, send
from .token import ConnInfo, DerpNode, DerpRegion, TokenError, parse_token, resolve_token
from .udp import MAX_UDP_PAYLOAD, AsyncUDPConnection, Datagram, UDPConnection, UDPError

__all__ = [
    "MAX_UDP_PAYLOAD",
    "AsyncClient",
    "AsyncServerProcess",
    "AsyncUDPConnection",
    "BackendInfo",
    "BackendNotFound",
    "BundleError",
    "BundleManifest",
    "Client",
    "ConnInfo",
    "Datagram",
    "DerpMapCache",
    "DerpMapError",
    "DerpNode",
    "DerpRegion",
    "DestinationError",
    "ServerProcess",
    "ServerStartError",
    "TokenError",
    "UDPConnection",
    "UDPError",
    "diagnostics",
    "inspect_backend",
    "parse_token",
    "resolve_destination",
    "resolve_destination_async",
    "resolve_token",
    "run",
    "run_async",
    "send",
]
