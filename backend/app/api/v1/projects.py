"""Read endpoints for projects and their structured facts (org-scoped)."""
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.core.tenancy import apply_viewing_tenant, get_scoped_project, scope_by_org
from app.database import get_db
from app.models import Document, LocationPoint, Project, Tower, User
from app.schemas import LocationPointOut, ProjectOut, TowerOut
from app.services import database_service as dbsvc

router = APIRouter(prefix="/v1/projects", tags=["projects"])


def _safe_filename(name: str) -> str:
    """Strip CR/LF/quote/backslash so a doc title can't inject an HTTP response
    header or break out of the Content-Disposition filename token."""
    return re.sub(r'[\r\n"\\]+', " ", (name or "")).strip() or "file"


def _latest_doc(db: Session, project_id: int, doc_type: str) -> Document | None:
    """The most recently uploaded/replaced document of a type for a project.
    `uploaded_at` is refreshed on upload AND replace, so the newest file wins."""
    return (
        db.query(Document)
        .filter(Document.project_id == project_id, Document.doc_type == doc_type)
        .order_by(Document.uploaded_at.desc(), Document.version.desc())
        .first()
    )


def _doc_info(db: Session, project_id: int, doc_type: str, user: User) -> dict:
    get_scoped_project(db, project_id, user)
    doc = _latest_doc(db, project_id, doc_type)
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        return {"available": False}
    return {
        "available": True, "title": doc.title, "version": doc.version,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
    }


def _doc_file(db: Session, project_id: int, doc_type: str, user: User, label: str):
    get_scoped_project(db, project_id, user)
    doc = _latest_doc(db, project_id, doc_type)
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(404, f"No {label} available for this project")
    return FileResponse(
        doc.file_path, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{_safe_filename(doc.title or label)}.pdf"'},
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(
    request: Request,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    apply_viewing_tenant(request, user)  # super-admin viewing one tenant → scope to it
    query = scope_by_org(db.query(Project), Project, user)
    if q:
        query = query.filter(Project.name.ilike(f"%{q}%"))
    return query.order_by(Project.name).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_scoped_project(db, project_id, user)


@router.get("/{project_id}/price")
def project_price(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_scoped_project(db, project_id, user)
    return dbsvc.current_price(db, project_id)


@router.get("/{project_id}/payment-plan")
def project_payment_plan(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_scoped_project(db, project_id, user)
    return dbsvc.payment_plans(db, project_id)


@router.get("/{project_id}/inventory")
def project_inventory(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_scoped_project(db, project_id, user)
    return dbsvc.inventory(db, project_id)


@router.get("/{project_id}/status")
def project_status(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_scoped_project(db, project_id, user)
    return dbsvc.status(db, project_id)


@router.get("/{project_id}/towers", response_model=list[TowerOut])
def project_towers(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_scoped_project(db, project_id, user)
    return db.query(Tower).filter(Tower.project_id == project_id).order_by(Tower.name).all()


@router.get("/{project_id}/location", response_model=list[LocationPointOut])
def project_location(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_scoped_project(db, project_id, user)
    return db.query(LocationPoint).filter(LocationPoint.project_id == project_id).all()


@router.get("/{project_id}/amenities")
def project_amenities(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_scoped_project(db, project_id, user)
    return dbsvc.amenities(db, project_id)


@router.get("/{project_id}/brochure/info")
def brochure_info(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _doc_info(db, project_id, "brochure", user)


@router.get("/{project_id}/brochure")
def view_brochure(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _doc_file(db, project_id, "brochure", user, "brochure")


@router.get("/{project_id}/site-plan/info")
def site_plan_info(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _doc_info(db, project_id, "site_plan", user)


@router.get("/{project_id}/site-plan")
def view_site_plan(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _doc_file(db, project_id, "site_plan", user, "site plan")


@router.get("/{project_id}/cost-sheet/info")
def cost_sheet_info(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _doc_info(db, project_id, "cost_sheet", user)


@router.get("/{project_id}/cost-sheet")
def view_cost_sheet(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _doc_file(db, project_id, "cost_sheet", user, "cost sheet")


@router.get("/{project_id}/cost-sheets")
def list_cost_sheets(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """All cost sheets for a project (id + title) — for the download dropdown."""
    get_scoped_project(db, project_id, user)
    docs = (
        db.query(Document)
        .filter(Document.project_id == project_id, Document.doc_type == "cost_sheet")
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return [
        {"id": d.id, "title": d.title, "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None}
        for d in docs if d.file_path and os.path.exists(d.file_path)
    ]


@router.get("/{project_id}/cost-sheets/{doc_id}")
def view_cost_sheet_by_id(
    project_id: int, doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    get_scoped_project(db, project_id, user)
    doc = db.get(Document, doc_id)
    if (not doc or doc.project_id != project_id or doc.doc_type != "cost_sheet"
            or not doc.file_path or not os.path.exists(doc.file_path)):
        raise HTTPException(404, "Cost sheet not found")
    return FileResponse(
        doc.file_path, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{_safe_filename(doc.title or "cost sheet")}.pdf"'},
    )
