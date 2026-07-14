"""
Live chat endpoints.

Widget side (auth: API key):
- GET  /v1/widget/poll                         → visitor's widget polls for agent
                                                  messages + current mode.

Agent console side (auth: employee JWT, sales+):
- GET  /v1/admin/live/sessions                 → inbox of recent conversations
- GET  /v1/admin/live/sessions/{sid}           → full transcript
- POST /v1/admin/live/sessions/{sid}/takeover  → switch to human mode (this agent)
- POST /v1/admin/live/sessions/{sid}/message   → agent sends a reply to the visitor
- POST /v1/admin/live/sessions/{sid}/release   → hand the chat back to the AI
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_live_chat
from app.core.tenancy import org_scope_id
from app.database import get_db
from app.models import User
from app.services import livechat

router = APIRouter(tags=["livechat"])


# ---- Widget side -----------------------------------------------------------
@router.get("/v1/widget/poll")
def widget_poll(
    session_id: str,
    after: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The widget polls this to receive human-agent messages and mode changes."""
    org_id = org_scope_id(user)
    cs = livechat.get_session(db, org_id, session_id)
    if cs is None:
        return {"mode": "ai", "agent_name": None, "messages": []}
    livechat.touch_seen(db, cs)  # heartbeat → visitor is online
    msgs = livechat.messages_after(db, cs, after_id=after, roles=["agent", "system"])
    agent_name = None
    if cs.agent_id:
        agent = db.get(User, cs.agent_id)
        agent_name = (agent.name or agent.email) if agent else None
    return {
        "mode": cs.mode,
        "agent_name": agent_name,
        "messages": [
            {"id": m.id, "role": m.role, "text": m.text,
             "at": m.created_at.isoformat() if m.created_at else None}
            for m in msgs
        ],
    }


# ---- Agent console side ----------------------------------------------------
@router.get("/v1/admin/live/sessions")
def list_sessions(user: User = Depends(require_live_chat), db: Session = Depends(get_db)):
    return livechat.list_active(db, org_scope_id(user))


def _load(db: Session, user: User, session_id: str):
    cs = livechat.get_session(db, org_scope_id(user), session_id)
    if cs is None:
        raise HTTPException(404, "Chat not found")
    return cs


@router.get("/v1/admin/live/sessions/{session_id}")
def get_transcript(session_id: str, user: User = Depends(require_live_chat), db: Session = Depends(get_db)):
    cs = _load(db, user, session_id)
    agent_name = None
    if cs.agent_id:
        agent = db.get(User, cs.agent_id)
        agent_name = (agent.name or agent.email) if agent else None
    return {
        "session_id": cs.session_id, "mode": cs.mode, "agent": agent_name,
        "online": livechat.is_online(cs),
        "messages": [
            {"id": m.id, "role": m.role, "text": m.text,
             "at": m.created_at.isoformat() if m.created_at else None}
            for m in livechat.transcript(db, cs)
        ],
    }


@router.post("/v1/admin/live/sessions/{session_id}/takeover")
def takeover(session_id: str, user: User = Depends(require_live_chat), db: Session = Depends(get_db)):
    cs = _load(db, user, session_id)
    livechat.set_mode(db, cs, "human", agent_id=user.id)
    livechat.add_message(db, cs, role="system", text=f"{user.name or 'An agent'} joined the chat.", agent_id=user.id)
    return {"ok": True, "mode": "human"}


class AgentMsgIn(BaseModel):
    text: str


@router.post("/v1/admin/live/sessions/{session_id}/message")
def agent_message(
    session_id: str, payload: AgentMsgIn,
    user: User = Depends(require_live_chat), db: Session = Depends(get_db),
):
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(422, "Message is empty.")
    cs = _load(db, user, session_id)
    if cs.mode != "human":
        livechat.set_mode(db, cs, "human", agent_id=user.id)
    m = livechat.add_message(db, cs, role="agent", text=text, agent_id=user.id)
    return {"ok": True, "id": m.id}


@router.post("/v1/admin/live/sessions/{session_id}/release")
def release(session_id: str, user: User = Depends(require_live_chat), db: Session = Depends(get_db)):
    cs = _load(db, user, session_id)
    livechat.set_mode(db, cs, "ai")
    livechat.add_message(db, cs, role="system", text="The AI assistant is back.")
    return {"ok": True, "mode": "ai"}
