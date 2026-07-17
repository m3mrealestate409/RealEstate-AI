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


CHANNELS = {"website", "internal"}
SCOPES = {"full", "read_only", "widget"}


class ApiKeyCreate(BaseModel):
    name: str
    # "website" = public chat widget (live chat, new-visitor alerts, auto-leads)
    # "internal" = CRM / back-office tool (no alerts, no live chat, trusted limits)
    channel: str = "website"
    # "full" = acts as its admin creator; "read_only" = may ask questions and
    # read, but can never modify anything (least privilege for integrations);
    # "widget" = only the public chat widget's own calls (safe to embed in a page).
    scope: str = "full"


def _out(k: ApiKey) -> dict:
    return {
        "id": k.id,
        "name": k.name,
        "channel": (k.channel or "website"),
        "scope": (k.scope or "full"),
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
    channel = (payload.channel or "website").lower()
    if channel not in CHANNELS:
        raise HTTPException(422, f"channel must be one of {sorted(CHANNELS)}")
    scope = (payload.scope or "full").lower()
    if scope not in SCOPES:
        raise HTTPException(422, f"scope must be one of {sorted(SCOPES)}")
    raw = "px_" + secrets.token_urlsafe(32)   # the full key — shown once
    key = ApiKey(
        organization_id=admin.organization_id,
        name=payload.name.strip() or "Integration",
        channel=channel,
        scope=scope,
        prefix=raw[:11],
        key_hash=hash_api_key(raw),
        created_by=admin.id,
    )
    db.add(key)
    db.flush()
    record_audit(db, user_id=admin.id, action="CREATE", entity="api_keys",
                 entity_id=key.id, after={"name": key.name, "channel": channel, "scope": scope})
    db.commit()
    return {
        "id": key.id, "name": key.name, "channel": key.channel, "scope": key.scope,
        "api_key": raw, "note": "Save this key now — it will not be shown again.",
    }


class ScopeIn(BaseModel):
    scope: str


@router.post("/{key_id}/scope")
def set_scope(
    key_id: int, payload: ScopeIn,
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """Tighten (or restore) what a key may do — e.g. make a CRM key read-only."""
    scope = (payload.scope or "").lower()
    if scope not in SCOPES:
        raise HTTPException(422, f"scope must be one of {sorted(SCOPES)}")
    key = db.get(ApiKey, key_id)
    if not key or (not admin.is_super_admin and key.organization_id != admin.organization_id):
        raise HTTPException(404, "API key not found")
    key.scope = scope
    record_audit(db, user_id=admin.id, action="UPDATE", entity="api_keys",
                 entity_id=key.id, after={"scope": scope})
    db.commit()
    return _out(key)


class ChannelIn(BaseModel):
    channel: str


@router.post("/{key_id}/channel")
def set_channel(
    key_id: int, payload: ChannelIn,
    db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """Switch what a key is plugged into — e.g. flip an existing CRM key from
    'website' to 'internal' so it stops raising new-visitor alerts."""
    channel = (payload.channel or "").lower()
    if channel not in CHANNELS:
        raise HTTPException(422, f"channel must be one of {sorted(CHANNELS)}")
    key = db.get(ApiKey, key_id)
    if not key or (not admin.is_super_admin and key.organization_id != admin.organization_id):
        raise HTTPException(404, "API key not found")
    key.channel = channel
    record_audit(db, user_id=admin.id, action="UPDATE", entity="api_keys",
                 entity_id=key.id, after={"channel": channel})
    db.commit()
    return _out(key)


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
