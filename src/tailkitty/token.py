"""Tailcat connection-token wire format.

The format mirrors github.com/tailscale/tailcat/wire.go: ``tc`` followed by
unpadded base64url CBOR.  Keeping this in Python makes token inspection and
resolution usable without the Go data-plane helper.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

import cbor2

from .derp import DEFAULT_DERP_MAP_URL, DerpMapCache, DerpMapError


class TokenError(ValueError):
    """Raised when a Tailcat token is malformed or incomplete."""


@dataclass(slots=True)
class DerpNode:
    name: str = ""
    region_id: int = 0
    hostname: str = ""
    cert_name: str = ""
    ipv4: str = ""
    ipv6: str = ""
    stun_port: int = 0
    derp_port: int = 0
    insecure_for_tests: bool = False

    @classmethod
    def from_wire(cls, value: dict[str, Any]) -> DerpNode:
        _require_mapping(value, "DERP node")
        return cls(
            name=value.get("n", ""),
            region_id=value.get("i", 0),
            hostname=value.get("h", ""),
            cert_name=value.get("t", ""),
            ipv4=value.get("4", ""),
            ipv6=value.get("6", ""),
            stun_port=value.get("s", 0),
            derp_port=value.get("d", 0),
            insecure_for_tests=value.get("x", False),
        )

    @classmethod
    def from_derp_map(cls, value: dict[str, Any]) -> DerpNode:
        return cls(
            name=value.get("Name", ""),
            region_id=value.get("RegionID", 0),
            hostname=value.get("HostName", ""),
            cert_name=value.get("CertName", ""),
            ipv4=value.get("IPv4", ""),
            ipv6=value.get("IPv6", ""),
            stun_port=value.get("STUNPort", 0),
            derp_port=value.get("DERPPort", 0),
            insecure_for_tests=value.get("InsecureForTests", False),
        )

    def to_wire(self) -> dict[str, Any]:
        values = {
            "n": self.name,
            "i": self.region_id,
            "h": self.hostname,
            "t": self.cert_name,
            "4": self.ipv4,
            "6": self.ipv6,
            "s": self.stun_port,
            "d": self.derp_port,
            "x": self.insecure_for_tests,
        }
        return {key: value for key, value in values.items() if value not in ("", 0, False)}


@dataclass(slots=True)
class DerpRegion:
    region_id: int = 0
    region_code: str = ""
    region_name: str = ""
    nodes: list[DerpNode] = field(default_factory=list)

    @classmethod
    def from_wire(cls, value: dict[str, Any]) -> DerpRegion:
        _require_mapping(value, "DERP region")
        nodes = value.get("N", [])
        if not isinstance(nodes, list):
            raise TokenError("DERP region field 'N' must be an array")
        return cls(
            region_id=value.get("i", 0),
            region_code=value.get("c", ""),
            region_name=value.get("m", ""),
            nodes=[DerpNode.from_wire(node) for node in nodes],
        )

    @classmethod
    def from_derp_map(cls, value: dict[str, Any]) -> DerpRegion:
        return cls(
            region_id=value.get("RegionID", 0),
            region_code=value.get("RegionCode", ""),
            region_name=value.get("RegionName", ""),
            nodes=[
                DerpNode.from_derp_map(node)
                for node in value.get("Nodes", [])
                if not node.get("STUNOnly", False)
            ],
        )

    def to_wire(self, *, compact: bool = True) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        for node in self.nodes:
            item = node.to_wire()
            if compact:
                item.pop("i", None)
                if item.get("h"):
                    item.pop("n", None)
            nodes.append(item)
        values: dict[str, Any] = {
            "i": 0 if compact else self.region_id,
            "c": "" if compact else self.region_code,
            "m": "" if compact else self.region_name,
            "N": nodes,
        }
        return {key: value for key, value in values.items() if value not in ("", 0, False, [])}


@dataclass(slots=True)
class ConnInfo:
    server_public: bytes
    server_disco_public: bytes | None = None
    preshared_key: bytes | None = None
    regions: list[DerpRegion] = field(default_factory=list)
    region_id: int = 0

    def __post_init__(self) -> None:
        if len(self.server_public) != 32:
            raise TokenError(f"server public key must be 32 bytes, got {len(self.server_public)}")
        for label, value in (
            ("server disco public key", self.server_disco_public),
            ("pre-shared key", self.preshared_key),
        ):
            if value is not None and len(value) != 32:
                raise TokenError(f"{label} must be 32 bytes, got {len(value)}")

    def to_token(self) -> str:
        wire: dict[str, Any] = {"p": self.server_public}
        if self.server_disco_public is not None:
            wire["k"] = self.server_disco_public
        if self.preshared_key is not None:
            wire["q"] = self.preshared_key
        if self.regions:
            wire["r"] = [region.to_wire(compact=True) for region in self.regions]
        if self.region_id:
            wire["i"] = self.region_id
        encoded = cbor2.dumps(wire)
        return "tc" + base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")

    def to_display_dict(self, *, raw: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {"ServerPublic": "nodekey:" + self.server_public.hex()}
        if self.server_disco_public is not None:
            result["ServerDiscoPublic"] = "discokey:" + self.server_disco_public.hex()
        if self.preshared_key is not None:
            result["PresharedKey"] = "psk:" + self.preshared_key.hex()
        if self.regions:
            result["Region"] = [_region_display(region, raw=raw) for region in self.regions]
        if self.region_id:
            result["RegionID"] = self.region_id
        return result


def _decode_base64url(value: str) -> bytes:
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise TokenError(f"invalid base64url token: {exc}") from exc


def parse_token(token: str, *, restore_implicit: bool = False) -> ConnInfo:
    """Decode a Tailcat token.

    By default this retains only fields physically present in the token, which
    matches ``tailcat parse``. Set ``restore_implicit`` for operational use.
    """
    if not token.startswith("tc"):
        raise TokenError('server address does not start with "tc"')
    if len(token) > 65_536:
        raise TokenError("token is unreasonably large")
    try:
        wire = cbor2.loads(_decode_base64url(token[2:]))
    except cbor2.CBORDecodeError as exc:
        raise TokenError(f"invalid CBOR: {exc}") from exc
    if not isinstance(wire, dict) or not isinstance(wire.get("p"), bytes):
        raise TokenError("token CBOR must contain byte-string field 'p'")
    regions = wire.get("r", [])
    region_id = wire.get("i", 0)
    server_disco_public = wire.get("k")
    preshared_key = wire.get("q")
    if not isinstance(regions, list):
        raise TokenError("token CBOR field 'r' must be an array")
    if not isinstance(region_id, int) or isinstance(region_id, bool):
        raise TokenError("token CBOR field 'i' must be an integer")
    for key, label, value in (
        ("k", "server disco public key", server_disco_public),
        ("q", "pre-shared key", preshared_key),
    ):
        if value is not None and not isinstance(value, bytes):
            raise TokenError(f"token CBOR field '{key}' must be a byte string")
        if value is not None and len(value) != 32:
            raise TokenError(f"{label} must be 32 bytes, got {len(value)}")
    info = ConnInfo(
        server_public=wire["p"],
        server_disco_public=server_disco_public,
        preshared_key=preshared_key,
        regions=[DerpRegion.from_wire(region) for region in regions],
        region_id=region_id,
    )
    if restore_implicit:
        for index, region in enumerate(info.regions, start=1):
            region.region_id = region.region_id or index
            region.region_code = region.region_code or str(region.region_id)
            for node in region.nodes:
                node.name = node.name or node.hostname
                node.region_id = node.region_id or region.region_id
    return info


def resolve_token(
    token: str,
    *,
    derp_map_url: str = DEFAULT_DERP_MAP_URL,
    timeout: float = 10.0,
    cache: DerpMapCache | None = None,
) -> str:
    """Embed relay information into a short Tailcat token."""
    info = parse_token(token, restore_implicit=True)
    if info.regions:
        return token
    if info.region_id <= 0:
        raise TokenError("token has neither an embedded region nor a region ID")
    try:
        derp_map = (cache or DerpMapCache()).fetch(derp_map_url, timeout=timeout)
    except DerpMapError as exc:
        raise TokenError(str(exc)) from exc
    raw_region = derp_map.get("Regions", {}).get(str(info.region_id))
    if raw_region is None:
        raise TokenError(f"DERP map has no region {info.region_id}")
    region = DerpRegion.from_derp_map(raw_region)
    region.nodes = region.nodes[:2]
    info.regions = [region]
    info.region_id = 0
    return info.to_token()


def _require_mapping(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise TokenError(f"{label} must be a CBOR map")


def _region_display(region: DerpRegion, *, raw: bool) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if region.region_id:
        result["RegionID"] = region.region_id
    if region.region_code:
        result["RegionCode"] = region.region_code
    if region.region_name:
        result["RegionName"] = region.region_name
    if region.nodes:
        result["Nodes"] = []
        for node in region.nodes:
            values = {
                "Name": node.name,
                "RegionID": node.region_id,
                "HostName": node.hostname,
                "CertName": node.cert_name,
                "IPv4": node.ipv4,
                "IPv6": node.ipv6,
                "STUNPort": node.stun_port,
                "DERPPort": node.derp_port,
                "InsecureForTests": node.insecure_for_tests,
            }
            result["Nodes"].append(
                {key: value for key, value in values.items() if value not in ("", 0, False)}
            )
    return result
