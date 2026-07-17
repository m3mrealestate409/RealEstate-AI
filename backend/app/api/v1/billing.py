"""
Billing, as the tenant sees it (read-only).

An org admin may look at their plan, what it entitles them to, how much of it
they have used today, and when it runs out. They cannot change any of it —
Phase 1 takes money by hand, so only a super-admin records payment. This
endpoint exists so nobody has to ask us "am I still paid up?".
"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.database import get_db
from app.models import Organization, User
from app.services import billing, quota

router = APIRouter(prefix="/v1/billing", tags=["billing"])


@router.get("/me")
def my_billing(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    org = db.get(Organization, admin.organization_id) if admin.organization_id else None
    out = billing.summary(db, org)
    if org is None:
        return out
    out["employees"] = db.query(func.count(User.id)).filter(
        User.organization_id == org.id, User.is_active.is_(True)
    ).scalar() or 0
    out["queries_today"] = quota.org_used_today(org.id, date.today().isoformat())
    return out
