"""Analytics endpoints — powered by the query_log. Manager+ only."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.database import get_db
from app.models import Document, Project, QueryLog, RagChunk, User

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(require_role("manager"))):
    return {
        "projects": db.query(func.count(Project.id)).scalar(),
        "documents": db.query(func.count(Document.id)).scalar(),
        "active_chunks": db.query(func.count(RagChunk.id)).filter(RagChunk.is_active.is_(True)).scalar(),
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require_role("manager"))):
    total = db.query(func.count(QueryLog.id)).scalar() or 0
    today = db.query(func.count(QueryLog.id)).filter(
        func.date(QueryLog.created_at) == date.today()
    ).scalar() or 0
    misses = db.query(func.count(QueryLog.id)).filter(QueryLog.not_available.is_(True)).scalar() or 0
    avg_latency = db.query(func.avg(QueryLog.latency_ms)).scalar()

    # Queries per day, last 7 days.
    since = date.today() - timedelta(days=6)
    daily_rows = (
        db.query(func.date(QueryLog.created_at).label("d"), func.count(QueryLog.id))
        .filter(func.date(QueryLog.created_at) >= since)
        .group_by("d").all()
    )
    daily_map = {str(d): c for d, c in daily_rows}
    daily = [
        {"date": str(since + timedelta(days=i)), "count": daily_map.get(str(since + timedelta(days=i)), 0)}
        for i in range(7)
    ]

    # Top intents (intents is a JSONB array per row).
    intent_counts: dict[str, int] = {}
    project_counts: dict[int, int] = {}
    for row in db.query(QueryLog.intents, QueryLog.project_ids).all():
        for it in (row[0] or []):
            intent_counts[it] = intent_counts.get(it, 0) + 1
        for pid in (row[1] or []):
            project_counts[pid] = project_counts.get(pid, 0) + 1

    top_intents = sorted(intent_counts.items(), key=lambda x: -x[1])[:6]
    top_pids = sorted(project_counts.items(), key=lambda x: -x[1])[:6]
    id_to_name = {p.id: p.name for p in db.query(Project).all()}
    top_projects = [{"project": id_to_name.get(pid, f"#{pid}"), "count": c} for pid, c in top_pids]

    recent_misses = [
        {"query": q, "at": (ts.isoformat() if ts else None)}
        for q, ts in db.query(QueryLog.query, QueryLog.created_at)
        .filter(QueryLog.not_available.is_(True))
        .order_by(QueryLog.created_at.desc())
        .limit(8).all()
    ]

    return {
        "total_queries": total,
        "queries_today": today,
        "miss_rate": round(misses / total * 100, 1) if total else 0.0,
        "avg_latency_ms": round(float(avg_latency), 1) if avg_latency is not None else 0.0,
        "daily": daily,
        "top_intents": [{"intent": k, "count": v} for k, v in top_intents],
        "top_projects": top_projects,
        "recent_misses": recent_misses,
    }
