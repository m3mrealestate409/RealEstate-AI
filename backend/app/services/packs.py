"""
Project packs — move a project's whole knowledge tree between organizations.

A project on its own is a name and a city. What actually answers questions
lives underneath it: configurations, their prices, payment plans and the
milestones inside them, towers, amenities, location points, offers. A CSV of
project rows onboards a company that still knows nothing; a pack onboards one
that can answer on day one.

Two things make this more than a dict dump:

  * **Ids cannot travel.** `Price.payment_plan_id` points at a payment plan of
    the same project, so a pack records the plan's NAME and the importer relinks
    it against the newly created plan. Carrying the id would silently attach a
    price to whatever row happened to own that id in the target database.
  * **Builders are per-company.** A project references a builder by id, and the
    target company has its own builder list. The importer matches by name and
    creates one if it has to, rather than pointing across a tenant boundary.

Documents are deliberately NOT in a pack: they are files on disk plus their
embeddings, and one company's brochure is not another's to hold.
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models import (
    Amenity,
    Builder,
    Configuration,
    Inventory,
    LocationPoint,
    Offer,
    PaymentPlan,
    PaymentPlanMilestone,
    Price,
    Project,
    Tower,
)

logger = logging.getLogger(__name__)

PACK_VERSION = 1

# Project columns worth carrying. `id`, `organization_id` and `builder_id` are
# excluded on purpose — they are properties of where the project LIVED, not of
# what it is, and re-using them across tenants is exactly the bug to avoid.
_PROJECT_FIELDS = (
    "name", "slug", "city", "locality", "rera_number", "project_status",
    "project_type", "land_parcel", "green_area", "rise_type",
    "launch_date", "launch_price", "possession_date",
)


def _val(v):
    """JSON-safe: Numeric → float, date → ISO string."""
    if v is None or isinstance(v, (str, int, bool)):
        return v
    if isinstance(v, date):
        return v.isoformat()
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


def _row(obj, fields) -> dict:
    return {f: _val(getattr(obj, f, None)) for f in fields}


def _to_date(v):
    return date.fromisoformat(v) if isinstance(v, str) and v else None


# ------------------------------- Export -----------------------------------
def export_project(db: Session, project: Project) -> dict:
    """One project and everything under it, as plain JSON."""
    # Price has no `payment_plan` relationship, only the raw id — and the plan
    # always belongs to this same project, so resolve names from here rather
    # than querying per price.
    plan_name_by_id = {pp.id: pp.name for pp in project.payment_plans}

    plans = []
    for pp in project.payment_plans:
        plans.append({
            "name": pp.name, "description": pp.description, "is_active": pp.is_active,
            "milestones": [
                {"sequence": m.sequence, "label": m.label, "percent": _val(m.percent)}
                for m in sorted(pp.milestones, key=lambda m: m.sequence or 0)
            ],
        })

    configs = []
    for c in project.configurations:
        configs.append({
            "type": c.type,
            "carpet_area": _val(c.carpet_area),
            "built_up_area": _val(c.built_up_area),
            "super_area": _val(c.super_area),
            "inventory": (
                {"total_units": c.inventory.total_units, "available_units": c.inventory.available_units}
                if c.inventory else None
            ),
            "prices": [{
                # The plan's NAME, not its id — see the module docstring.
                "payment_plan": plan_name_by_id.get(p.payment_plan_id),
                "base_price": _val(p.base_price),
                "price_unit": p.price_unit,
                "plc": _val(p.plc),
                "gst_percent": _val(p.gst_percent),
                "effective_from": _val(p.effective_from),
                "effective_to": _val(p.effective_to),
                "source": p.source,
            } for p in c.prices],
        })

    return {
        "project": _row(project, _PROJECT_FIELDS),
        "builder": project.builder.name if project.builder else None,
        "payment_plans": plans,
        "configurations": configs,
        "towers": [_row(t, ("name", "floors", "height", "units_per_floor")) for t in project.towers],
        "amenities": [_row(a, ("name", "category")) for a in project.amenities],
        "location_points": [
            _row(lp, ("category", "name", "distance", "notes")) for lp in project.location_points
        ],
        "offers": [
            _row(o, ("title", "details", "valid_from", "valid_to", "is_active")) for o in project.offers
        ],
    }


def export_org(db: Session, org_id: int | None, project_ids: list[int] | None = None) -> dict:
    q = db.query(Project).filter(Project.organization_id == org_id)
    if project_ids:
        q = q.filter(Project.id.in_(project_ids))
    projects = q.order_by(Project.name).all()
    return {
        "pack_version": PACK_VERSION,
        "exported_at": None,   # stamped by the caller; keeps this function pure
        "projects": [export_project(db, p) for p in projects],
    }


# ------------------------------- Import -----------------------------------
def _builder_for(db: Session, org_id: int | None, name: str | None) -> int | None:
    """Match the target company's own builder by name, creating one if needed.
    Never returns another tenant's builder."""
    name = (name or "").strip()
    if not name:
        return None
    b = (
        db.query(Builder)
        .filter(Builder.name.ilike(name), Builder.organization_id == org_id)
        .first()
    )
    if not b:
        b = Builder(name=name, organization_id=org_id)
        db.add(b)
        db.flush()
    return b.id


def import_project(db: Session, org_id: int | None, item: dict) -> str:
    """Create one project from a pack entry. Returns 'created' or 'skipped'.
    Raises on malformed input so the caller can report the row."""
    pdata = dict(item.get("project") or {})
    name = (pdata.get("name") or "").strip()
    slug = (pdata.get("slug") or "").strip()
    if not name or not slug:
        raise ValueError("project needs a name and a slug")

    # Scoped: another tenant owning this slug is irrelevant here.
    if (
        db.query(Project)
        .filter(Project.slug == slug, Project.organization_id == org_id)
        .first()
    ):
        return "skipped"

    project = Project(
        organization_id=org_id,
        builder_id=_builder_for(db, org_id, item.get("builder")),
        **{
            k: (_to_date(pdata.get(k)) if k in ("launch_date", "possession_date") else pdata.get(k))
            for k in _PROJECT_FIELDS
        },
    )
    db.add(project)
    db.flush()

    # Payment plans first: prices below relink to them by name.
    by_name: dict[str, PaymentPlan] = {}
    for pp in item.get("payment_plans") or []:
        plan = PaymentPlan(
            project_id=project.id, name=pp.get("name") or "Plan",
            description=pp.get("description"),
            is_active=pp.get("is_active", True),
        )
        db.add(plan)
        db.flush()
        for m in pp.get("milestones") or []:
            db.add(PaymentPlanMilestone(
                payment_plan_id=plan.id, sequence=m.get("sequence") or 0,
                label=m.get("label") or "", percent=m.get("percent") or 0,
            ))
        by_name[plan.name.lower()] = plan

    for c in item.get("configurations") or []:
        cfg = Configuration(
            project_id=project.id, type=c.get("type") or "—",
            carpet_area=c.get("carpet_area"), built_up_area=c.get("built_up_area"),
            super_area=c.get("super_area"),
        )
        db.add(cfg)
        db.flush()
        inv = c.get("inventory")
        if inv:
            db.add(Inventory(
                configuration_id=cfg.id,
                total_units=inv.get("total_units") or 0,
                available_units=inv.get("available_units") or 0,
            ))
        for p in c.get("prices") or []:
            plan = by_name.get((p.get("payment_plan") or "").lower())
            db.add(Price(
                configuration_id=cfg.id,
                payment_plan_id=plan.id if plan else None,   # relinked, not copied
                base_price=p.get("base_price") or 0,
                price_unit=p.get("price_unit") or "per_sqft",
                plc=p.get("plc"), gst_percent=p.get("gst_percent"),
                effective_from=_to_date(p.get("effective_from")) or date.today(),
                effective_to=_to_date(p.get("effective_to")),
                source=p.get("source") or "import",
            ))

    for t in item.get("towers") or []:
        db.add(Tower(project_id=project.id, name=t.get("name") or "—", floors=t.get("floors"),
                     height=t.get("height"), units_per_floor=t.get("units_per_floor")))
    for a in item.get("amenities") or []:
        db.add(Amenity(project_id=project.id, name=a.get("name") or "—", category=a.get("category")))
    for lp in item.get("location_points") or []:
        db.add(LocationPoint(project_id=project.id, category=lp.get("category"),
                             name=lp.get("name") or "—", distance=lp.get("distance"),
                             notes=lp.get("notes")))
    for o in item.get("offers") or []:
        db.add(Offer(project_id=project.id, title=o.get("title") or "—", details=o.get("details"),
                     valid_from=_to_date(o.get("valid_from")), valid_to=_to_date(o.get("valid_to")),
                     is_active=o.get("is_active", True)))
    return "created"


def import_pack(db: Session, org_id: int | None, pack: dict) -> dict:
    """Import a whole pack. One bad project is reported and skipped rather than
    losing the rest — an onboarding half-done beats an onboarding refused."""
    items = pack.get("projects")
    if not isinstance(items, list):
        raise ValueError("Not a project pack: expected a 'projects' list.")
    created, skipped, errors = 0, 0, []
    for i, item in enumerate(items, start=1):
        name = ((item or {}).get("project") or {}).get("name") or f"#{i}"
        try:
            with db.begin_nested():        # savepoint: a bad row rolls back alone
                result = import_project(db, org_id, item)
            created += result == "created"
            skipped += result == "skipped"
        except Exception as exc:           # noqa: BLE001 — reported, not raised
            logger.warning("Pack import failed for %s: %s", name, exc)
            errors.append(f"{name}: {exc}")
    return {"created": created, "skipped_existing": skipped, "errors": errors}
