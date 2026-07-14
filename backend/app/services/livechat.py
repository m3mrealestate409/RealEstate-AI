"""
Live chat / human-takeover helpers.

Every website-widget conversation is recorded so an employee can watch it in the
agent console and, when they choose, take it over from the AI. Backed by
Postgres (persistent, easy to list/poll at small scale).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession, User

_MAX_TEXT = 4000
# A visitor counts as "online" if their widget has polled within this window
# (the widget heartbeats every ~3s; generous enough to tolerate jitter).
ONLINE_SECONDS = 30


def _aware(dt):
    """Treat naive DB timestamps as UTC so comparisons never crash."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_online(cs: "ChatSession") -> bool:
    seen = _aware(cs.last_seen_at)
    if seen is None:
        return False
    return (datetime.now(timezone.utc) - seen).total_seconds() < ONLINE_SECONDS


def touch_seen(db: Session, cs: "ChatSession") -> None:
    cs.last_seen_at = datetime.now(timezone.utc)
    db.commit()


def get_or_create_session(db: Session, org_id: int | None, session_id: str) -> tuple[ChatSession, bool]:
    """Returns (session, created) — `created` is True on the visitor's first
    message, which is when we fire a "new chat" notification."""
    cs = (
        db.query(ChatSession)
        .filter(ChatSession.organization_id == org_id, ChatSession.session_id == session_id)
        .first()
    )
    if cs is not None:
        return cs, False
    cs = ChatSession(organization_id=org_id, session_id=session_id, mode="ai")
    db.add(cs)
    db.commit()
    db.refresh(cs)
    return cs, True


def get_session(db: Session, org_id: int | None, session_id: str) -> ChatSession | None:
    return (
        db.query(ChatSession)
        .filter(ChatSession.organization_id == org_id, ChatSession.session_id == session_id)
        .first()
    )


def add_message(db: Session, cs: ChatSession, *, role: str, text: str, agent_id: int | None = None) -> ChatMessage:
    m = ChatMessage(session_pk=cs.id, role=role, text=(text or "")[:_MAX_TEXT], agent_id=agent_id)
    db.add(m)
    cs.last_activity_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(m)
    return m


def set_mode(db: Session, cs: ChatSession, mode: str, agent_id: int | None = None) -> None:
    cs.mode = mode
    cs.agent_id = agent_id if mode == "human" else None
    db.commit()


def messages_after(db: Session, cs: ChatSession, after_id: int = 0, roles: list[str] | None = None) -> list[ChatMessage]:
    q = db.query(ChatMessage).filter(ChatMessage.session_pk == cs.id, ChatMessage.id > after_id)
    if roles:
        q = q.filter(ChatMessage.role.in_(roles))
    return q.order_by(ChatMessage.id).all()


def transcript(db: Session, cs: ChatSession) -> list[ChatMessage]:
    return db.query(ChatMessage).filter(ChatMessage.session_pk == cs.id).order_by(ChatMessage.id).all()


def list_active(db: Session, org_id: int | None, minutes: int = 120) -> list[dict]:
    """Recent sessions with a one-line preview — powers the console's inbox."""
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    q = db.query(ChatSession).filter(ChatSession.last_activity_at >= since)
    if org_id is not None:
        q = q.filter(ChatSession.organization_id == org_id)
    sessions = q.order_by(ChatSession.last_activity_at.desc()).limit(100).all()

    agent_names = {u.id: (u.name or u.email) for u in db.query(User).all()}
    out = []
    for cs in sessions:
        last = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_pk == cs.id)
            .order_by(ChatMessage.id.desc())
            .first()
        )
        out.append({
            "session_id": cs.session_id,
            "mode": cs.mode,
            "agent": agent_names.get(cs.agent_id),
            "last_message": (last.text[:80] if last else ""),
            "last_role": (last.role if last else None),
            "last_activity": cs.last_activity_at.isoformat() if cs.last_activity_at else None,
            "online": is_online(cs),
        })
    return out
