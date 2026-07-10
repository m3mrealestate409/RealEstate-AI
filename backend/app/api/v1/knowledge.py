"""
Knowledge / RAG monitoring + Documents management (admin/manager).

Gives visibility into the ingestion pipeline: how many chunks/embeddings exist,
which documents are processed / pending / failed, and coverage — so an admin can
confirm a brochure actually got indexed (or re-index / delete it).
"""
import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import require_role
from app.database import get_db
from app.models import Document, Project, RagChunk, User
from app.services.rag.ingest import ingest_document

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")

router = APIRouter(prefix="/v1/admin/knowledge", tags=["knowledge"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(require_role("manager"))):
    total_docs = db.query(func.count(Document.id)).scalar() or 0
    processed = db.query(func.count(Document.id)).filter(Document.status == "completed").scalar() or 0
    pending = db.query(func.count(Document.id)).filter(Document.status.in_(["pending", "processing"])).scalar() or 0
    failed = db.query(func.count(Document.id)).filter(Document.status == "failed").scalar() or 0
    total_chunks = db.query(func.count(RagChunk.id)).scalar() or 0
    active_chunks = db.query(func.count(RagChunk.id)).filter(RagChunk.is_active.is_(True)).scalar() or 0

    recent = (
        db.query(Document, Project.name)
        .join(Project, Project.id == Document.project_id)
        .order_by(Document.uploaded_at.desc())
        .limit(6).all()
    )
    recent_uploads = [
        {
            "title": doc.title, "project": pname, "status": doc.status,
            "created": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        }
        for doc, pname in recent
    ]

    return {
        "projects": db.query(func.count(Project.id)).scalar() or 0,
        "documents": total_docs,
        "chunks": total_chunks,
        "embeddings": active_chunks,
        "processed": processed,
        "pending": pending,
        "failed": failed,
        "coverage": round(processed / total_docs * 100, 1) if total_docs else 0.0,
        "recent_uploads": recent_uploads,
        "recent_jobs": [
            {"job": "full_pipeline", "status": u["status"], "started": u["created"]}
            for u in recent_uploads
        ],
    }


@router.get("/documents")
def list_documents(db: Session = Depends(get_db), user: User = Depends(require_role("manager"))):
    rows = (
        db.query(Document, Project.name)
        .join(Project, Project.id == Document.project_id)
        .order_by(Document.uploaded_at.desc()).all()
    )
    out = []
    for doc, pname in rows:
        chunks = db.query(func.count(RagChunk.id)).filter(
            RagChunk.document_id == doc.id, RagChunk.is_active.is_(True)
        ).scalar() or 0
        out.append({
            "id": doc.id, "title": doc.title, "project": pname, "doc_type": doc.doc_type,
            "status": doc.status, "chunks": chunks, "version": doc.version,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "indexed_at": doc.indexed_at.isoformat() if doc.indexed_at else None,
        })
    return out


@router.post("/documents/{doc_id}/reindex")
def reindex_document(
    doc_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))
):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.file_path:
        raise HTTPException(422, "Document has no stored file to re-index")
    doc.version = (doc.version or 1) + 1
    doc.status = "processing"
    db.commit()
    try:
        chunks = ingest_document(db, doc)
    except Exception as exc:
        doc.status = "failed"
        db.commit()
        raise HTTPException(500, f"Re-index failed: {exc}")
    record_audit(db, user_id=admin.id, action="UPDATE", entity="documents",
                 entity_id=doc.id, after={"reindexed": True, "version": doc.version})
    db.commit()
    return {"document_id": doc.id, "chunks_indexed": chunks, "version": doc.version}


@router.post("/reindex-all")
def reindex_all(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    """Re-embed every document with the CURRENT embedding provider. Run this
    after switching embeddings (e.g. mock → Gemini) so all chunks match."""
    docs = db.query(Document).filter(Document.file_path.isnot(None)).all()
    done, failed, total_chunks = 0, [], 0
    for doc in docs:
        try:
            doc.status = "processing"
            db.commit()
            total_chunks += ingest_document(db, doc)
            done += 1
        except Exception as exc:
            doc.status = "failed"
            db.commit()
            failed.append({"id": doc.id, "title": doc.title, "error": str(exc)[:120]})
    record_audit(db, user_id=admin.id, action="UPDATE", entity="documents",
                 entity_id=None, after={"reindexed_all": done, "failed": len(failed)})
    db.commit()
    return {"reindexed": done, "chunks": total_chunks, "failed": failed}


@router.post("/documents/{doc_id}/replace")
def replace_document(
    doc_id: int,
    title: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Replace a document with a NEW file. The old brochure's chunks are
    deactivated during re-index, so RAG never serves the outdated version
    (Constitution §6 — frequently-changing info must not stay in RAG)."""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = f"{doc.project_id}_v{(doc.version or 1) + 1}_{datetime.now(timezone.utc).timestamp()}_{file.filename}"
    dest = os.path.join(UPLOAD_DIR, safe_name)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    old_file = doc.file_path
    doc.file_path = dest
    doc.version = (doc.version or 1) + 1
    doc.status = "processing"
    if title:
        doc.title = title
    db.commit()

    try:
        # ingest_document deactivates the old chunks, then indexes the new file.
        chunks = ingest_document(db, doc)
    except Exception as exc:
        doc.status = "failed"
        db.commit()
        raise HTTPException(500, f"Re-index of new file failed: {exc}")

    record_audit(db, user_id=admin.id, action="UPDATE", entity="documents", entity_id=doc.id,
                 before={"old_file": old_file}, after={"new_file": dest, "version": doc.version})
    db.commit()
    return {"document_id": doc.id, "version": doc.version, "chunks_indexed": chunks,
            "message": "Brochure replaced; old content deactivated."}


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))
):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    record_audit(db, user_id=admin.id, action="DELETE", entity="documents",
                 entity_id=doc.id, before={"title": doc.title})
    db.delete(doc)  # cascade removes its rag_chunks
    db.commit()
    return {"deleted": doc_id}
