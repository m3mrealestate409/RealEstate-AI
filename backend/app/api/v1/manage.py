"""
Data management (admin) — add/edit the structured facts behind a project:
configurations (+ current price + inventory) and payment plans. Plus CSV bulk
import for projects. All mutations are audited (§19).
"""
import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import require_role
from app.core.tenancy import get_scoped_project
from app.database import get_db
from app.services import cache
from app.models import (
    Builder,
    Configuration,
    Inventory,
    PaymentPlan,
    PaymentPlanMilestone,
    Price,
    Project,
    Setting,
    Tower,
    User,
)
from app.schemas import TowerIn, TowerOut

router = APIRouter(prefix="/v1/admin", tags=["data-management"])

DEFAULT_DOC_TYPES = ["brochure", "legal", "floor_plan", "master_plan", "price_list"]
_DOCTYPES_KEY = "document_types"


class ConfigurationIn(BaseModel):
    type: str
    carpet_area: float | None = None
    super_area: float | None = None
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
        project_id=project_id, type=payload.type,
        carpet_area=payload.carpet_area, super_area=payload.super_area,
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
                or_(Price.effective_to.is_(None), Price.effective_to >= date.today()),
            )
            .order_by(Price.effective_from.desc())
            .first()
        )
        inv = db.query(Inventory).filter(Inventory.configuration_id == cfg.id).first()
        out.append({
            "id": cfg.id, "type": cfg.type,
            "carpet_area": float(cfg.carpet_area) if cfg.carpet_area else None,
            "super_area": float(cfg.super_area) if cfg.super_area else None,
            "current_price": {
                "base_price": float(price.base_price), "price_unit": price.price_unit,
                "plc": float(price.plc) if price.plc else None,
                "gst_percent": float(price.gst_percent) if price.gst_percent else None,
                "effective_from": price.effective_from.isoformat() if price.effective_from else None,
                "source": price.source,
            } if price else None,
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


@router.put("/configurations/{config_id}/price")
def update_price(
    config_id: int, payload: PriceUpdateIn,
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """Update a configuration's price WITHOUT losing history.
    Closes the currently-open price(s) as of today and inserts a new current row."""
    cfg = db.get(Configuration, config_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    get_scoped_project(db, cfg.project_id, admin)

    # Close any still-open price rows so the new one becomes current.
    open_prices = db.query(Price).filter(
        Price.configuration_id == config_id, Price.effective_to.is_(None)
    ).all()
    old_snapshot = [{"base_price": float(p.base_price), "from": p.effective_from.isoformat()} for p in open_prices]
    for p in open_prices:
        p.effective_to = date.today()

    new = Price(
        configuration_id=config_id, base_price=payload.base_price, price_unit=payload.price_unit,
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
    return {"configuration_id": config_id, "new_price": payload.base_price,
            "message": f"Price updated to {payload.base_price} (previous price kept in history)."}


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


class BuilderIn(BaseModel):
    name: str
    rera_id: str | None = None


@router.get("/builders")
def list_builders(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    return [
        {"id": b.id, "name": b.name, "rera_id": b.rera_id,
         "projects": db.query(Project).filter(Project.builder_id == b.id).count()}
        for b in db.query(Builder).order_by(Builder.name).all()
    ]


@router.post("/builders", status_code=201)
def create_builder(
    payload: BuilderIn, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))
):
    b = Builder(name=payload.name, rera_id=payload.rera_id)
    db.add(b)
    db.flush()
    record_audit(db, user_id=admin.id, action="CREATE", entity="builders",
                 entity_id=b.id, after=payload.model_dump())
    db.commit()
    return {"id": b.id, "name": b.name}


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
            if db.query(Project).filter(Project.slug == slug).first():
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
