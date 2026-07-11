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
    """Current price per configuration. Each config has a BASE price
    (payment_plan_id IS NULL) plus optional per-payment-plan overrides. A plan
    override supplies its own rate; PLC/GST are inherited from the base when the
    override leaves them blank."""
    today = date.today()
    configs = db.query(Configuration).filter(Configuration.project_id == project_id).all()
    rows, last_updated = [], None
    for cfg in configs:
        open_prices = (
            db.query(Price)
            .filter(
                Price.configuration_id == cfg.id,
                or_(Price.effective_to.is_(None), Price.effective_to >= today),
            )
            .order_by(Price.effective_from.desc())
            .all()
        )
        if not open_prices:
            continue

        # Latest open price per plan (None key = base price).
        by_plan: dict = {}
        for p in open_prices:
            by_plan.setdefault(p.payment_plan_id, p)  # first = latest (ordered desc)

        base = by_plan.get(None)
        base_plc = float(base.plc) if base and base.plc is not None else None
        base_gst = float(base.gst_percent) if base and base.gst_percent is not None else None

        plans = []
        for plan_id, p in by_plan.items():
            if plan_id is None:
                continue
            pp = db.get(PaymentPlan, plan_id)
            plans.append(
                {
                    "payment_plan_id": plan_id,
                    "plan": pp.name if pp else f"Plan {plan_id}",
                    "base_price": float(p.base_price),
                    "price_unit": p.price_unit,
                    "plc": float(p.plc) if p.plc is not None else base_plc,
                    "gst_percent": float(p.gst_percent) if p.gst_percent is not None else base_gst,
                    "source": p.source,
                    "effective_from": _iso(p.effective_from),
                }
            )
        plans.sort(key=lambda r: r["plan"])

        rows.append(
            {
                "configuration": cfg.type,
                "carpet_area": float(cfg.carpet_area) if cfg.carpet_area else None,
                "base_price": float(base.base_price) if base else None,
                "price_unit": base.price_unit if base else (plans[0]["price_unit"] if plans else "per_sqft"),
                "plc": base_plc,
                "gst_percent": base_gst,
                "source": base.source if base else None,
                "effective_from": _iso(base.effective_from) if base else None,
                "plans": plans,
            }
        )
        for p in open_prices:
            if p.effective_from:
                last_updated = p.effective_from if not last_updated else max(last_updated, p.effective_from)
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


def overview(db: Session, project_id: int) -> dict:
    """Project-level attributes: type, land parcel, green area, towers, status."""
    from app.models import Tower

    p = db.get(Project, project_id)
    if not p:
        return {"found": False}
    towers = db.query(Tower).filter(Tower.project_id == project_id).order_by(Tower.name).all()
    return {
        "found": True,
        "project_type": p.project_type,
        "land_parcel": p.land_parcel,
        "green_area": p.green_area,
        "project_status": p.project_status,
        "possession_date": _iso(p.possession_date),
        "total_towers": len(towers),
        "towers": [
            {"name": t.name, "floors": t.floors, "height": t.height,
             "units_per_floor": t.units_per_floor}
            for t in towers
        ],
        "last_updated": _iso(p.updated_at),
    }


def location(db: Session, project_id: int) -> dict:
    """Structured location details grouped by category."""
    from app.models import LocationPoint

    p = db.get(Project, project_id)
    if not p:
        return {"found": False}
    points = db.query(LocationPoint).filter(LocationPoint.project_id == project_id).all()
    grouped: dict[str, list] = {"nearby": [], "connectivity": [], "upcoming": []}
    for lp in points:
        grouped.setdefault(lp.category or "nearby", []).append(
            {"name": lp.name, "distance": lp.distance, "notes": lp.notes}
        )
    return {
        "found": bool(points),
        "city": p.city, "locality": p.locality,
        "nearby": grouped.get("nearby", []),
        "connectivity": grouped.get("connectivity", []),
        "upcoming": grouped.get("upcoming", []),
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
    "overview": overview,
    "location": location,
}
