"""Resolve Tailcat tokens directly or through DNS TXT records."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import dns.asyncresolver
import dns.exception
import dns.resolver

from .token import TokenError, parse_token


class DestinationError(ValueError):
    """A Tailcat destination could not be resolved."""


def resolve_destination(destination: str, *, timeout: float = 5.0) -> str:
    """Return a validated token from a token or ``tailcat=`` DNS TXT record."""
    value = destination.strip()
    if value.startswith("tc") and "." not in value:
        parse_token(value)
        return value
    if "." not in value:
        raise DestinationError(f"{destination!r} is neither a Tailcat token nor a DNS name")
    try:
        answers = dns.resolver.resolve(value, "TXT", lifetime=timeout)
    except (dns.exception.DNSException, OSError) as exc:
        raise DestinationError(
            f"could not resolve Tailcat TXT record for {value!r}: {exc}"
        ) from exc
    return _token_from_answers(value, answers)


async def resolve_destination_async(destination: str, *, timeout: float = 5.0) -> str:
    """Asyncio version of :func:`resolve_destination`."""
    value = destination.strip()
    if value.startswith("tc") and "." not in value:
        parse_token(value)
        return value
    if "." not in value:
        raise DestinationError(f"{destination!r} is neither a Tailcat token nor a DNS name")
    try:
        answers = await dns.asyncresolver.resolve(value, "TXT", lifetime=timeout)
    except (dns.exception.DNSException, OSError) as exc:
        raise DestinationError(
            f"could not resolve Tailcat TXT record for {value!r}: {exc}"
        ) from exc
    return _token_from_answers(value, answers)


def _token_from_answers(name: str, answers: Iterable[Any]) -> str:
    for answer in answers:
        try:
            text = b"".join(answer.strings).decode("utf-8", errors="strict").strip()
        except (AttributeError, TypeError, UnicodeDecodeError) as exc:
            raise DestinationError(f"malformed TXT record returned for {name!r}") from exc
        if text.startswith("tailcat="):
            token = text.removeprefix("tailcat=").strip()
            try:
                parse_token(token)
            except TokenError as exc:
                raise DestinationError(f"invalid Tailcat token in TXT record for {name!r}") from exc
            return token
    raise DestinationError(f"no tailcat= TXT record found for {name!r}")
