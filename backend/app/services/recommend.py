"""
Recommendation engine — deterministic ranking over SQL facts (Golden Rule).

"Best 3BHK under 2 crore" → filter configurations by type + computed total price,
rank cheapest first. The LLM may later add narrative, but the SHORTLIST itself
is computed here, never invented.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Configuration, Price, Project


def _current_price(db: Session, config_id: int) -> Price | None:
    return (
        db.query(Price)
        .filter(
            Price.configuration_id == config_id,
            or_(Price.effective_to.is_(None), Price.effective_to >= date.today()),
        )
        .order_by(Price.effective_from.desc())
        .first()
    )


def _total_price(price: Price, cfg: Configuration) -> float | None:
    if price.price_unit == "total":
        base = float(price.base_price)
    else:
        area = cfg.super_area or cfg.built_up_area or cfg.carpet_area
        if not area:
            return None
        base = float(price.base_price) * float(area)
    return base + float(price.plc or 0)


def recommend(
    db: Session, *, config_type: str | None = None, max_budget: float | None = None,
    limit: int = 5, org_id: int | None = None
) -> list[dict]:
    q = db.query(Configuration).join(Project)
    if org_id is not None:
        q = q.filter(Project.organization_id == org_id)
    if config_type:
        q = q.filter(Configuration.type.ilike(config_type))

    results = []
    for cfg in q.all():
        price = _current_price(db, cfg.id)
        if not price:
            continue
        total = _total_price(price, cfg)
        if total is None:
            continue
        if max_budget and total > max_budget:
            continue
        results.append(
            {
                "project": cfg.project.name,
                "project_id": cfg.project_id,
                "configuration": cfg.type,
                "total_price": round(total),
                "status": cfg.project.project_status,
                "possession": cfg.project.possession_date.isoformat() if cfg.project.possession_date else None,
            }
        )

    results.sort(key=lambda r: r["total_price"])
    return results[:limit]
