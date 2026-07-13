"""Analytics endpoints — powered by the query_log. Manager+ only."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.core.tenancy import org_scope_id
from app.database import get_db
from app.models import Document, Organization, Project, QueryLog, RagChunk, User
from app.services import quota

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(require_role("manager"))):
    org_id = org_scope_id(user)
    pq = db.query(func.count(Project.id))
    dq = db.query(func.count(Document.id)).join(Project, Project.id == Document.project_id)
    cq = db.query(func.count(RagChunk.id)).join(Project, Project.id == RagChunk.project_id).filter(RagChunk.is_active.is_(True))
    if org_id is not None:
        pq = pq.filter(Project.organization_id == org_id)
        dq = dq.filter(Project.organization_id == org_id)
        cq = cq.filter(Project.organization_id == org_id)
    return {"projects": pq.scalar(), "documents": dq.scalar(), "active_chunks": cq.scalar()}


@router.get("/usage")
def usage(db: Session = Depends(get_db), user: User = Depends(require_role("manager"))):
    """Per-employee AI-query usage today vs their tier limit, + company total."""
    today = date.today().isoformat()
    org_id = user.organization_id
    org = db.get(Organization, org_id) if org_id else None
    basic = org.basic_daily_limit if org else None
    advanced = org.advanced_daily_limit if org else None

    uq = db.query(User).filter(User.is_active.is_(True))
    if not user.is_super_admin and org_id:
        uq = uq.filter(User.organization_id == org_id)

    rows = []
    for u in uq.order_by(User.name).all():
        limit = (advanced if u.tier == "advanced" else basic)
        used = quota.used_today(u.id, today)
        rows.append({
            "name": u.name or u.email, "email": u.email, "tier": u.tier,
            "used": used, "limit": limit,
            "over": limit is not None and used >= limit,
        })
    rows.sort(key=lambda r: -(r["used"]))

    company = None
    if org and org.plan:
        company = {
            "used": quota.org_used_today(org_id, today),
            "limit": org.plan.daily_llm_quota,
            "plan": org.plan.name,
        }
    return {"employees": rows, "company": company}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require_role("manager"))):
    org_id = org_scope_id(user)

    def q():
        base = db.query(QueryLog)
        return base.filter(QueryLog.organization_id == org_id) if org_id is not None else base

    total = q().count()
    today = q().filter(func.date(QueryLog.created_at) == date.today()).count()
    misses = q().filter(QueryLog.not_available.is_(True)).count()
    avg_latency = q().with_entities(func.avg(QueryLog.latency_ms)).scalar()

    # Queries per day, last 7 days.
    since = date.today() - timedelta(days=6)
    daily_rows = (
        q().with_entities(func.date(QueryLog.created_at).label("d"), func.count(QueryLog.id))
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
    for row in q().with_entities(QueryLog.intents, QueryLog.project_ids).all():
        for it in (row[0] or []):
            intent_counts[it] = intent_counts.get(it, 0) + 1
        for pid in (row[1] or []):
            project_counts[pid] = project_counts.get(pid, 0) + 1

    top_intents = sorted(intent_counts.items(), key=lambda x: -x[1])[:6]
    top_pids = sorted(project_counts.items(), key=lambda x: -x[1])[:6]
    id_to_name = {p.id: p.name for p in db.query(Project).all()}
    top_projects = [{"project": id_to_name.get(pid, f"#{pid}"), "count": c} for pid, c in top_pids]

    recent_misses = [
        {"query": qtext, "at": (ts.isoformat() if ts else None)}
        for qtext, ts in q().with_entities(QueryLog.query, QueryLog.created_at)
        .filter(QueryLog.not_available.is_(True))
        .order_by(QueryLog.created_at.desc())
        .limit(8).all()
    ]

    # Top MISSED questions, grouped — the same question asked 20 times is one
    # row with count=20. This is the actionable signal: it tells the admin
    # exactly which data/brochure is missing from the knowledge base.
    miss_counts: dict[str, dict] = {}
    for (qtext,) in (
        q().with_entities(QueryLog.query)
        .filter(QueryLog.not_available.is_(True)).all()
    ):
        norm = (qtext or "").strip().lower()
        if not norm:
            continue
        slot = miss_counts.setdefault(norm, {"query": (qtext or "").strip(), "count": 0})
        slot["count"] += 1
    top_missed = sorted(miss_counts.values(), key=lambda x: -x["count"])[:10]

    return {
        "total_queries": total,
        "queries_today": today,
        "misses": misses,
        "miss_rate": round(misses / total * 100, 1) if total else 0.0,
        "avg_latency_ms": round(float(avg_latency), 1) if avg_latency is not None else 0.0,
        "daily": daily,
        "top_intents": [{"intent": k, "count": v} for k, v in top_intents],
        "top_projects": top_projects,
        "recent_misses": recent_misses,
        "top_missed": top_missed,
    }
