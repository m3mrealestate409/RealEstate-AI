"""
Security + regression tests for the production SECRET_KEY guard (Sprint 1, C1).

Threat: with the repo's default/derived signing key an attacker forges a
super-admin JWT (sub = any super-admin email) — no password needed. These tests
lock in that a production boot rejects weak/derived secrets and that an unset
APP_ENV fails closed (treated as production).
"""
import secrets

import pytest

from app.config import Settings, _is_weak_secret, get_settings


# --- the exact string that defeated the old exact-match denylist ---
def test_derived_placeholder_secret_is_weak():
    assert _is_weak_secret("dev-secret-change-me-please-0123456789abcdef")


def test_short_secret_is_weak():
    assert _is_weak_secret("x" * 31)


def test_low_variety_secret_is_weak():
    assert _is_weak_secret("a" * 40)  # 40 chars but 1 unique char


def test_strong_random_secret_is_accepted():
    assert not _is_weak_secret(secrets.token_urlsafe(48))


# --- fail-closed default: unset APP_ENV == production ---
def test_unset_app_env_defaults_to_production(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    s = Settings(_env_file=None)  # ignore any .env on disk
    assert s.is_production is True


def test_explicit_dev_env_is_not_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    s = Settings(_env_file=None)
    assert s.is_production is False


# --- the boot guard itself ---
def test_production_boot_rejects_weak_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "dev-secret-change-me-please-0123456789abcdef")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        get_settings()
    get_settings.cache_clear()


def test_production_boot_accepts_strong_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", secrets.token_urlsafe(48))
    get_settings.cache_clear()
    s = get_settings()
    assert s.is_production and not _is_weak_secret(s.secret_key)
    get_settings.cache_clear()


def test_dev_still_boots_with_weak_secret(monkeypatch):
    # Regression: local dev must keep working with the convenient default.
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "dev-secret-change-me")
    get_settings.cache_clear()
    s = get_settings()  # must NOT raise
    assert not s.is_production
    get_settings.cache_clear()
