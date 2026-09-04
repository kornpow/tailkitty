from __future__ import annotations

import json
from io import BytesIO

import pytest

from tailkitty.derp import DerpMapCache
from tailkitty.token import ConnInfo, DerpNode, DerpRegion, TokenError, parse_token, resolve_token

README_TOKEN = "tcomFwWCCcjS5nKNqAod034nWoJZW0LZqDhhC8U_dKdnDRYQ8uNGFpGQEu"


def test_parse_upstream_readme_token() -> None:
    parsed = parse_token(README_TOKEN)
    assert (
        parsed.server_public.hex()
        == "9c8d2e6728da80a1dd37e275a82595b42d9a838610bc53f74a7670d1610f2e34"
    )
    assert parsed.region_id == 302
    assert parsed.to_display_dict() == {
        "ServerPublic": "nodekey:9c8d2e6728da80a1dd37e275a82595b42d9a838610bc53f74a7670d1610f2e34",
        "RegionID": 302,
    }


def test_round_trip_embedded_region() -> None:
    original = ConnInfo(
        server_public=bytes(range(32)),
        server_disco_public=bytes(reversed(range(32))),
        preshared_key=b"p" * 32,
        regions=[
            DerpRegion(
                region_id=10,
                region_code="sea",
                region_name="Seattle",
                nodes=[
                    DerpNode(
                        name="10a",
                        region_id=10,
                        hostname="derp.example.com",
                        ipv4="192.0.2.1",
                        stun_port=3478,
                        derp_port=443,
                    )
                ],
            )
        ],
    )
    parsed = parse_token(original.to_token(), restore_implicit=True)
    assert parsed.server_public == original.server_public
    assert parsed.server_disco_public == original.server_disco_public
    assert parsed.preshared_key == original.preshared_key
    assert parsed.regions[0].nodes[0].hostname == "derp.example.com"
    assert parsed.regions[0].nodes[0].name == "derp.example.com"


def test_resolve_uses_region_and_limits_nodes(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    derp_map = {
        "Regions": {
            "302": {
                "RegionID": 302,
                "RegionCode": "sfo",
                "RegionName": "San Francisco",
                "Nodes": [
                    {"Name": f"302{index}", "RegionID": 302, "HostName": f"d{index}.example"}
                    for index in range(3)
                ],
            }
        }
    }

    class Response(BytesIO):
        def __init__(self, value):
            super().__init__(value)
            self.headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout: Response(json.dumps(derp_map).encode())
    )
    resolved = parse_token(
        resolve_token(README_TOKEN, cache=DerpMapCache(tmp_path)), restore_implicit=True
    )
    assert resolved.region_id == 0
    assert len(resolved.regions[0].nodes) == 2
    assert resolved.regions[0].nodes[0].hostname == "d0.example"


@pytest.mark.parametrize("value", ["nope", "tc!!!!", "tc"])
def test_bad_tokens(value: str) -> None:
    with pytest.raises(TokenError):
        parse_token(value)


def test_resolve_preserves_modern_security_fields(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    derp_map = {"Regions": {"1": {"RegionID": 1, "Nodes": [{"HostName": "derp.example.com"}]}}}

    class Response(BytesIO):
        def __init__(self, value):
            super().__init__(value)
            self.headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout: Response(json.dumps(derp_map).encode())
    )
    original = ConnInfo(
        server_public=b"n" * 32,
        server_disco_public=b"d" * 32,
        preshared_key=b"p" * 32,
        region_id=1,
    )
    resolved = parse_token(resolve_token(original.to_token(), cache=DerpMapCache(tmp_path)))
    assert resolved.server_disco_public == b"d" * 32
    assert resolved.preshared_key == b"p" * 32
