"""
Data management (admin) — add/edit the structured facts behind a project:
configurations (+ current price + inventory) and payment plans. Plus CSV bulk
import for projects. All mutations are audited (§19).
"""
import csv
import io
import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import require_role
from app.core.tenancy import get_scoped_project
from app.database import get_db
from app.services import cache, packs
from app.models import (
    Amenity,
    Builder,
    Configuration,
    Inventory,
    LocationPoint,
    Organization,
    PaymentPlan,
    PaymentPlanMilestone,
    Price,
    Project,
    Setting,
    Tower,
    User,
)
from app.schemas import LocationPointIn, LocationPointOut, TowerIn, TowerOut

router = APIRouter(prefix="/v1/admin", tags=["data-management"])

DEFAULT_DOC_TYPES = ["brochure", "legal", "floor_plan", "master_plan", "price_list"]
_DOCTYPES_KEY = "document_types"


class ConfigurationIn(BaseModel):
    type: str
    super_area: float | None = None   # shown to users as "Size"
    base_price: float
    price_unit: str = "per_sqft"
    plc: float | None = None
    gst_percent: float | None = None
    total_units: int | None = None
    available_units: int | None = None
    source: str | None = "Manual entry"


class MilestoneIn(BaseModel):
    label: str
    percent: float


class PaymentPlanIn(BaseModel):
    name: str
    description: str | None = None
    milestones: list[MilestoneIn]


@router.post("/projects/{project_id}/configurations", status_code=201)
def add_configuration(
    project_id: int, payload: ConfigurationIn,
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    get_scoped_project(db, project_id, admin)

    cfg = Configuration(
        project_id=project_id, type=payload.type, super_area=payload.super_area,
    )
    db.add(cfg)
    db.flush()
    db.add(Price(
        configuration_id=cfg.id, base_price=payload.base_price, price_unit=payload.price_unit,
        plc=payload.plc, gst_percent=payload.gst_percent,
        effective_from=date.today(), source=payload.source, created_by=admin.id,
    ))
    if payload.total_units is not None or payload.available_units is not None:
        db.add(Inventory(
            configuration_id=cfg.id, total_units=payload.total_units,
            available_units=payload.available_units,
        ))
    record_audit(db, user_id=admin.id, action="CREATE", entity="configurations",
                 entity_id=cfg.id, after=payload.model_dump(mode="json"))
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"configuration_id": cfg.id, "message": f"Added {payload.type} with price + inventory."}


@router.get("/projects/{project_id}/configurations")
def list_configurations(
    project_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))
):
    """List a project's configurations with their CURRENT price + inventory (for editing)."""
    get_scoped_project(db, project_id, admin)
    configs = db.query(Configuration).filter(Configuration.project_id == project_id).all()
    out = []
    for cfg in configs:
        price = (
            db.query(Price)
            .filter(
                Price.configuration_id == cfg.id,
                Price.payment_plan_id.is_(None),  # the BASE price (plan overrides listed separately)
                or_(Price.effective_to.is_(None), Price.effective_to >= date.today()),
            )
            .order_by(Price.effective_from.desc())
            .first()
        )
        inv = db.query(Inventory).filter(Inventory.configuration_id == cfg.id).first()

        # Per-payment-plan price overrides (latest open row per plan).
        plan_rows = (
            db.query(Price, PaymentPlan.name)
            .join(PaymentPlan, PaymentPlan.id == Price.payment_plan_id)
            .filter(Price.configuration_id == cfg.id, Price.effective_to.is_(None))
            .order_by(Price.effective_from.desc())
            .all()
        )
        plan_prices, seen = [], set()
        for p, pname in plan_rows:
            if p.payment_plan_id in seen:
                continue
            seen.add(p.payment_plan_id)
            plan_prices.append({
                "payment_plan_id": p.payment_plan_id, "plan": pname,
                "base_price": float(p.base_price), "price_unit": p.price_unit,
            })

        out.append({
            "id": cfg.id, "type": cfg.type,
            "size": float(cfg.super_area) if cfg.super_area else None,
            "current_price": {
                "base_price": float(price.base_price), "price_unit": price.price_unit,
                "plc": float(price.plc) if price.plc else None,
                "gst_percent": float(price.gst_percent) if price.gst_percent else None,
                "effective_from": price.effective_from.isoformat() if price.effective_from else None,
                "source": price.source,
            } if price else None,
            "plan_prices": plan_prices,
            "inventory": {
                "total_units": inv.total_units, "available_units": inv.available_units,
            } if inv else None,
        })
    return out


class PriceUpdateIn(BaseModel):
    base_price: float
    price_unit: str = "per_sqft"
    plc: float | None = None
    gst_percent: float | None = None
    source: str | None = None
    # None = the base price (applies to all plans). Set to a payment plan id to
    # give that plan its own price (real estate — price varies by payment plan).
    payment_plan_id: int | None = None


@router.put("/configurations/{config_id}/price")
def update_price(
    config_id: int, payload: PriceUpdateIn,
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """Update a configuration's price WITHOUT losing history. Scoped to a single
    payment plan (or the base price when payment_plan_id is None): closes the
    currently-open price(s) for that plan and inserts a new current row."""
    cfg = db.get(Configuration, config_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    get_scoped_project(db, cfg.project_id, admin)

    plan_name = "base"
    if payload.payment_plan_id is not None:
        pp = db.get(PaymentPlan, payload.payment_plan_id)
        if not pp or pp.project_id != cfg.project_id:
            raise HTTPException(422, "Invalid payment plan for this configuration's project")
        plan_name = pp.name

    # Close any still-open price rows FOR THIS PLAN (or base) so the new one wins.
    q = db.query(Price).filter(
        Price.configuration_id == config_id, Price.effective_to.is_(None)
    )
    if payload.payment_plan_id is None:
        q = q.filter(Price.payment_plan_id.is_(None))
    else:
        q = q.filter(Price.payment_plan_id == payload.payment_plan_id)
    open_prices = q.all()
    old_snapshot = [
        {"base_price": float(p.base_price), "from": p.effective_from.isoformat() if p.effective_from else None}
        for p in open_prices
    ]
    for p in open_prices:
        p.effective_to = date.today()

    new = Price(
        configuration_id=config_id, payment_plan_id=payload.payment_plan_id,
        base_price=payload.base_price, price_unit=payload.price_unit,
        plc=payload.plc, gst_percent=payload.gst_percent, effective_from=date.today(),
        effective_to=None, source=payload.source or "Price update", created_by=admin.id,
    )
    db.add(new)
    db.flush()
    record_audit(db, user_id=admin.id, action="UPDATE", entity="prices", entity_id=new.id,
                 before={"previous_open_prices": old_snapshot},
                 after=payload.model_dump(mode="json"))
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"configuration_id": config_id, "new_price": payload.base_price, "plan": plan_name,
            "message": f"Price for '{plan_name}' updated to {payload.base_price} (previous price kept in history)."}


class InventoryUpdateIn(BaseModel):
    total_units: int | None = None
    available_units: int | None = None


@router.put("/configurations/{config_id}/inventory")
def update_inventory(
    config_id: int, payload: InventoryUpdateIn,
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    cfg = db.get(Configuration, config_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    get_scoped_project(db, cfg.project_id, admin)
    inv = db.query(Inventory).filter(Inventory.configuration_id == config_id).first()
    before = {"total": inv.total_units, "available": inv.available_units} if inv else None
    if not inv:
        inv = Inventory(configuration_id=config_id)
        db.add(inv)
    if payload.total_units is not None:
        inv.total_units = payload.total_units
    if payload.available_units is not None:
        inv.available_units = payload.available_units
    db.flush()
    record_audit(db, user_id=admin.id, action="UPDATE", entity="inventory", entity_id=inv.id,
                 before=before, after=payload.model_dump(mode="json"))
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"configuration_id": config_id, "message": "Inventory updated."}


@router.get("/projects/{project_id}/payment-plans")
def list_payment_plans(
    project_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """Active payment plans for a project (id + name) — used to attach per-plan
    prices in the price editor."""
    get_scoped_project(db, project_id, admin)
    plans = (
        db.query(PaymentPlan)
        .filter(PaymentPlan.project_id == project_id, PaymentPlan.is_active.is_(True))
        .order_by(PaymentPlan.name)
        .all()
    )
    return [
        {
            "id": p.id, "name": p.name, "description": p.description,
            "milestones": [{"label": m.label, "percent": float(m.percent)} for m in p.milestones],
        }
        for p in plans
    ]


@router.post("/projects/{project_id}/payment-plans", status_code=201)
def add_payment_plan(
    project_id: int, payload: PaymentPlanIn,
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    get_scoped_project(db, project_id, admin)
    total = sum(m.percent for m in payload.milestones)
    if round(total, 2) != 100.0:
        raise HTTPException(422, f"Milestone percents must sum to 100 (got {total}).")

    pp = PaymentPlan(project_id=project_id, name=payload.name, description=payload.description)
    db.add(pp)
    db.flush()
    for i, m in enumerate(payload.milestones):
        db.add(PaymentPlanMilestone(payment_plan_id=pp.id, sequence=i, label=m.label, percent=m.percent))
    record_audit(db, user_id=admin.id, action="CREATE", entity="payment_plans",
                 entity_id=pp.id, after=payload.model_dump(mode="json"))
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"payment_plan_id": pp.id, "message": f"Added payment plan '{payload.name}'."}


@router.put("/payment-plans/{plan_id}")
def update_payment_plan(
    plan_id: int, payload: PaymentPlanIn,
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    pp = db.get(PaymentPlan, plan_id)
    if not pp:
        raise HTTPException(404, "Payment plan not found")
    get_scoped_project(db, pp.project_id, admin)
    total = sum(m.percent for m in payload.milestones)
    if round(total, 2) != 100.0:
        raise HTTPException(422, f"Milestone percents must sum to 100 (got {total}).")

    pp.name = payload.name
    pp.description = payload.description
    # Replace the milestones wholesale (simplest correct edit for a small list).
    db.query(PaymentPlanMilestone).filter(PaymentPlanMilestone.payment_plan_id == pp.id).delete()
    db.flush()
    for i, m in enumerate(payload.milestones):
        db.add(PaymentPlanMilestone(payment_plan_id=pp.id, sequence=i, label=m.label, percent=m.percent))
    record_audit(db, user_id=admin.id, action="UPDATE", entity="payment_plans",
                 entity_id=pp.id, after=payload.model_dump(mode="json"))
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"payment_plan_id": pp.id, "message": f"Updated payment plan '{payload.name}'."}


@router.delete("/payment-plans/{plan_id}")
def delete_payment_plan(
    plan_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """Delete a payment plan. Any config prices tied ONLY to this plan are removed
    too (those configs simply fall back to their base price). Milestones cascade."""
    pp = db.get(PaymentPlan, plan_id)
    if not pp:
        raise HTTPException(404, "Payment plan not found")
    get_scoped_project(db, pp.project_id, admin)

    removed_prices = (
        db.query(Price).filter(Price.payment_plan_id == plan_id)
        .delete(synchronize_session=False)
    )
    record_audit(db, user_id=admin.id, action="DELETE", entity="payment_plans",
                 entity_id=plan_id, before={"name": pp.name, "removed_plan_prices": removed_prices})
    db.delete(pp)  # milestones cascade via ondelete
    db.commit()
    cache.bump_org(admin.organization_id)
    msg = f"Deleted payment plan '{pp.name}'."
    if removed_prices:
        msg += f" {removed_prices} plan-specific price(s) removed (those configs revert to base price)."
    return {"deleted": plan_id, "removed_plan_prices": removed_prices, "message": msg}


class ConfigDetailsIn(BaseModel):
    type: str
    super_area: float | None = None


@router.put("/configurations/{config_id}")
def update_configuration(
    config_id: int, payload: ConfigDetailsIn,
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """Edit a configuration's own details (type + size). Price and inventory have
    their own dedicated endpoints (they're versioned/audited separately)."""
    cfg = db.get(Configuration, config_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    get_scoped_project(db, cfg.project_id, admin)
    cfg.type = payload.type
    cfg.super_area = payload.super_area
    record_audit(db, user_id=admin.id, action="UPDATE", entity="configurations",
                 entity_id=config_id, after=payload.model_dump(mode="json"))
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"id": cfg.id, "type": cfg.type, "size": float(cfg.super_area) if cfg.super_area else None}


@router.delete("/configurations/{config_id}")
def delete_configuration(
    config_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    cfg = db.get(Configuration, config_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    get_scoped_project(db, cfg.project_id, admin)
    record_audit(db, user_id=admin.id, action="DELETE", entity="configurations",
                 entity_id=config_id, before={"type": cfg.type, "project_id": cfg.project_id})
    db.delete(cfg)
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"deleted": config_id}


@router.get("/projects/{project_id}/towers", response_model=list[TowerOut])
def list_towers(project_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    get_scoped_project(db, project_id, admin)
    return db.query(Tower).filter(Tower.project_id == project_id).order_by(Tower.name).all()


@router.post("/projects/{project_id}/towers", response_model=TowerOut, status_code=201)
def add_tower(project_id: int, payload: TowerIn, db: Session = Depends(get_db),
              admin: User = Depends(require_role("admin"))):
    get_scoped_project(db, project_id, admin)
    tower = Tower(project_id=project_id, **payload.model_dump())
    db.add(tower)
    db.flush()
    record_audit(db, user_id=admin.id, action="CREATE", entity="towers",
                 entity_id=tower.id, after=payload.model_dump())
    db.commit()
    cache.bump_org(admin.organization_id)
    db.refresh(tower)
    return tower


@router.put("/towers/{tower_id}", response_model=TowerOut)
def update_tower(tower_id: int, payload: TowerIn, db: Session = Depends(get_db),
                 admin: User = Depends(require_role("admin"))):
    tower = db.get(Tower, tower_id)
    if not tower:
        raise HTTPException(404, "Tower not found")
    get_scoped_project(db, tower.project_id, admin)
    for k, v in payload.model_dump().items():
        setattr(tower, k, v)
    record_audit(db, user_id=admin.id, action="UPDATE", entity="towers",
                 entity_id=tower_id, after=payload.model_dump())
    db.commit()
    cache.bump_org(admin.organization_id)
    db.refresh(tower)
    return tower


@router.delete("/towers/{tower_id}")
def delete_tower(tower_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    tower = db.get(Tower, tower_id)
    if not tower:
        raise HTTPException(404, "Tower not found")
    get_scoped_project(db, tower.project_id, admin)
    record_audit(db, user_id=admin.id, action="DELETE", entity="towers",
                 entity_id=tower_id, before={"name": tower.name})
    db.delete(tower)
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"deleted": tower_id}


@router.get("/projects/{project_id}/location", response_model=list[LocationPointOut])
def list_location(project_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    get_scoped_project(db, project_id, admin)
    return db.query(LocationPoint).filter(LocationPoint.project_id == project_id).all()


@router.post("/projects/{project_id}/location", response_model=LocationPointOut, status_code=201)
def add_location(project_id: int, payload: LocationPointIn, db: Session = Depends(get_db),
                 admin: User = Depends(require_role("admin"))):
    get_scoped_project(db, project_id, admin)
    lp = LocationPoint(project_id=project_id, **payload.model_dump())
    db.add(lp)
    db.flush()
    record_audit(db, user_id=admin.id, action="CREATE", entity="location_points",
                 entity_id=lp.id, after=payload.model_dump())
    db.commit()
    cache.bump_org(admin.organization_id)
    db.refresh(lp)
    return lp


@router.put("/location/{point_id}", response_model=LocationPointOut)
def update_location(point_id: int, payload: LocationPointIn, db: Session = Depends(get_db),
                    admin: User = Depends(require_role("admin"))):
    lp = db.get(LocationPoint, point_id)
    if not lp:
        raise HTTPException(404, "Location point not found")
    get_scoped_project(db, lp.project_id, admin)
    for k, v in payload.model_dump().items():
        setattr(lp, k, v)
    record_audit(db, user_id=admin.id, action="UPDATE", entity="location_points",
                 entity_id=point_id, after=payload.model_dump())
    db.commit()
    cache.bump_org(admin.organization_id)
    db.refresh(lp)
    return lp


@router.delete("/location/{point_id}")
def delete_location(point_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    lp = db.get(LocationPoint, point_id)
    if not lp:
        raise HTTPException(404, "Location point not found")
    get_scoped_project(db, lp.project_id, admin)
    record_audit(db, user_id=admin.id, action="DELETE", entity="location_points",
                 entity_id=point_id, before={"name": lp.name})
    db.delete(lp)
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"deleted": point_id}


# ---- Amenities (SQL-first; extracted once at import, then served from DB) ----
class AmenityIn(BaseModel):
    name: str
    category: str | None = None


@router.get("/projects/{project_id}/amenities")
def list_amenities(project_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    get_scoped_project(db, project_id, admin)
    rows = (
        db.query(Amenity).filter(Amenity.project_id == project_id)
        .order_by(Amenity.category, Amenity.name).all()
    )
    return [{"id": a.id, "name": a.name, "category": a.category} for a in rows]


@router.post("/projects/{project_id}/amenities", status_code=201)
def add_amenity(project_id: int, payload: AmenityIn, db: Session = Depends(get_db),
                admin: User = Depends(require_role("admin"))):
    get_scoped_project(db, project_id, admin)
    a = Amenity(project_id=project_id, name=payload.name, category=payload.category)
    db.add(a)
    db.flush()
    record_audit(db, user_id=admin.id, action="CREATE", entity="amenities",
                 entity_id=a.id, after=payload.model_dump())
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"id": a.id, "name": a.name, "category": a.category}


@router.put("/amenities/{amenity_id}")
def update_amenity(amenity_id: int, payload: AmenityIn, db: Session = Depends(get_db),
                   admin: User = Depends(require_role("admin"))):
    a = db.get(Amenity, amenity_id)
    if not a:
        raise HTTPException(404, "Amenity not found")
    get_scoped_project(db, a.project_id, admin)
    a.name = payload.name
    a.category = payload.category
    record_audit(db, user_id=admin.id, action="UPDATE", entity="amenities",
                 entity_id=amenity_id, after=payload.model_dump())
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"id": a.id, "name": a.name, "category": a.category}


@router.delete("/amenities/{amenity_id}")
def delete_amenity(amenity_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    a = db.get(Amenity, amenity_id)
    if not a:
        raise HTTPException(404, "Amenity not found")
    get_scoped_project(db, a.project_id, admin)
    record_audit(db, user_id=admin.id, action="DELETE", entity="amenities",
                 entity_id=amenity_id, before={"name": a.name})
    db.delete(a)
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"deleted": amenity_id}


class BuilderIn(BaseModel):
    name: str
    rera_id: str | None = None


@router.get("/builders")
def list_builders(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    bq = db.query(Builder)
    if not admin.is_super_admin and admin.organization_id:
        bq = bq.filter(Builder.organization_id == admin.organization_id)
    return [
        {"id": b.id, "name": b.name, "rera_id": b.rera_id,
         "projects": db.query(Project).filter(Project.builder_id == b.id).count()}
        for b in bq.order_by(Builder.name).all()
    ]


@router.post("/builders", status_code=201)
def create_builder(
    payload: BuilderIn, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))
):
    b = Builder(name=payload.name, rera_id=payload.rera_id, organization_id=admin.organization_id)
    db.add(b)
    db.flush()
    record_audit(db, user_id=admin.id, action="CREATE", entity="builders",
                 entity_id=b.id, after=payload.model_dump())
    db.commit()
    return {"id": b.id, "name": b.name}


@router.delete("/builders/{builder_id}")
def delete_builder(builder_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    b = db.get(Builder, builder_id)
    if not b or (not admin.is_super_admin and b.organization_id != admin.organization_id):
        raise HTTPException(404, "Developer not found")
    in_use = db.query(Project).filter(Project.builder_id == builder_id).count()
    if in_use:
        raise HTTPException(409, f"Cannot delete — {in_use} project(s) use this developer. Reassign them first.")
    record_audit(db, user_id=admin.id, action="DELETE", entity="builders",
                 entity_id=builder_id, before={"name": b.name})
    db.delete(b)
    db.commit()
    return {"deleted": builder_id}


class DocTypesIn(BaseModel):
    types: list[str]


@router.get("/document-types")
def get_document_types(db: Session = Depends(get_db), user: User = Depends(require_role("manager"))):
    row = db.get(Setting, _DOCTYPES_KEY)
    types = row.value.get("types") if row and row.value else None
    return {"types": types or DEFAULT_DOC_TYPES}


@router.put("/document-types")
def set_document_types(
    payload: DocTypesIn, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))
):
    cleaned = [t.strip() for t in payload.types if t.strip()]
    row = db.get(Setting, _DOCTYPES_KEY)
    if row:
        row.value = {"types": cleaned}
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(row, "value")
    else:
        db.add(Setting(key=_DOCTYPES_KEY, value={"types": cleaned}))
    record_audit(db, user_id=admin.id, action="UPDATE", entity="settings",
                 entity_id=None, after={"document_types": cleaned})
    db.commit()
    return {"types": cleaned}


@router.post("/import/projects-csv")
def import_projects_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """Bulk-create projects from a CSV (export from Excel as CSV).
    Columns: name, slug, city, locality, project_status, possession_date (YYYY-MM-DD)."""
    raw = file.file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    created, skipped, errors = 0, 0, []
    for i, row in enumerate(reader, start=2):
        try:
            slug = (row.get("slug") or "").strip()
            name = (row.get("name") or "").strip()
            if not slug or not name:
                errors.append(f"Row {i}: missing name/slug")
                continue
            # Scoped: an unscoped check reported "skipped existing" for a project
            # this company had never seen, just because another tenant had the slug.
            if (
                db.query(Project)
                .filter(Project.slug == slug, Project.organization_id == admin.organization_id)
                .first()
            ):
                skipped += 1
                continue
            poss = (row.get("possession_date") or "").strip()
            db.add(Project(
                name=name, slug=slug, organization_id=admin.organization_id,
                city=row.get("city"), locality=row.get("locality"),
                project_status=row.get("project_status") or None,
                possession_date=date.fromisoformat(poss) if poss else None,
            ))
            created += 1
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")
    record_audit(db, user_id=admin.id, action="CREATE", entity="projects",
                 entity_id=None, after={"import_created": created, "skipped": skipped})
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"created": created, "skipped_existing": skipped, "errors": errors}


# ----------------------- Project packs (export / import) -------------------
# A CSV row makes a project SHELL. A pack carries the whole knowledge tree —
# configurations, prices, payment plans, towers, amenities — which is what the
# engine actually answers from. See services/packs.py.
def _ids_param(ids: str | None) -> list[int] | None:
    if not ids:
        return None
    out = []
    for part in ids.split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out or None


@router.get("/export/projects.json")
def export_projects_json(
    ids: str | None = None,
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """Download this company's projects, with everything under them, as one file."""
    pack = packs.export_org(db, admin.organization_id, _ids_param(ids))
    pack["exported_at"] = datetime.now(timezone.utc).isoformat()
    org = db.get(Organization, admin.organization_id) if admin.organization_id else None
    pack["exported_from"] = org.name if org else None
    fname = f"projects-{(org.slug if org else 'export')}-{date.today().isoformat()}.json"
    return Response(
        content=json.dumps(pack, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.post("/import/projects-json")
def import_projects_json(
    file: UploadFile = File(...),
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """Load a pack into THIS company. Projects it already has (by slug) are
    skipped rather than merged — an import must never quietly rewrite live prices."""
    try:
        pack = json.loads(file.file.read().decode("utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise HTTPException(422, f"That file isn't valid JSON: {exc}") from exc
    try:
        result = packs.import_pack(db, admin.organization_id, pack)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    record_audit(db, user_id=admin.id, action="CREATE", entity="projects", entity_id=None,
                 after={"pack_created": result["created"], "skipped": result["skipped_existing"]})
    db.commit()
    cache.bump_org(admin.organization_id)
    return result


@router.get("/export/projects.csv")
def export_projects_csv(
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """The flat project list for Excel. Round-trips with the CSV import — but it
    is a shell: prices and plans need the JSON pack."""
    rows = (
        db.query(Project).filter(Project.organization_id == admin.organization_id)
        .order_by(Project.name).all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "slug", "city", "locality", "project_status", "possession_date"])
    for p in rows:
        w.writerow([p.name, p.slug, p.city or "", p.locality or "",
                    p.project_status or "", p.possession_date or ""])
    org = db.get(Organization, admin.organization_id) if admin.organization_id else None
    fname = f"projects-{(org.slug if org else 'export')}-{date.today().isoformat()}.csv"
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
