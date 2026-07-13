"""
Session memory (Constitution §10, §11).

Session-only context so follow-ups resolve ("Golf Hills price" -> "Payment plan?"
means Golf Hills). It NEVER answers from cache — it only fills missing entities;
every factual answer still re-queries SQL/RAG. No permanent memory in V1.

Backed by Redis; falls back to an in-process dict if Redis is unavailable so
the engine still runs in dev.
"""
from __future__ import annotations

import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)

_TTL_SECONDS = 60 * 60 * 3  # 3h session window
_MAX_TURNS = 8


class _MemoryStore:
    def __init__(self) -> None:
        self._redis = None
        self._fallback: dict[str, str] = {}
        try:
            import redis

            self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            self._redis.ping()
        except Exception as exc:
            logger.warning("Redis unavailable (%s); using in-memory session store.", exc)
            self._redis = None

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def get(self, session_id: str) -> dict:
        raw = None
        if self._redis:
            raw = self._redis.get(self._key(session_id))
        else:
            raw = self._fallback.get(self._key(session_id))
        return json.loads(raw) if raw else {"turns": [], "last_project_ids": []}

    def save(self, session_id: str, state: dict) -> None:
        state["turns"] = state.get("turns", [])[-_MAX_TURNS:]
        raw = json.dumps(state)
        if self._redis:
            self._redis.setex(self._key(session_id), _TTL_SECONDS, raw)
        else:
            self._fallback[self._key(session_id)] = raw

    def remember_turn(
        self,
        session_id: str,
        *,
        query: str,
        intents: list[str],
        project_ids: list[int],
        answer: str | None = None,
    ) -> None:
        state = self.get(session_id)
        turn = {"query": query, "intents": intents}
        if answer:
            turn["answer"] = answer[:400]  # short snippet for conversation context
        state["turns"].append(turn)
        if project_ids:
            state["last_project_ids"] = project_ids  # for follow-up entity resolution
        self.save(session_id, state)

    def last_project_ids(self, session_id: str) -> list[int]:
        return self.get(session_id).get("last_project_ids", [])

    def recent_dialogue(self, session_id: str, max_turns: int = 4) -> list[dict]:
        """The last few (query, answer) turns, oldest first — for LLM context."""
        return self.get(session_id).get("turns", [])[-max_turns:]


session_store = _MemoryStore()
