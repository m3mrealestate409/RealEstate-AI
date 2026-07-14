"""The main engine endpoint — natural-language query in, structured answer out."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.core.tenancy import org_scope_id
from app.database import get_db
from app.models import Organization, User
from app.schemas import QueryRequest, QueryResponse
from app.services import livechat, notify, ratelimit
from app.services.orchestrator import handle_query
from app.services.renderer import blocks_to_text


def _human_mode_envelope(session_id: str) -> dict:
    """Returned when a human agent has taken over — the AI stays silent and the
    visitor's message is just recorded; the agent replies via polling."""
    return {
        "answer_type": "text", "content": {"blocks": []}, "citations": [],
        "handlers_used": ["human"], "session_id": session_id, "not_available": False,
        "confidence": 1.0, "detected_intents": [], "resolved_from_memory": False,
        "resolved_via": "", "resolution_note": None, "llm_provider": "human",
        "suggestions": [], "human_mode": True, "answer_text": "",
    }

router = APIRouter(prefix="/v1", tags=["engine"])


def client_ip(request: Request) -> str:
    """Real client IP — trust X-Forwarded-For's first entry when behind a proxy."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/query", response_model=QueryResponse)
def query(
    payload: QueryRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a query through the hybrid pipeline (Intent → DB → RAG → LLM → Render).

    Works with a JWT (web app) OR an X-API-Key header (integrations). Set
    `format` to "blocks" (default), "text", or "voice" — `answer_text` is a
    ready-to-use plain-text answer for CRM/WhatsApp/voice consumers.
    """
    is_widget = getattr(user, "_via_api_key", False)
    cs = None
    if is_widget:
        # Anti-flood: only for the public widget. Employees are trusted.
        ok, retry = ratelimit.flood_check(org_scope_id(user), payload.session_id, client_ip(request))
        if not ok:
            raise HTTPException(
                status_code=429,
                detail="You're sending messages too quickly. Please wait a moment and try again.",
                headers={"Retry-After": str(retry)},
            )
        # Record the visitor's message for the live-chat console. If a human has
        # taken over this session, the AI stays silent (agent replies via poll).
        org_id = org_scope_id(user)
        cs, created = livechat.get_or_create_session(db, org_id, payload.session_id or "anon")
        livechat.add_message(db, cs, role="user", text=payload.query)
        livechat.touch_seen(db, cs)  # visitor is clearly online right now
        # First message of a new visitor → fire a "new chat" notification
        # (best-effort, in the background so the reply isn't delayed).
        if created and org_id is not None:
            org = db.get(Organization, org_id)
            if org and (org.notify_provider or "off") != "off":
                msg = notify.build_new_chat_message(payload.query, payload.page_url)
                background.add_task(notify.send, org.notify_provider, dict(org.notify_config or {}), msg)
        if cs.mode == "human":
            return _human_mode_envelope(payload.session_id or "anon")

    env = handle_query(db, payload.query, payload.session_id, user)
    voice = (payload.format or "blocks").lower() == "voice"
    env["answer_text"] = blocks_to_text(env.get("content", {}).get("blocks", []), voice=voice)
    if is_widget and cs is not None:
        livechat.add_message(db, cs, role="ai", text=env.get("answer_text", ""))
    return env
