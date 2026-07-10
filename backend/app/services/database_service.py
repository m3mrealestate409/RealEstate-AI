"""
Structured lookups — the SQL-first source of truth (Constitution §5).

Every function returns render-ready data AND citation metadata (source +
last_updated) so the composer can satisfy the Citation Policy (§9). These
handle price/plan/possession/inventory/builder/status/offer — the volatile
facts that must NEVER come from RAG or the LLM.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import (
    Configuration,
    Inventory,
    Offer,
    PaymentPlan,
    Price,
    Project,
)


def _iso(d) -> str | None:
    return d.isoformat() if d else None


def get_project(db: Session, project_id: int) -> Project | None:
    return db.get(Project, project_id)


def current_price(db: Session, project_id: int) -> dict:
    """Current price per configuration (effective_to IS NULL)."""
    configs = db.query(Configuration).filter(Configuration.project_id == project_id).all()
    rows, last_updated = [], None
    for cfg in configs:
        price = (
            db.query(Price)
            .filter(
                Price.configuration_id == cfg.id,
                or_(Price.effective_to.is_(None), Price.effective_to >= date.today()),
            )
            .order_by(Price.effective_from.desc())
            .first()
        )
        if not price:
            continue
        rows.append(
            {
                "configuration": cfg.type,
                "carpet_area": float(cfg.carpet_area) if cfg.carpet_area else None,
                "base_price": float(price.base_price),
                "price_unit": price.price_unit,
                "plc": float(price.plc) if price.plc else None,
                "gst_percent": float(price.gst_percent) if price.gst_percent else None,
                "source": price.source,
                "effective_from": _iso(price.effective_from),
            }
        )
        last_updated = price.effective_from if not last_updated else max(last_updated, price.effective_from)
    return {"found": bool(rows), "prices": rows, "last_updated": _iso(last_updated)}


def payment_plans(db: Session, project_id: int) -> dict:
    plans = (
        db.query(PaymentPlan)
        .filter(PaymentPlan.project_id == project_id, PaymentPlan.is_active.is_(True))
        .all()
    )
    out = []
    last_updated = None
    for p in plans:
        out.append(
            {
                "name": p.name,
                "description": p.description,
                "milestones": [
                    {"label": m.label, "percent": float(m.percent)} for m in p.milestones
                ],
            }
        )
        last_updated = p.updated_at if not last_updated else max(last_updated, p.updated_at)
    return {"found": bool(out), "payment_plans": out, "last_updated": _iso(last_updated)}


def inventory(db: Session, project_id: int) -> dict:
    configs = db.query(Configuration).filter(Configuration.project_id == project_id).all()
    rows, last_updated = [], None
    for cfg in configs:
        inv = db.query(Inventory).filter(Inventory.configuration_id == cfg.id).first()
        if not inv:
            continue
        rows.append(
            {
                "configuration": cfg.type,
                "total_units": inv.total_units,
                "available_units": inv.available_units,
            }
        )
        last_updated = inv.updated_at if not last_updated else max(last_updated, inv.updated_at)
    return {"found": bool(rows), "inventory": rows, "last_updated": _iso(last_updated)}


def possession(db: Session, project_id: int) -> dict:
    p = db.get(Project, project_id)
    if not p:
        return {"found": False}
    return {
        "found": p.possession_date is not None,
        "possession_date": _iso(p.possession_date),
        "project_status": p.project_status,
        "last_updated": _iso(p.updated_at),
    }


def builder(db: Session, project_id: int) -> dict:
    p = db.get(Project, project_id)
    if not p or not p.builder:
        return {"found": False}
    return {
        "found": True,
        "builder": p.builder.name,
        "rera_id": p.builder.rera_id,
        "last_updated": _iso(p.updated_at),
    }


def status(db: Session, project_id: int) -> dict:
    p = db.get(Project, project_id)
    if not p:
        return {"found": False}
    return {
        "found": True,
        "project_status": p.project_status,
        "rera_number": p.rera_number,
        "launch_date": _iso(p.launch_date),
        "possession_date": _iso(p.possession_date),
        "last_updated": _iso(p.updated_at),
    }


def offers(db: Session, project_id: int) -> dict:
    today = date.today()
    active = (
        db.query(Offer)
        .filter(
            Offer.project_id == project_id,
            Offer.is_active.is_(True),
            or_(Offer.valid_to.is_(None), Offer.valid_to >= today),
            or_(Offer.valid_from.is_(None), Offer.valid_from <= today),
        )
        .all()
    )
    return {
        "found": bool(active),
        "offers": [{"title": o.title, "details": o.details, "valid_to": _iso(o.valid_to)} for o in active],
    }


# Intent -> resolver mapping used by the orchestrator.
DB_RESOLVERS = {
    "price": current_price,
    "payment_plan": payment_plans,
    "inventory": inventory,
    "possession": possession,
    "builder": builder,
    "status": status,
    "offer": offers,
}
