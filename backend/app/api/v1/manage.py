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
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import require_role
from app.database import get_db
from app.models import (
    Builder,
    Configuration,
    Inventory,
    PaymentPlan,
    PaymentPlanMilestone,
    Price,
    Project,
    Setting,
    User,
)

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
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")

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
    return {"configuration_id": cfg.id, "message": f"Added {payload.type} with price + inventory."}


@router.post("/projects/{project_id}/payment-plans", status_code=201)
def add_payment_plan(
    project_id: int, payload: PaymentPlanIn,
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
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
    return {"payment_plan_id": pp.id, "message": f"Added payment plan '{payload.name}'."}


@router.delete("/configurations/{config_id}")
def delete_configuration(
    config_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    cfg = db.get(Configuration, config_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    record_audit(db, user_id=admin.id, action="DELETE", entity="configurations",
                 entity_id=config_id, before={"type": cfg.type, "project_id": cfg.project_id})
    db.delete(cfg)
    db.commit()
    return {"deleted": config_id}


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
                name=name, slug=slug, city=row.get("city"), locality=row.get("locality"),
                project_status=row.get("project_status") or None,
                possession_date=date.fromisoformat(poss) if poss else None,
            ))
            created += 1
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")
    record_audit(db, user_id=admin.id, action="CREATE", entity="projects",
                 entity_id=None, after={"import_created": created, "skipped": skipped})
    db.commit()
    return {"created": created, "skipped_existing": skipped, "errors": errors}
