"""
SSRF guard for outbound webhooks (CRM lead push, new-chat notifications).

Those destinations are chosen by a tenant admin — an untrusted party. Without
this, an admin (or an anonymous widget visitor triggering a CRM push) can point
the server at internal addresses (169.254.169.254, 127.0.0.1, 10.0.0.0/8,
host.docker.internal, …) and use the server as a proxy into the private network.

`assert_public_url` is pure and always validates (unit-testable). `guard_outbound`
applies it only in production, so local development can still reach
host.docker.internal / localhost CRMs.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.config import settings

_ALLOWED_SCHEMES = {"http", "https"}


class BlockedURLError(ValueError):
    """Raised when a URL is not a public http(s) endpoint."""


def _addresses(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise BlockedURLError(f"cannot resolve host {host!r}: {exc}") from exc
    return [info[4][0] for info in infos]


def assert_public_url(url: str) -> None:
    """Raise BlockedURLError unless `url` is an http(s) URL whose host resolves
    ONLY to public, routable IP addresses."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise BlockedURLError("URL must start with http:// or https://")
    host = parsed.hostname
    if not host:
        raise BlockedURLError("URL has no host")

    default_port = 443 if parsed.scheme == "https" else 80
    for addr in _addresses(host, parsed.port or default_port):
        ip = ipaddress.ip_address(addr)
        # Every non-public category an attacker would pivot through.
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise BlockedURLError(f"URL resolves to a non-public address ({ip})")


def is_public_url(url: str) -> bool:
    try:
        assert_public_url(url)
        return True
    except BlockedURLError:
        return False


def guard_outbound(url: str) -> None:
    """Enforce the SSRF guard in production; a no-op in dev so localhost /
    host.docker.internal CRMs keep working for local testing. Raises
    BlockedURLError when blocked."""
    if settings.is_production:
        assert_public_url(url)
