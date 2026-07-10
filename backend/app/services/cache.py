"""
Response cache for repeated queries — saves LLM/embedding cost and latency.

Scoped PER ORGANIZATION (tenants never share cached answers). Freshness is
handled two ways:
  1. A short TTL backstop.
  2. A per-org cache VERSION that is bumped whenever that org's data changes
     (price/document/project edits) — old cached answers are instantly orphaned.

If Redis is unavailable, caching silently no-ops.
"""
from __future__ import annotations

import hashlib
import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)

TTL_SECONDS = 600  # 10-minute backstop

_redis = None
_tried = False


def _get_redis():
    global _redis, _tried
    if not _tried:
        _tried = True
        try:
            import redis

            _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            _redis.ping()
        except Exception as exc:
            logger.warning("Cache: Redis unavailable (%s); caching disabled.", exc)
            _redis = None
    return _redis


def _version(r, org_id: int | None) -> str:
    return r.get(f"qcache_ver:{org_id}") or "0"


def _key(r, org_id: int | None, query: str) -> str:
    norm = " ".join(query.lower().split())
    h = hashlib.md5(norm.encode()).hexdigest()
    return f"qcache:{org_id}:{_version(r, org_id)}:{h}"


def get(org_id: int | None, query: str) -> dict | None:
    r = _get_redis()
    if r is None:
        return None
    raw = r.get(_key(r, org_id, query))
    return json.loads(raw) if raw else None


def set(org_id: int | None, query: str, envelope: dict) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(_key(r, org_id, query), TTL_SECONDS, json.dumps(envelope))
    except Exception:
        pass


def bump_org(org_id: int | None) -> None:
    """Invalidate all cached answers for an org (call after its data changes)."""
    if not org_id:
        return
    r = _get_redis()
    if r is None:
        return
    try:
        r.incr(f"qcache_ver:{org_id}")
    except Exception:
        pass
