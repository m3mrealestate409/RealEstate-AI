"""
Per-employee daily query quota (Constitution: low operating cost + fair usage).

Only EXPENSIVE queries (those that hit the LLM or RAG — i.e. cost money) count.
Cheap SQL lookups (price, inventory…) are always free and never limited.

Each employee's daily cap comes from their tier (basic/advanced), whose limits
are configured per organization. Super-admins are unlimited. Counters live in
Redis with a 24h TTL; if Redis is down we fail OPEN (never block on infra error).
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Organization, User

logger = logging.getLogger(__name__)

_redis = None
_redis_tried = False


def _get_redis():
    global _redis, _redis_tried
    if not _redis_tried:
        _redis_tried = True
        try:
            import redis

            _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            _redis.ping()
        except Exception as exc:
            logger.warning("Quota: Redis unavailable (%s); quotas not enforced.", exc)
            _redis = None
    return _redis


def user_daily_limit(db: Session, user: User) -> int | None:
    """The user's daily expensive-query cap. None = unlimited (super-admin / no org)."""
    if user is None or user.is_super_admin or not user.organization_id:
        return None
    org = db.get(Organization, user.organization_id)
    if not org:
        return None
    return org.advanced_daily_limit if user.tier == "advanced" else org.basic_daily_limit


def org_daily_limit(db: Session, org_id: int | None) -> int | None:
    """The whole company's daily expensive-query cap. None = unlimited, 0 = AI off.

    Comes from the plan AND whether the org has paid — an unpaid org resolves to
    0, which is what actually stops our LLM spend. See services/billing.py.
    """
    if not org_id:
        return None
    org = db.get(Organization, org_id)
    if not org:
        return None
    from app.services import billing  # local import: billing imports models too

    return billing.entitlements(db, org).daily_llm_quota


def _key(user_id: int, day: str) -> str:
    return f"quota:{user_id}:{day}"


def _org_key(org_id: int, day: str) -> str:
    return f"quota:org:{org_id}:{day}"


def _used(r, key: str) -> int:
    return int(r.get(key) or 0)


def check_quota(db: Session, user: User, day: str) -> tuple[bool, int, int | None]:
    """Return (allowed, used_today, limit) WITHOUT consuming. limit None = unlimited."""
    limit = user_daily_limit(db, user)
    if limit is None or user is None:
        return True, 0, None
    r = _get_redis()
    if r is None:
        return True, 0, limit  # fail open
    used = _used(r, _key(user.id, day))
    return used < limit, used, limit


def check_org_quota(db: Session, org_id: int | None, day: str) -> tuple[bool, int, int | None]:
    """Company-wide quota check (all employees combined)."""
    limit = org_daily_limit(db, org_id)
    if limit is None:
        return True, 0, None
    # A zero limit means billing switched AI off — that is a decision, not a
    # counter, so it must hold even when Redis is down. Fail-open applies to
    # infra hiccups, never to "this org has not paid".
    if limit <= 0:
        return False, 0, 0
    r = _get_redis()
    if r is None:
        return True, 0, limit
    used = _used(r, _org_key(org_id, day))
    return used < limit, used, limit


def _incr(r, key: str) -> None:
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 60 * 60 * 24)
    pipe.execute()


def used_today(user_id: int, day: str) -> int:
    r = _get_redis()
    return _used(r, _key(user_id, day)) if r else 0


def org_used_today(org_id: int, day: str) -> int:
    r = _get_redis()
    return _used(r, _org_key(org_id, day)) if r else 0


def consume_quota(user: User, day: str, org_id: int | None = None) -> None:
    """Increment the user's (and company's) counter for an expensive query."""
    r = _get_redis()
    if r is None:
        return
    if user is not None:
        _incr(r, _key(user.id, day))
    if org_id:
        _incr(r, _org_key(org_id, day))
