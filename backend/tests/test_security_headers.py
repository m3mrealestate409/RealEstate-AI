"""
Security tests for the response-header middleware (Sprint 1, H2).

Threat: no anti-clickjacking / hardening headers → the admin app is framable and
responses are MIME-sniffable. These lock the headers in place.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_hardening_headers_present_on_every_response():
    r = client.get("/health")
    h = {k.lower(): v for k, v in r.headers.items()}
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in h["permissions-policy"]


def test_no_hsts_outside_production():
    # conftest sets APP_ENV=testing → not production → HSTS must be absent
    # (it is only safe to send over guaranteed TLS).
    r = client.get("/health")
    assert "strict-transport-security" not in {k.lower() for k in r.headers}
