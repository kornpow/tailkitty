from __future__ import annotations

import base64

import cbor2
import pytest

from tailkitty import TokenError, parse_token


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
