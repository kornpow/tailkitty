"""Tailkitty Python tooling for Tailcat."""

from .constants import TAILKITTY_VERSION

__version__ = TAILKITTY_VERSION

from .backend import BackendInfo, inspect_backend, run
from .bundle import BundleError, BundleManifest
from .client import AsyncClient, Client
from .derp import DerpMapCache, DerpMapError
from .destination import DestinationError, resolve_destination, resolve_destination_async
from .diagnostics import diagnostics
from .process import AsyncServerProcess, ServerProcess, run_async, send
from .token import ConnInfo, DerpNode, DerpRegion, TokenError, parse_token, resolve_token

__all__ = [
    "AsyncClient",
    "AsyncServerProcess",
    "BackendInfo",
    "BundleError",
    "BundleManifest",
    "Client",
    "ConnInfo",
    "DerpMapCache",
    "DerpMapError",
    "DerpNode",
    "DerpRegion",
    "DestinationError",
    "ServerProcess",
    "TokenError",
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
