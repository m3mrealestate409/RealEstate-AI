"""
New-chat notification config (org admin).

- GET  /v1/admin/notify-config       → current provider + settings
- PUT  /v1/admin/notify-config       → save provider + settings
- POST /v1/admin/notify-config/test  → send a test notification with the saved config
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import require_role
from app.database import get_db
from app.models import Organization, User
from app.services import notify

router = APIRouter(tags=["notify"])

VALID_PROVIDERS = {"off", "telegram", "webhook"}


class NotifyCfgIn(BaseModel):
    provider: str = "off"
    config: dict | None = None


@router.get("/v1/admin/notify-config")
def get_notify_config(admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    org = db.get(Organization, admin.organization_id) if admin.organization_id else None
    return {
        "provider": (org.notify_provider if org else "off") or "off",
        "config": (org.notify_config if org else None) or {},
    }


@router.put("/v1/admin/notify-config")
def set_notify_config(
    payload: NotifyCfgIn, admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)
):
    if payload.provider not in VALID_PROVIDERS:
        raise HTTPException(422, f"provider must be one of {sorted(VALID_PROVIDERS)}")
    if not admin.organization_id:
        raise HTTPException(400, "No organization")
    org = db.get(Organization, admin.organization_id)
    org.notify_provider = payload.provider
    org.notify_config = payload.config or {}
    record_audit(db, user_id=admin.id, action="UPDATE", entity="organizations",
                 entity_id=org.id, after={"notify_provider": org.notify_provider})
    db.commit()
    return {"provider": org.notify_provider, "config": org.notify_config}


@router.post("/v1/admin/notify-config/test")
def test_notify_config(admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    org = db.get(Organization, admin.organization_id) if admin.organization_id else None
    if not org or (org.notify_provider or "off") == "off":
        raise HTTPException(400, "Notifications are off. Choose a provider and save first.")
    ok, detail = notify.send(
        org.notify_provider, org.notify_config,
        "✅ Test notification from your AI assistant. New-visitor alerts will look like this.",
    )
    if not ok:
        raise HTTPException(400, f"Test failed: {detail}")
    return {"ok": True, "detail": detail}
