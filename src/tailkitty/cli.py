"""Tailkitty command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .backend import BackendNotFound, exec_backend
from .bundle import BundleError
from .derp import DEFAULT_DERP_MAP_URL
from .destination import DestinationError, resolve_destination
from .diagnostics import diagnostics
from .token import TokenError, parse_token, resolve_token


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tailkitty",
        description="Tailkitty: Python tooling with an upstream-compatible Tailcat data plane",
        epilog=(
            "Streaming, port serving, ping, SOCKS, SSH, and key commands are passed "
            "unchanged to the bundled data-plane helper."
        ),
    )
    parser.add_argument("--version", action="version", version=f"tailkitty {__version__}")
    commands = parser.add_subparsers(dest="command")
    parse = commands.add_parser("parse", help="decode a Tailcat connection token in Python")
    parse.add_argument("token")
    resolve = commands.add_parser("resolve", help="embed DERP relay details in a token")
    resolve.add_argument("token")
    resolve.add_argument("--derpmap-url", default=DEFAULT_DERP_MAP_URL)
    doctor = commands.add_parser("doctor", help="show environment and backend diagnostics")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if arguments is None else arguments)
    # Keep the upstream CLI surface intact. Only Python-native commands are
    # parsed here; everything else (including no arguments) is passed through.
    if not args or args[0] not in {"parse", "resolve", "doctor", "--version", "-h", "--help"}:
        try:
            exec_backend(args)
        except BackendNotFound as exc:
            print(f"tailkitty: {exc}", file=sys.stderr)
            return 127

    parser = _parser()
    namespace = parser.parse_args(args)
    try:
        if namespace.command == "parse":
            info = parse_token(resolve_destination(namespace.token))
            print(json.dumps(info.to_display_dict(raw=True), indent=4))
            return 0
        if namespace.command == "resolve":
            token = resolve_destination(namespace.token)
            print(resolve_token(token, derp_map_url=namespace.derpmap_url))
            return 0
        if namespace.command == "doctor":
            report = diagnostics()
            if namespace.as_json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(f"tailkitty {report['tailkitty_version']}")
                print(f"Python {report['python_version']} ({report['machine']})")
                print(
                    f"data-plane backend: {report['backend']['path']} "
                    f"[{report['backend']['source']}]"
                )
                if bundle := report["backend"].get("bundle"):
                    print(f"Tailcat {bundle['tailcat_version']} ({bundle['target']}, verified)")
            return 0
    except (TokenError, DestinationError, BackendNotFound, BundleError) as exc:
        parser.error(str(exc))
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
