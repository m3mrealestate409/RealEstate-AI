"""
Lead capture — the chatbot's business payoff.

A conversation on any channel (website widget, CRM, WhatsApp) can drop a lead
here. Leads are org-scoped and, if the org has configured a CRM webhook, are
pushed to it in real time (best-effort, non-blocking).

- POST  /v1/leads              → capture a lead (auth: API key or JWT)
- GET   /v1/admin/leads        → org admin/manager lists leads
- PATCH /v1/admin/leads/{id}   → update a lead's status
- GET   /v1/admin/crm-config   → read the CRM webhook URL
- PUT   /v1/admin/crm-config   → set the CRM webhook URL
"""
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import get_current_user, require_role
from app.core.tenancy import org_scope_id
from app.database import get_db
from app.models import Lead, Organization, User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["leads"])

VALID_STATUS = {"new", "contacted", "qualified", "closed"}


def _push_to_crm(url: str, payload: dict) -> None:
    """Fire the lead at the org's CRM webhook. Best-effort: a CRM that is down
    must never break lead capture, so all errors are swallowed (just logged)."""
    try:
        httpx.post(url, json=payload, timeout=8.0)
    except Exception as exc:  # noqa: BLE001 — deliberately non-fatal
        logger.warning("CRM webhook push failed for %s: %s", url, exc)


class LeadIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    message: str | None = None
    project_interest: str | None = None
    source: str = "widget"
    page_url: str | None = None
    session_id: str | None = None


@router.post("/v1/leads")
def capture_lead(
    payload: LeadIn,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Capture a lead from any channel. The API key (or JWT) identifies the org."""
    if not (payload.phone or payload.email):
        raise HTTPException(422, "A phone number or email is required.")

    org_id = org_scope_id(user)
    lead = Lead(
        organization_id=org_id,
        name=(payload.name or "").strip() or None,
        phone=(payload.phone or "").strip() or None,
        email=(payload.email or "").strip() or None,
        message=(payload.message or "").strip() or None,
        project_interest=(payload.project_interest or "").strip() or None,
        source=(payload.source or "widget").strip() or "widget",
        page_url=(payload.page_url or "").strip() or None,
        session_id=(payload.session_id or "").strip() or None,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    # Push to the org's CRM webhook if one is configured (non-blocking).
    org = db.get(Organization, org_id) if org_id else None
    if org and org.crm_webhook_url:
        background.add_task(_push_to_crm, org.crm_webhook_url, {
            "id": lead.id, "name": lead.name, "phone": lead.phone, "email": lead.email,
            "message": lead.message, "project_interest": lead.project_interest,
            "source": lead.source, "page_url": lead.page_url,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
        })

    return {"ok": True, "id": lead.id}


@router.get("/v1/admin/leads")
def list_leads(
    user: User = Depends(require_role("manager")), db: Session = Depends(get_db)
):
    org_id = org_scope_id(user)
    q = db.query(Lead)
    if org_id is not None:
        q = q.filter(Lead.organization_id == org_id)
    rows = q.order_by(Lead.created_at.desc()).limit(500).all()
    return [
        {
            "id": r.id, "name": r.name, "phone": r.phone, "email": r.email,
            "message": r.message, "project_interest": r.project_interest,
            "source": r.source, "status": r.status, "page_url": r.page_url,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


class LeadStatusIn(BaseModel):
    status: str


@router.patch("/v1/admin/leads/{lead_id}")
def update_lead(
    lead_id: int, payload: LeadStatusIn,
    user: User = Depends(require_role("manager")), db: Session = Depends(get_db),
):
    if payload.status not in VALID_STATUS:
        raise HTTPException(422, f"status must be one of {sorted(VALID_STATUS)}")
    org_id = org_scope_id(user)
    lead = db.get(Lead, lead_id)
    if not lead or (org_id is not None and lead.organization_id != org_id):
        raise HTTPException(404, "Lead not found")
    lead.status = payload.status
    db.commit()
    return {"ok": True, "id": lead.id, "status": lead.status}


# ---- CRM webhook config (org admin) ----------------------------------------
class CrmCfgIn(BaseModel):
    crm_webhook_url: str | None = None


@router.get("/v1/admin/crm-config")
def get_crm_config(admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    org = db.get(Organization, admin.organization_id) if admin.organization_id else None
    return {"crm_webhook_url": (org.crm_webhook_url if org else None)}


@router.put("/v1/admin/crm-config")
def set_crm_config(
    payload: CrmCfgIn, admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)
):
    if not admin.organization_id:
        raise HTTPException(400, "No organization")
    url = (payload.crm_webhook_url or "").strip() or None
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(422, "Webhook URL must start with http:// or https://")
    org = db.get(Organization, admin.organization_id)
    org.crm_webhook_url = url
    record_audit(db, user_id=admin.id, action="UPDATE", entity="organizations",
                 entity_id=org.id, after={"crm_webhook_url_set": bool(url)})
    db.commit()
    return {"crm_webhook_url": org.crm_webhook_url}
