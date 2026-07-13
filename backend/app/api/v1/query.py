"""The main engine endpoint — natural-language query in, structured answer out."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.core.tenancy import org_scope_id
from app.database import get_db
from app.models import User
from app.schemas import QueryRequest, QueryResponse
from app.services import ratelimit
from app.services.orchestrator import handle_query
from app.services.renderer import blocks_to_text

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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a query through the hybrid pipeline (Intent → DB → RAG → LLM → Render).

    Works with a JWT (web app) OR an X-API-Key header (integrations). Set
    `format` to "blocks" (default), "text", or "voice" — `answer_text` is a
    ready-to-use plain-text answer for CRM/WhatsApp/voice consumers.
    """
    # Anti-flood: only for the public widget (API key). Employees are trusted
    # and already have per-user/per-org quotas.
    if getattr(user, "_via_api_key", False):
        ok, retry = ratelimit.flood_check(org_scope_id(user), payload.session_id, client_ip(request))
        if not ok:
            raise HTTPException(
                status_code=429,
                detail="You're sending messages too quickly. Please wait a moment and try again.",
                headers={"Retry-After": str(retry)},
            )
    env = handle_query(db, payload.query, payload.session_id, user)
    voice = (payload.format or "blocks").lower() == "voice"
    env["answer_text"] = blocks_to_text(env.get("content", {}).get("blocks", []), voice=voice)
    return env
