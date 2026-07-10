"""Read endpoints for projects and their structured facts (org-scoped)."""
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.core.tenancy import get_scoped_project, scope_by_org
from app.database import get_db
from app.models import Document, Project, User
from app.schemas import ProjectOut
from app.services import database_service as dbsvc

router = APIRouter(prefix="/v1/projects", tags=["projects"])


def _latest_brochure(db: Session, project_id: int) -> Document | None:
    """Most recent brochure document for a project (newest version first)."""
    return (
        db.query(Document)
        .filter(Document.project_id == project_id, Document.doc_type == "brochure")
        .order_by(Document.version.desc(), Document.uploaded_at.desc())
        .first()
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
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


@router.get("/{project_id}/brochure/info")
def brochure_info(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Whether this project has a viewable brochure + its metadata (for the UI)."""
    get_scoped_project(db, project_id, user)
    doc = _latest_brochure(db, project_id)
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        return {"available": False}
    return {
        "available": True,
        "title": doc.title,
        "version": doc.version,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
    }


@router.get("/{project_id}/brochure")
def view_brochure(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Stream the latest brochure PDF inline (org-scoped)."""
    get_scoped_project(db, project_id, user)
    doc = _latest_brochure(db, project_id)
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(404, "No brochure available for this project")
    return FileResponse(
        doc.file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{(doc.title or "brochure")}.pdf"'},
    )
