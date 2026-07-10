"""
Admin endpoints — data management, document upload/index, audit trail.
All mutations require 'admin' role and are audit-logged (Constitution §19).
"""
import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import require_role
from app.core.tenancy import get_scoped_project
from app.database import get_db
from app.models import Document, Project, User
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.services import cache
from app.services.rag.ingest import ingest_document

router = APIRouter(prefix="/v1/admin", tags=["admin"])

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    if db.query(Project).filter(Project.slug == payload.slug).first():
        raise HTTPException(409, "slug already exists")
    project = Project(**payload.model_dump(), organization_id=admin.organization_id)
    db.add(project)
    db.flush()
    record_audit(db, user_id=admin.id, action="CREATE", entity="projects",
                 entity_id=project.id, after=payload.model_dump(mode="json"))
    db.commit()
    cache.bump_org(admin.organization_id)
    db.refresh(project)
    return project


@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    project = get_scoped_project(db, project_id, admin)

    before = {c.name: getattr(project, c.name) for c in project.__table__.columns}
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(project, k, v)
    db.flush()
    record_audit(
        db, user_id=admin.id, action="UPDATE", entity="projects", entity_id=project.id,
        before={k: str(before.get(k)) for k in changes},
        after={k: str(v) for k, v in changes.items()},
    )
    db.commit()
    cache.bump_org(admin.organization_id)
    db.refresh(project)
    return project


@router.post("/documents", status_code=201)
def upload_document(
    project_id: int = Form(...),
    title: str = Form(...),
    doc_type: str = Form("brochure"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Upload a brochure/legal PDF and index it into the RAG store."""
    project = get_scoped_project(db, project_id, admin)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = f"{project_id}_{datetime.now(timezone.utc).timestamp()}_{file.filename}"
    dest = os.path.join(UPLOAD_DIR, safe_name)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    document = Document(
        project_id=project_id, title=title, doc_type=doc_type, file_path=dest,
        version=1, status="processing",
    )
    db.add(document)
    db.flush()
    record_audit(db, user_id=admin.id, action="CREATE", entity="documents",
                 entity_id=document.id, after={"title": title, "doc_type": doc_type})
    db.commit()

    try:
        chunks = ingest_document(db, document)
    except Exception as exc:  # PDF parse / embedding failure
        document.status = "failed"
        db.commit()
        raise HTTPException(500, f"Indexing failed: {exc}")

    cache.bump_org(admin.organization_id)
    return {"document_id": document.id, "chunks_indexed": chunks, "title": title}


@router.get("/audit")
def list_audit(
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    from app.models import AuditLog

    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "action": r.action,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
