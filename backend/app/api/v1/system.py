"""System Health — live status of the moving parts (DB, Redis, LLM, embeddings)."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import require_role
from app.database import get_db
from app.models import User
from app.services.runtime_config import public_llm_config

router = APIRouter(prefix="/v1/admin/system", tags=["system"])


def _check_db(db: Session) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"name": "PostgreSQL", "ok": True, "detail": "connected"}
    except Exception as exc:
        return {"name": "PostgreSQL", "ok": False, "detail": str(exc)[:120]}


def _check_redis() -> dict:
    try:
        import redis

        r = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        return {"name": "Redis (session)", "ok": True, "detail": "connected"}
    except Exception as exc:
        return {"name": "Redis (session)", "ok": False, "detail": f"fallback in-memory ({str(exc)[:60]})"}


def _check_pgvector(db: Session) -> dict:
    try:
        row = db.execute(
            text("SELECT 1 FROM pg_extension WHERE extname='vector'")
        ).first()
        return {"name": "pgvector", "ok": bool(row), "detail": "installed" if row else "missing"}
    except Exception as exc:
        return {"name": "pgvector", "ok": False, "detail": str(exc)[:120]}


@router.get("/health")
def system_health(db: Session = Depends(get_db), user: User = Depends(require_role("manager"))):
    cfg = public_llm_config()
    checks = [
        _check_db(db),
        _check_pgvector(db),
        _check_redis(),
        {
            "name": "LLM Provider",
            "ok": True,
            "detail": f"{cfg['provider']} - {cfg['model']}"
            + (" - key set" if cfg["key_set"] else " - mock (no key)"),
        },
        {
            "name": "Embeddings",
            "ok": True,
            "detail": cfg["embedding_provider"],
        },
    ]
    return {"healthy": all(c["ok"] for c in checks), "checks": checks}
