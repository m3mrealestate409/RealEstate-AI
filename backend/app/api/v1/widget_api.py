"""
Chat-widget configuration.

- GET  /v1/widget/config        → used by the embedded widget (auth: API key or JWT)
- GET  /v1/admin/widget-config  → org admin reads their greeting
- PUT  /v1/admin/widget-config  → org admin edits their greeting
"""
import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import get_current_user, require_role
from app.core.uploads import save_image_upload
from app.database import get_db
from app.models import Organization, User

router = APIRouter(tags=["widget"])

DEFAULT_GREETING = "Hi! 👋 Ask me about our projects — price, payment plan, or amenities."
DEFAULT_NAME = "Assistant"

# app/api/v1/widget_api.py → app/static/avatars
_AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "avatars")


@router.get("/v1/widget/config")
def widget_config(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The widget calls this (with its API key) for the org's greeting + identity."""
    org = db.get(Organization, user.organization_id) if user.organization_id else None
    greeting = (org.widget_greeting if org and org.widget_greeting else "") or DEFAULT_GREETING
    return {
        "greeting": greeting,
        "name": (org.assistant_name if org and org.assistant_name else "") or DEFAULT_NAME,
        "avatar_url": (org.assistant_avatar if org else None),
    }


class WidgetCfgIn(BaseModel):
    greeting: str | None = None


@router.get("/v1/admin/widget-config")
def get_widget_config(admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    org = db.get(Organization, admin.organization_id) if admin.organization_id else None
    return {"greeting": (org.widget_greeting if org else None), "default": DEFAULT_GREETING}


@router.put("/v1/admin/widget-config")
def set_widget_config(
    payload: WidgetCfgIn, admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)
):
    if not admin.organization_id:
        raise HTTPException(400, "No organization")
    org = db.get(Organization, admin.organization_id)
    org.widget_greeting = (payload.greeting or "").strip() or None
    record_audit(db, user_id=admin.id, action="UPDATE", entity="organizations",
                 entity_id=org.id, after={"widget_greeting": org.widget_greeting})
    db.commit()
    return {"greeting": org.widget_greeting or DEFAULT_GREETING}


# ---- Assistant persona (org-wide, applied to every channel) ----------------
PERSONA_HINT = (
    "You are Riya, a warm and helpful sales advisor for our real-estate company. "
    "Speak in a friendly, professional tone and match the customer's language (English/Hindi/Hinglish). "
    "Keep replies short and encourage them to explore projects or book a site visit."
)


class PersonaIn(BaseModel):
    persona: str | None = None
    name: str | None = None


@router.get("/v1/admin/assistant-config")
def get_assistant_config(admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    org = db.get(Organization, admin.organization_id) if admin.organization_id else None
    return {
        "persona": (org.assistant_persona if org else None),
        "name": (org.assistant_name if org else None),
        "avatar_url": (org.assistant_avatar if org else None),
        "hint": PERSONA_HINT,
        "name_hint": "Riya",
    }


@router.put("/v1/admin/assistant-config")
def set_assistant_config(
    payload: PersonaIn, admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)
):
    if not admin.organization_id:
        raise HTTPException(400, "No organization")
    org = db.get(Organization, admin.organization_id)
    org.assistant_persona = (payload.persona or "").strip() or None
    if payload.name is not None:
        org.assistant_name = (payload.name or "").strip()[:40] or None
    record_audit(db, user_id=admin.id, action="UPDATE", entity="organizations",
                 entity_id=org.id, after={"assistant_persona_set": bool(org.assistant_persona),
                                          "assistant_name": org.assistant_name})
    db.commit()
    return {"persona": org.assistant_persona, "name": org.assistant_name}


@router.post("/v1/admin/assistant-avatar")
def upload_assistant_avatar(
    file: UploadFile = File(...),
    admin: User = Depends(require_role("admin")), db: Session = Depends(get_db),
):
    if not admin.organization_id:
        raise HTTPException(400, "No organization")
    org = db.get(Organization, admin.organization_id)
    dest = save_image_upload(file, _AVATAR_DIR, prefix=f"org{org.id}")
    # Remove the previous avatar file so old images don't pile up on disk.
    old = org.assistant_avatar
    org.assistant_avatar = "/static/avatars/" + os.path.basename(dest)
    db.commit()
    if old:
        old_path = os.path.join(_AVATAR_DIR, os.path.basename(old))
        try:
            if os.path.exists(old_path):
                os.unlink(old_path)
        except OSError:
            pass
    return {"avatar_url": org.assistant_avatar}


@router.delete("/v1/admin/assistant-avatar")
def delete_assistant_avatar(admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    if not admin.organization_id:
        raise HTTPException(400, "No organization")
    org = db.get(Organization, admin.organization_id)
    old = org.assistant_avatar
    org.assistant_avatar = None
    db.commit()
    if old:
        try:
            p = os.path.join(_AVATAR_DIR, os.path.basename(old))
            if os.path.exists(p):
                os.unlink(p)
        except OSError:
            pass
    return {"avatar_url": None}
