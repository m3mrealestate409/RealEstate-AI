"""The main engine endpoint — natural-language query in, structured answer out."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import QueryRequest, QueryResponse
from app.services.orchestrator import handle_query
from app.services.renderer import blocks_to_text

router = APIRouter(prefix="/v1", tags=["engine"])


@router.post("/query", response_model=QueryResponse)
def query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a query through the hybrid pipeline (Intent → DB → RAG → LLM → Render).

    Works with a JWT (web app) OR an X-API-Key header (integrations). Set
    `format` to "blocks" (default), "text", or "voice" — `answer_text` is a
    ready-to-use plain-text answer for CRM/WhatsApp/voice consumers.
    """
    env = handle_query(db, payload.query, payload.session_id, user)
    voice = (payload.format or "blocks").lower() == "voice"
    env["answer_text"] = blocks_to_text(env.get("content", {}).get("blocks", []), voice=voice)
    return env
