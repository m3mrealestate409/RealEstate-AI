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


def _key(user_id: int, day: str) -> str:
    return f"quota:{user_id}:{day}"


def check_quota(db: Session, user: User, day: str) -> tuple[bool, int, int | None]:
    """Return (allowed, used_today, limit) WITHOUT consuming. limit None = unlimited."""
    limit = user_daily_limit(db, user)
    if limit is None or user is None:
        return True, 0, None
    r = _get_redis()
    if r is None:
        return True, 0, limit  # fail open
    used = int(r.get(_key(user.id, day)) or 0)
    return used < limit, used, limit


def consume_quota(user: User, day: str) -> None:
    """Increment the user's counter for an expensive query (24h expiry)."""
    r = _get_redis()
    if r is None or user is None:
        return
    key = _key(user.id, day)
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 60 * 60 * 24)
    pipe.execute()
