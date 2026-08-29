from __future__ import annotations

import pytest

from tailkitty.destination import DestinationError, resolve_destination

TOKEN = "tcomFwWCCcjS5nKNqAod034nWoJZW0LZqDhhC8U_dKdnDRYQ8uNGFpGQEu"


class Answer:
    def __init__(self, *parts: bytes) -> None:
        self.strings = parts


def test_token_passes_through() -> None:
    assert resolve_destination(TOKEN) == TOKEN


def test_dns_txt_record(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "dns.resolver.resolve",
        lambda name, kind, lifetime: [Answer(b"tail", b"cat=", TOKEN.encode())],
    )
    assert resolve_destination("host.example") == TOKEN


def test_dns_without_tailcat_record(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "dns.resolver.resolve", lambda name, kind, lifetime: [Answer(b"something=else")]
    )
    with pytest.raises(DestinationError, match="no tailcat="):
        resolve_destination("host.example")
