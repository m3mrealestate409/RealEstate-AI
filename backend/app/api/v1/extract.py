"""
AI-assisted data entry (admin only).

  POST /v1/admin/extract                 → PDF in, structured DRAFT out (no save)
  POST /v1/admin/projects/{id}/apply     → save a reviewed draft into SQL

The draft is always reviewed/edited by a human before `apply` writes anything,
so the SQL source of truth stays human-verified (Constitution §5, §8).
"""
import tempfile
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import require_role
from app.core.tenancy import get_scoped_project
from app.database import get_db
from app.models import (
    Amenity,
    Configuration,
    Inventory,
    LocationPoint,
    PaymentPlan,
    PaymentPlanMilestone,
    Price,
    Tower,
    User,
)
from app.services import cache, extract

router = APIRouter(prefix="/v1/admin", tags=["ai-import"])


def _pdf_text(path: str) -> str:
    import fitz

    parts = []
    with fitz.open(path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n".join(parts)


@router.post("/extract")
def extract_draft(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Read a brochure PDF and return an editable draft (nothing is saved)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        text = _pdf_text(tmp_path)
    except Exception as exc:
        raise HTTPException(422, f"Could not read PDF: {exc}")
    if not text.strip():
        raise HTTPException(422, "No extractable text in this PDF (scanned image?).")

    result = extract.extract_fields(text)
    if "error" in result:
        raise HTTPException(502, result["error"])
    return result  # {"draft": {...}}


# ---- Apply a reviewed draft to SQL ----------------------------------------
class MilestoneDraft(BaseModel):
    label: str
    percent: float


class PaymentPlanDraft(BaseModel):
    name: str | None = None
    milestones: list[MilestoneDraft] = []


class ConfigDraft(BaseModel):
    type: str
    super_area: float | None = None   # shown to users as "Size"
    base_price: float | None = None
    price_unit: str | None = "per_sqft"
    plc: float | None = None
    gst_percent: float | None = None
    total_units: int | None = None
    available_units: int | None = None


class TowerDraft(BaseModel):
    name: str
    floors: int | None = None
    height: str | None = None
    units_per_floor: int | None = None


class LocationDraft(BaseModel):
    category: str = "nearby"
    name: str
    distance: str | None = None
    notes: str | None = None


class AmenityDraft(BaseModel):
    name: str
    category: str | None = None


class ApplyDraft(BaseModel):
    project_type: str | None = None
    land_parcel: str | None = None
    green_area: str | None = None
    project_status: str | None = None
    possession_date: str | None = None
    towers: list[TowerDraft] = []
    configurations: list[ConfigDraft] = []
    payment_plan: PaymentPlanDraft | None = None
    location_points: list[LocationDraft] = []
    amenities: list[AmenityDraft] = []


@router.post("/projects/{project_id}/apply")
def apply_draft(
    project_id: int,
    payload: ApplyDraft,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Write the reviewed draft into SQL (additive). Returns a summary."""
    project = get_scoped_project(db, project_id, admin)
    summary = {"fields": 0, "towers": 0, "configurations": 0, "payment_plan": False,
               "location_points": 0, "amenities": 0}

    # Project-level attributes (only the ones provided).
    for attr in ("project_type", "land_parcel", "green_area", "project_status"):
        val = getattr(payload, attr)
        if val:
            setattr(project, attr, val)
            summary["fields"] += 1
    if payload.possession_date:
        try:
            project.possession_date = date.fromisoformat(payload.possession_date)
            summary["fields"] += 1
        except ValueError:
            pass

    for t in payload.towers:
        if not t.name:
            continue
        db.add(Tower(project_id=project_id, name=t.name, floors=t.floors,
                     height=t.height, units_per_floor=t.units_per_floor))
        summary["towers"] += 1

    for c in payload.configurations:
        if not c.type:
            continue
        cfg = Configuration(project_id=project_id, type=c.type, super_area=c.super_area)
        db.add(cfg)
        db.flush()
        if c.base_price is not None:
            db.add(Price(configuration_id=cfg.id, base_price=c.base_price,
                        price_unit=c.price_unit or "per_sqft", plc=c.plc,
                        gst_percent=c.gst_percent, effective_from=date.today(),
                        source="AI extract (reviewed)", created_by=admin.id))
        if c.total_units is not None or c.available_units is not None:
            db.add(Inventory(configuration_id=cfg.id, total_units=c.total_units,
                            available_units=c.available_units))
        summary["configurations"] += 1

    for lp in payload.location_points:
        if not lp.name:
            continue
        db.add(LocationPoint(project_id=project_id, category=lp.category or "nearby",
                            name=lp.name, distance=lp.distance, notes=lp.notes))
        summary["location_points"] += 1

    for am in payload.amenities:
        if not am.name:
            continue
        db.add(Amenity(project_id=project_id, name=am.name, category=am.category))
        summary["amenities"] += 1

    pp = payload.payment_plan
    if pp and pp.milestones:
        plan = PaymentPlan(project_id=project_id, name=pp.name or "Payment Plan")
        db.add(plan)
        db.flush()
        for i, m in enumerate(pp.milestones):
            db.add(PaymentPlanMilestone(payment_plan_id=plan.id, sequence=i,
                                        label=m.label, percent=m.percent))
        summary["payment_plan"] = True

    record_audit(db, user_id=admin.id, action="CREATE", entity="ai_extract",
                 entity_id=project_id, after=summary)
    db.commit()
    cache.bump_org(admin.organization_id)
    return {"applied": summary, "message": "Saved to project."}
