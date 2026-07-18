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

import httpx

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


def _is_public(ip: ipaddress._BaseAddress) -> bool:
    """False for every category an attacker would pivot through."""
    return not (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


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
        if not _is_public(ipaddress.ip_address(addr)):
            raise BlockedURLError(f"URL resolves to a non-public address ({addr})")


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


def _validated_ip(host: str, port: int) -> str:
    """Resolve `host` ONCE, require every answer to be public, return one IP."""
    addrs = _addresses(host, port)
    for addr in addrs:
        if not _is_public(ipaddress.ip_address(addr)):
            raise BlockedURLError(f"URL resolves to a non-public address ({addr})")
    return addrs[0]


def safe_post(url: str, **kwargs) -> httpx.Response:
    """SSRF- and DNS-rebind-safe POST.

    The plain flow (validate the URL, then httpx.post the URL) has a TOCTOU hole:
    httpx re-resolves the hostname at connect time, so an attacker with a
    low-TTL record can answer 'public' to our check and 'private' to httpx.

    Here we resolve the host EXACTLY ONCE, validate every answer, then connect to
    the validated IP literal — httpx does no second DNS lookup against an IP, so
    the rebind answer can never reach the socket. The original hostname rides in
    the Host header (vhost routing) and as the TLS SNI / cert-verification name.

    In dev this is a plain post so localhost / host.docker.internal CRMs work.
    """
    if not settings.is_production:
        return httpx.post(url, **kwargs)

    parsed = urlparse((url or "").strip())
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise BlockedURLError("URL must start with http:// or https://")
    host = parsed.hostname
    if not host:
        raise BlockedURLError("URL has no host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    ip = _validated_ip(host, port)
    netloc_ip = f"[{ip}]" if ":" in ip else ip  # bracket IPv6 literals
    pinned = parsed._replace(netloc=f"{netloc_ip}:{port}").geturl()

    headers = dict(kwargs.pop("headers", None) or {})
    headers.setdefault("Host", host if port in (80, 443) else f"{host}:{port}")
    extensions = dict(kwargs.pop("extensions", None) or {})
    extensions.setdefault("sni_hostname", host)  # TLS SNI + cert verify vs the name
    return httpx.post(pinned, headers=headers, extensions=extensions, **kwargs)
