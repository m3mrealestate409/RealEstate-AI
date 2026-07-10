"""The main engine endpoint — natural-language query in, structured answer out."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import QueryRequest, QueryResponse
from app.services.orchestrator import handle_query

router = APIRouter(prefix="/v1", tags=["engine"])


@router.post("/query", response_model=QueryResponse)
def query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a query through the hybrid pipeline (Intent → DB → RAG → LLM → Render)."""
    return handle_query(db, payload.query, payload.session_id, user)
