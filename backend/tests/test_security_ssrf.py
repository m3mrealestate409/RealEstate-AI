"""
Security tests for the outbound-webhook SSRF guard (Sprint 1, C2).

Threat: a tenant admin (or an anonymous widget visitor triggering a CRM push)
points a webhook at an internal address and uses the server as a proxy into the
private network / cloud metadata. `assert_public_url` must reject every internal
category; public hosts must still pass.
"""
import pytest

from app.services import httpguard
from app.services.httpguard import BlockedURLError, assert_public_url, is_public_url


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/x",           # loopback
    "http://localhost:6379",             # loopback by name
    "http://169.254.169.254/latest/",    # cloud metadata (link-local)
    "http://10.0.0.5/internal",          # private
    "http://192.168.0.104:6380",         # private (the exposed Redis)
    "http://172.16.5.5/",                # private
    "http://[::1]:80/",                  # loopback v6
    "http://0.0.0.0/",                   # unspecified
])
def test_internal_targets_are_blocked(url):
    assert not is_public_url(url)
    with pytest.raises(BlockedURLError):
        assert_public_url(url)


@pytest.mark.parametrize("url", [
    "ftp://example.com/x",
    "file:///etc/passwd",
    "gopher://127.0.0.1/",
    "not-a-url",
])
def test_non_http_schemes_are_blocked(url):
    assert not is_public_url(url)


@pytest.mark.parametrize("url", [
    "https://example.com/webhook",
    "https://hooks.slack.com/services/T/B/x",
])
def test_public_hosts_are_allowed(url):
    assert is_public_url(url)


def test_guard_outbound_blocks_internal_in_production(monkeypatch):
    monkeypatch.setattr(httpguard.settings, "app_env", "production")
    assert httpguard.settings.is_production
    with pytest.raises(BlockedURLError):
        httpguard.guard_outbound("http://169.254.169.254/latest/meta-data/")


def test_guard_outbound_is_noop_in_dev(monkeypatch):
    # Regression: local dev must still reach host.docker.internal / localhost CRMs.
    monkeypatch.setattr(httpguard.settings, "app_env", "development")
    assert not httpguard.settings.is_production
    httpguard.guard_outbound("http://127.0.0.1:55321/functions/v1/website-form")  # no raise
