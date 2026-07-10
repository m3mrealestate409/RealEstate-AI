"""Read endpoints for projects and their structured facts (org-scoped)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.core.tenancy import get_scoped_project, scope_by_org
from app.database import get_db
from app.models import Project, User
from app.schemas import ProjectOut
from app.services import database_service as dbsvc

router = APIRouter(prefix="/v1/projects", tags=["projects"])


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
