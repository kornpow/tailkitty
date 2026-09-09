from __future__ import annotations

import base64

import cbor2
import pytest

from tailkitty import ConnInfo, TokenError, parse_token


def token(value) -> str:
    return "tc" + base64.urlsafe_b64encode(cbor2.dumps(value)).rstrip(b"=").decode()


@pytest.mark.parametrize(
    ("wire", "message"),
    [
        ({"p": b"short"}, "32 bytes"),
        ({"p": bytes(32), "r": {}}, "field 'r' must be an array"),
        ({"p": bytes(32), "i": True}, "field 'i' must be an integer"),
        ({"p": bytes(32), "k": "bad"}, "field 'k' must be a byte string"),
        ({"p": bytes(32), "k": b"short"}, "disco public key must be 32 bytes"),
        ({"p": bytes(32), "q": "bad"}, "field 'q' must be a byte string"),
        ({"p": bytes(32), "q": b"short"}, "pre-shared key must be 32 bytes"),
        ({"p": bytes(32), "r": ["bad"]}, "DERP region must be a CBOR map"),
        ({"p": bytes(32), "r": [{"N": {}}]}, "field 'N' must be an array"),
    ],
)
def test_rejects_malformed_nested_wire_values(wire, message: str) -> None:
    with pytest.raises(TokenError, match=message):
        parse_token(token(wire))


def test_rejects_unreasonably_large_token() -> None:
    with pytest.raises(TokenError, match="unreasonably large"):
        parse_token("tc" + "A" * 65_536)


def test_rejects_trailing_cbor_data() -> None:
    encoded = cbor2.dumps({"p": bytes(32)}) + b"trailing"
    value = "tc" + base64.urlsafe_b64encode(encoded).rstrip(b"=").decode()
    with pytest.raises(TokenError, match="trailing data"):
        parse_token(value)


@pytest.mark.parametrize(
    ("wire", "message"),
    [
        ({"p": bytes(32), "i": 2**63}, "signed 64-bit"),
        ({"p": bytes(32), "r": [{"i": "bad"}]}, "field 'i' must be an integer"),
        ({"p": bytes(32), "r": [{"c": 7}]}, "field 'c' must be a text string"),
        ({"p": bytes(32), "r": [{"N": [{"h": 7}]}]}, "field 'h' must be a text string"),
        ({"p": bytes(32), "r": [{"N": [{"s": True}]}]}, "field 's' must be an integer"),
        ({"p": bytes(32), "r": [{"N": [{"x": 1}]}]}, "field 'x' must be a boolean"),
    ],
)
def test_rejects_wire_values_upstream_cannot_decode(wire, message: str) -> None:
    with pytest.raises(TokenError, match=message):
        parse_token(token(wire))


def test_rejects_reserved_extension_keys() -> None:
    with pytest.raises(TokenError, match="reserved"):
        ConnInfo(server_public=bytes(32), extensions={"q": b"shadowed"})
