"""
API keys for external integrations (CRM, WhatsApp, voice agent, other sites).

An org admin creates a key for their organization. The full key is returned
ONCE at creation (only its hash + prefix are stored). A request made with the
key (header `X-API-Key`) acts as the admin who created it, so all tenant scoping
and org data isolation still apply.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import hash_api_key, require_role
from app.database import get_db
from app.models import ApiKey, User

router = APIRouter(prefix="/v1/admin/api-keys", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    name: str


def _out(k: ApiKey) -> dict:
    return {
        "id": k.id,
        "name": k.name,
        "prefix": k.prefix,
        "is_active": k.is_active,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }


@router.get("")
def list_keys(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    q = db.query(ApiKey)
    if not admin.is_super_admin:
        q = q.filter(ApiKey.organization_id == admin.organization_id)
    return [_out(k) for k in q.order_by(ApiKey.created_at.desc()).all()]


@router.post("", status_code=201)
def create_key(
    payload: ApiKeyCreate, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))
):
    raw = "px_" + secrets.token_urlsafe(32)   # the full key — shown once
    key = ApiKey(
        organization_id=admin.organization_id,
        name=payload.name.strip() or "Integration",
        prefix=raw[:11],
        key_hash=hash_api_key(raw),
        created_by=admin.id,
    )
    db.add(key)
    db.flush()
    record_audit(db, user_id=admin.id, action="CREATE", entity="api_keys",
                 entity_id=key.id, after={"name": key.name})
    db.commit()
    return {
        "id": key.id, "name": key.name, "api_key": raw,
        "note": "Save this key now — it will not be shown again.",
    }


@router.delete("/{key_id}")
def revoke_key(key_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    key = db.get(ApiKey, key_id)
    if not key or (not admin.is_super_admin and key.organization_id != admin.organization_id):
        raise HTTPException(404, "API key not found")
    record_audit(db, user_id=admin.id, action="DELETE", entity="api_keys",
                 entity_id=key.id, before={"name": key.name})
    db.delete(key)
    db.commit()
    return {"revoked": key_id}
