"""The main engine endpoint — natural-language query in, structured answer out."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.core.tenancy import apply_viewing_tenant, org_scope_id
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

# Channels an API key may declare. Anything else is treated as a generic "api"
# integration (never as the public widget).
VALID_SOURCES = {"widget", "crm", "whatsapp", "voice", "api"}


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
    # Super-admin who has opened one company's console view → scope this query to
    # that tenant. No-op for tenant users and API-key / widget callers.
    apply_viewing_tenant(request, user)
    via_key = getattr(user, "_via_api_key", False)
    # Resolve the calling channel. A JWT is always the web app (staff). For an
    # API key, the KEY decides (set by the admin when creating it) — the caller
    # can't spoof it, and an internal tool can never look like the website.
    if not via_key:
        source = "app"
    elif getattr(user, "_api_key_channel", "website") == "internal":
        # Internal keys may refine the analytics tag, but never become "widget".
        s = (payload.source or "crm").lower()
        source = s if s in VALID_SOURCES - {"widget"} else "crm"
    else:
        source = "widget"
    # ONLY the public website widget gets live-chat recording, new-chat alerts,
    # auto-leads and the public budget. A CRM/WhatsApp/voice integration must
    # never show up as a "visitor" in the Live Chat console.
    is_widget = via_key and source == "widget"

    cs = None
    if via_key:
        # Anti-flood. Public widget → per-session + per-IP. Trusted server
        # integrations call from one IP for the whole team → per-org burst.
        if is_widget:
            ok, retry = ratelimit.flood_check(org_scope_id(user), payload.session_id, client_ip(request))
        else:
            ok, retry = ratelimit.api_flood_check(org_scope_id(user))
        if not ok:
            raise HTTPException(
                status_code=429,
                detail="You're sending messages too quickly. Please wait a moment and try again.",
                headers={"Retry-After": str(retry)},
            )

    if is_widget:
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

    env = handle_query(db, payload.query, payload.session_id, user, source=source)
    voice = (payload.format or "blocks").lower() == "voice"
    env["answer_text"] = blocks_to_text(env.get("content", {}).get("blocks", []), voice=voice)
    if is_widget and cs is not None:
        livechat.add_message(db, cs, role="ai", text=env.get("answer_text", ""))
    return env
