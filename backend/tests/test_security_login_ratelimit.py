"""
Security tests for login brute-force protection (Sprint 1, H1).

Threat: /v1/auth/login had no throttle — unlimited credential stuffing against
admin / super-admin accounts (weak seed defaults exist). These tests lock in the
per-account lockout, the per-IP cap, reset-on-success, and fail-open-on-outage.
"""
from app.services import ratelimit


class FakeRedis:
    """Minimal in-memory stand-in for the redis client used by ratelimit."""
    def __init__(self):
        self.store = {}

    def get(self, k):
        v = self.store.get(k)
        return None if v is None else str(v)

    def incr(self, k):
        self.store[k] = int(self.store.get(k, 0)) + 1
        return self.store[k]

    def expire(self, k, seconds):
        pass

    def delete(self, k):
        self.store.pop(k, None)


def _use_fake(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(ratelimit, "_get_redis", lambda: fake)
    return fake


def test_same_ip_same_account_still_locks(monkeypatch):
    # Brute force from ONE source against one account is still capped.
    _use_fake(monkeypatch)
    ip, email = "1.2.3.4", "victim@example.com"
    assert ratelimit.login_allowed(ip, email)
    for _ in range(ratelimit.LOGIN_ACCOUNT_MAX):
        ratelimit.login_register_failure(ip, email)
    assert not ratelimit.login_allowed(ip, email)  # locked for THIS ip+account


def test_attacker_cannot_lock_out_victim_from_another_ip(monkeypatch):
    # The DoS fix: an attacker hammering the victim's email from their own IP
    # must NOT lock the real user out on a different IP.
    _use_fake(monkeypatch)
    victim = "admin@example.com"
    for _ in range(ratelimit.LOGIN_ACCOUNT_MAX + 5):
        ratelimit.login_register_failure("10.0.0.1", victim)  # attacker's IP
    assert not ratelimit.login_allowed("10.0.0.1", victim)    # attacker's own IP blocked
    assert ratelimit.login_allowed("10.0.0.2", victim)        # VICTIM's IP still allowed


def test_success_reset_unlocks_that_pair(monkeypatch):
    _use_fake(monkeypatch)
    ip, email = "1.2.3.4", "victim@example.com"
    for _ in range(ratelimit.LOGIN_ACCOUNT_MAX):
        ratelimit.login_register_failure(ip, email)
    assert not ratelimit.login_allowed(ip, email)
    ratelimit.login_reset(ip, email)
    assert ratelimit.login_allowed(ip, email)  # unlocked after a real success


def test_ip_cap_trips_even_across_rotated_accounts(monkeypatch):
    _use_fake(monkeypatch)
    # Attacker sprays one password across many accounts from one IP.
    for i in range(ratelimit.LOGIN_IP_MAX):
        ratelimit.login_register_failure("9.9.9.9", f"user{i}@example.com")
    assert not ratelimit.login_allowed("9.9.9.9", "brand-new@example.com")


def test_email_is_case_insensitive(monkeypatch):
    _use_fake(monkeypatch)
    for _ in range(ratelimit.LOGIN_ACCOUNT_MAX):
        ratelimit.login_register_failure("1.1.1.1", "Victim@Example.com")
    assert not ratelimit.login_allowed("1.1.1.1", "victim@example.com")


def test_fail_open_when_redis_down(monkeypatch):
    monkeypatch.setattr(ratelimit, "_get_redis", lambda: None)
    assert ratelimit.login_allowed("ip", "e@x.com") is True
    ratelimit.login_register_failure("ip", "e@x.com")  # no raise
    ratelimit.login_reset("ip", "e@x.com")  # no raise
