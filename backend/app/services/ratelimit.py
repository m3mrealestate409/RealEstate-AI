"""
Abuse protection for the PUBLIC chat widget (Constitution: low op cost + safety).

Employees are authenticated and already have per-user/per-org quotas. The widget
is anonymous and public, so it needs its own guards. Three layers, all Redis-
backed and fail-OPEN (an infra hiccup must never block real visitors):

  1. Per-session + per-IP fixed-window rate limit  → stops floods/scripts.
  2. Per-org daily cap on expensive (LLM) queries   → hard cost ceiling.
  3. Widget traffic uses its OWN budget (this module), NOT the employee quota,
     so public abuse can never exhaust staff quotas.
"""
from __future__ import annotations

import logging
import time
from datetime import date

from app.config import settings

logger = logging.getLogger(__name__)

# Defaults — tune here (could later move to per-org settings).
SESSION_LIMIT = 20     # messages per window, per chat session   (public widget)
SESSION_WINDOW = 300   # 5 minutes
IP_LIMIT = 40          # requests per window, per IP             (public widget)
IP_WINDOW = 300        # 5 minutes
# Trusted server integrations (CRM etc.) call from ONE server IP for the whole
# team, so the per-IP widget limit would strangle them. They get a generous
# per-org burst limit instead; the daily budget is their real cost guard.
API_LIMIT = 120        # requests per window, per org
API_WINDOW = 60        # 1 minute

# Daily expensive-query (LLM) budget per org, per channel. The public widget is
# capped tightly (anyone on the internet can hit it); trusted integrations get
# a much larger, separate budget so widget abuse can never starve the CRM.
DAILY_LLM_CAP = 300            # "widget"
DAILY_CAPS = {"widget": DAILY_LLM_CAP}
DAILY_CAP_DEFAULT = 2000       # crm / whatsapp / voice / api

_redis = None
_redis_next_try = 0.0  # monotonic time of the next reconnect attempt


def _get_redis():
    """Cached Redis client. Reconnects at most every 30s while it's down — so a
    slow Redis at boot (or a transient outage) never leaves the limits OFF
    forever, and recovery is automatic. Logs at ERROR so a monitored deployment
    can alarm on 'limits not enforced'. Fail-open (returns None) when unreachable."""
    global _redis, _redis_next_try
    if _redis is not None:
        return _redis
    now = time.monotonic()
    if now < _redis_next_try:
        return None
    _redis_next_try = now + 30
    try:
        import redis

        r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        r.ping()
        _redis = r
        return _redis
    except Exception as exc:  # noqa: BLE001
        logger.error("Rate limit: Redis UNAVAILABLE (%s) — abuse limits are NOT enforced until it recovers.", exc)
        return None


def _hit(r, key: str, limit: int, window: int) -> tuple[bool, int]:
    """Fixed-window counter: increment `key`, set its expiry on the first hit.
    Returns (within_limit, current_count)."""
    count = r.incr(key)
    if count == 1:
        r.expire(key, window)
    return count <= limit, count


def flood_check(org_id: int | None, session_id: str | None, ip: str | None) -> tuple[bool, int]:
    """Layer 1. Returns (allowed, retry_after_seconds). Fail-open on infra error."""
    r = _get_redis()
    if r is None:
        return True, 0
    try:
        if session_id:
            ok, _ = _hit(r, f"rl:sess:{session_id}", SESSION_LIMIT, SESSION_WINDOW)
            if not ok:
                return False, SESSION_WINDOW
        if ip:
            ok, _ = _hit(r, f"rl:ip:{org_id or 0}:{ip}", IP_LIMIT, IP_WINDOW)
            if not ok:
                return False, IP_WINDOW
    except Exception as exc:  # noqa: BLE001
        logger.warning("flood_check failed (%s); allowing.", exc)
        return True, 0
    return True, 0


def api_flood_check(org_id: int | None) -> tuple[bool, int]:
    """Burst limit for trusted server integrations (CRM etc.), scoped to the org
    rather than the IP — they all call from one server. Fail-open."""
    r = _get_redis()
    if r is None:
        return True, 0
    try:
        ok, _ = _hit(r, f"rl:api:{org_id or 0}", API_LIMIT, API_WINDOW)
        if not ok:
            return False, API_WINDOW
    except Exception as exc:  # noqa: BLE001
        logger.warning("api_flood_check failed (%s); allowing.", exc)
    return True, 0


def _cap_for(source: str) -> int:
    return DAILY_CAPS.get((source or "").lower(), DAILY_CAP_DEFAULT)


def _day_key(org_id: int, source: str) -> str:
    return f"rl:day:{org_id}:{(source or 'api').lower()}:{date.today().isoformat()}"


def daily_check(org_id: int | None, source: str = "widget") -> tuple[bool, int, int]:
    """Layer 2/3. Is this org+channel under its daily LLM budget? (no consume)
    Each channel has its OWN budget, so public widget abuse can never starve the
    CRM (and vice-versa). Returns (allowed, used, limit). Fail-open."""
    cap = _cap_for(source)
    r = _get_redis()
    if r is None or not org_id:
        return True, 0, cap
    try:
        used = int(r.get(_day_key(org_id, source)) or 0)
    except Exception:  # noqa: BLE001
        return True, 0, cap
    return used < cap, used, cap


def daily_consume(org_id: int | None, source: str = "widget") -> None:
    """Count one expensive query against this org+channel's own daily budget."""
    r = _get_redis()
    if r is None or not org_id:
        return
    try:
        key = _day_key(org_id, source)
        c = r.incr(key)
        if c == 1:
            r.expire(key, 60 * 60 * 24)
    except Exception as exc:  # noqa: BLE001
        logger.warning("daily_consume failed (%s).", exc)


def daily_event_allowed(org_id: int | None, event: str, cap: int) -> bool:
    """Per-org, per-day ceiling on a discrete abuse-prone event (new-chat
    notifications, public lead inserts) — bounds notification-flood / DB-growth
    abuse from a widget key that rotates session ids past the per-session limit.
    Increments and returns whether still under `cap`. Fail-open on infra error."""
    r = _get_redis()
    if r is None or not org_id:
        return True
    try:
        key = f"rl:evt:{org_id}:{event}:{date.today().isoformat()}"
        c = r.incr(key)
        if c == 1:
            r.expire(key, 60 * 60 * 24)
        return c <= cap
    except Exception:  # noqa: BLE001
        return True


# --- Login brute-force protection -----------------------------------------
# Counts FAILED logins per IP and per (IP, account) within a window.
#
# The lockout is keyed on the (IP, account) PAIR, not the account alone. A
# global per-account lock lets an attacker deny login to any known email by
# submitting a few bad passwords (account-lockout DoS). Pairing it with the IP
# means an attacker's failures only lock the ATTACKER's own source for that
# account — the real user on a different IP is never locked out. The per-IP cap
# still bounds how many failures any single source can make across all accounts.
# Fail-open on infra error so a Redis blip never locks everyone out.
LOGIN_WINDOW = 900          # 15 minutes
LOGIN_IP_MAX = 30           # failed logins per IP per window (across all accounts)
LOGIN_ACCOUNT_MAX = 8       # failed logins per (IP, account) per window
# Backstop that a spoofed X-Forwarded-For CANNOT rotate away: cap failures per
# ACCOUNT across ALL source IPs. Set high enough that a fumbling real user won't
# trip it, low enough to kill bulk credential-guessing; cleared on success. This
# is the IP-independent brake the (IP, account) pairing deliberately lacked, and
# the reason the XFF-spoofing bypass no longer yields unlimited guesses.
LOGIN_EMAIL_MAX = 50


def _acct_key(ip: str | None, email: str | None) -> str:
    return f"login:acct:{ip}:{(email or '').lower()}"


def _email_key(email: str | None) -> str:
    return f"login:email:{(email or '').lower()}"


def login_allowed(ip: str | None, email: str | None) -> bool:
    r = _get_redis()
    if r is None:
        return True
    try:
        ip_fails = int(r.get(f"login:ip:{ip}") or 0)
        pair_fails = int(r.get(_acct_key(ip, email)) or 0)
        email_fails = int(r.get(_email_key(email)) or 0)
        return (ip_fails < LOGIN_IP_MAX and pair_fails < LOGIN_ACCOUNT_MAX
                and email_fails < LOGIN_EMAIL_MAX)
    except Exception:  # noqa: BLE001
        return True


def login_register_failure(ip: str | None, email: str | None) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        for key in (f"login:ip:{ip}", _acct_key(ip, email), _email_key(email)):
            if r.incr(key) == 1:
                r.expire(key, LOGIN_WINDOW)
    except Exception:  # noqa: BLE001
        pass


def login_reset(ip: str | None, email: str | None) -> None:
    """Clear the (IP, account) failed-login counter after a successful login."""
    r = _get_redis()
    if r is None:
        return
    try:
        r.delete(_acct_key(ip, email), _email_key(email))
    except Exception:  # noqa: BLE001
        pass
