"""
SSRF guard for outbound webhooks (CRM lead push, new-chat notifications).

Those destinations are chosen by a tenant admin — an untrusted party. Without
this, an admin (or an anonymous widget visitor triggering a CRM push) can point
the server at internal addresses (169.254.169.254, 127.0.0.1, 10.0.0.0/8,
host.docker.internal, …) and use the server as a proxy into the private network.

`assert_public_url` is pure and always validates (unit-testable). `guard_outbound`
enforces it ALWAYS; the only opt-out is the explicit SSRF_ALLOW_PRIVATE flag, so
local dev can still reach host.docker.internal / localhost CRMs on purpose.
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
    """False for every category an attacker would pivot through. IPv6 forms that
    embed an IPv4 address (6to4 2002::/16, ::ffff: mapped) are unwrapped and the
    inner v4 re-checked, so a literal like [2002:7f00:1::] cannot smuggle an
    internal 127.0.0.1 past the pure category test."""
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = ip.sixtofour or ip.ipv4_mapped
        if embedded is not None:
            return _is_public(embedded)
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
    """Enforce the SSRF guard ALWAYS — a mis-set APP_ENV must never silently
    disable it. The only opt-out is the explicit SSRF_ALLOW_PRIVATE flag, for
    local dev against a localhost / host.docker.internal CRM. Raises
    BlockedURLError when blocked."""
    if not settings.ssrf_allow_private:
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
    if settings.ssrf_allow_private:
        return httpx.post(url, **kwargs)  # explicit dev opt-out only

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
