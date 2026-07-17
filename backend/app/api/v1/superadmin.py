"""
Super-admin console (platform owner only). Manage tenant organizations and
subscription plans — create companies, assign/change their plan, edit plan
limits, and see per-tenant usage. All endpoints require is_super_admin.
"""
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import hash_password, require_super_admin
from app.database import get_db
from app.models import Organization, Plan, QueryLog, User
from app.services import billing

router = APIRouter(prefix="/v1/superadmin", tags=["superadmin"])


# ---------------------------- Plans ---------------------------------------
class PlanIn(BaseModel):
    name: str
    max_employees: int = 5
    daily_llm_quota: int = 25
    price_monthly: float = 0


@router.get("/plans")
def list_plans(db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    return [
        {"id": p.id, "name": p.name, "max_employees": p.max_employees,
         "daily_llm_quota": p.daily_llm_quota, "price_monthly": float(p.price_monthly),
         "is_active": p.is_active,
         "organizations": db.query(func.count(Organization.id)).filter(Organization.plan_id == p.id).scalar()}
        for p in db.query(Plan).order_by(Plan.price_monthly).all()
    ]


@router.post("/plans", status_code=201)
def create_plan(payload: PlanIn, db: Session = Depends(get_db), admin: User = Depends(require_super_admin)):
    if db.query(Plan).filter(Plan.name == payload.name).first():
        raise HTTPException(409, "A plan with that name already exists")
    plan = Plan(**payload.model_dump())
    db.add(plan)
    db.flush()
    record_audit(db, user_id=admin.id, action="CREATE", entity="plans", entity_id=plan.id,
                 after=payload.model_dump(mode="json"))
    db.commit()
    return {"id": plan.id, "name": plan.name}


class PlanUpdate(BaseModel):
    max_employees: int | None = None
    daily_llm_quota: int | None = None
    price_monthly: float | None = None
    is_active: bool | None = None


@router.put("/plans/{plan_id}")
def update_plan(plan_id: int, payload: PlanUpdate, db: Session = Depends(get_db),
                admin: User = Depends(require_super_admin)):
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(plan, k, v)
    record_audit(db, user_id=admin.id, action="UPDATE", entity="plans", entity_id=plan.id,
                 after={k: str(v) for k, v in changes.items()})
    db.commit()
    return {"id": plan.id, "updated": list(changes.keys())}


# ------------------------- Organizations ----------------------------------
class OrgIn(BaseModel):
    name: str
    slug: str
    plan_id: int
    admin_email: str
    admin_password: str
    admin_name: str | None = None
    # False when the deal is already signed — starts them active for 30 days.
    trial: bool = True


@router.get("/organizations")
def list_orgs(db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    out = []
    for org in db.query(Organization).order_by(Organization.created_at.desc()).all():
        emp = db.query(func.count(User.id)).filter(
            User.organization_id == org.id, User.is_active.is_(True)
        ).scalar() or 0
        used_today = db.query(func.count(QueryLog.id)).filter(
            QueryLog.organization_id == org.id, func.date(QueryLog.created_at) == date.today()
        ).scalar() or 0
        sub = org.subscription
        ent = billing.entitlements(db, org)
        expires = billing.expires_at(sub)
        out.append({
            "id": org.id, "name": org.name, "slug": org.slug, "is_active": org.is_active,
            "plan": org.plan.name if org.plan else None,
            "plan_id": org.plan_id,
            "max_employees": ent.max_employees,
            "employees": emp,
            "daily_llm_quota": ent.daily_llm_quota,
            "queries_today": used_today,
            # Billing — what the platform owner chases people about.
            "status": ent.status,
            "set_status": sub.status if sub else None,
            "expires_at": expires.isoformat() if expires else None,
            "days_left": billing.days_left(sub),
            "note": sub.note if sub else None,
            "price_monthly": float(org.plan.price_monthly) if org.plan else None,
            "grace_days": billing.GRACE_DAYS,
        })
    return out


@router.post("/organizations", status_code=201)
def create_org(payload: OrgIn, db: Session = Depends(get_db), admin: User = Depends(require_super_admin)):
    if db.query(Organization).filter(Organization.slug == payload.slug).first():
        raise HTTPException(409, "slug already exists")
    if db.query(User).filter(User.email == payload.admin_email).first():
        raise HTTPException(409, "admin email already exists")
    if not db.get(Plan, payload.plan_id):
        raise HTTPException(422, "plan not found")

    org = Organization(name=payload.name, slug=payload.slug, plan_id=payload.plan_id)
    db.add(org)
    db.flush()
    db.add(User(
        email=payload.admin_email, name=payload.admin_name or "Org Admin", role="admin",
        password_hash=hash_password(payload.admin_password), organization_id=org.id,
    ))
    # Every tenant starts on a trial, so its billing state is never undefined.
    sub = billing.ensure_subscription(db, org, trial=payload.trial)
    record_audit(db, user_id=admin.id, action="CREATE", entity="organizations", entity_id=org.id,
                 after={"name": payload.name, "plan_id": payload.plan_id, "status": sub.status})
    db.commit()
    return {"id": org.id, "name": org.name, "admin": payload.admin_email}


class OrgUpdate(BaseModel):
    plan_id: int | None = None
    is_active: bool | None = None


@router.put("/organizations/{org_id}")
def update_org(org_id: int, payload: OrgUpdate, db: Session = Depends(get_db),
               admin: User = Depends(require_super_admin)):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    changes = payload.model_dump(exclude_unset=True)
    if "plan_id" in changes and not db.get(Plan, changes["plan_id"]):
        raise HTTPException(422, "plan not found")
    for k, v in changes.items():
        setattr(org, k, v)
    record_audit(db, user_id=admin.id, action="UPDATE", entity="organizations", entity_id=org.id,
                 after={k: str(v) for k, v in changes.items()})
    db.commit()
    return {"id": org.id, "updated": list(changes.keys())}


# ------------------------- Subscriptions ----------------------------------
# Phase 1 is billed by hand: money arrives by bank transfer / UPI and the
# platform owner records it here. No provider, no webhooks, no card on file.
class SubscriptionIn(BaseModel):
    # trialing | active | suspended | cancelled ("past_due" is derived, never set)
    status: str | None = None
    # Paid up to, as YYYY-MM-DD. Setting it implies the money arrived.
    paid_till: date | None = None
    trial_days: int | None = None
    plan_id: int | None = None
    note: str | None = None


def _sub_out(db: Session, org: Organization) -> dict:
    sub = org.subscription
    expires = billing.expires_at(sub)
    return {
        "organization_id": org.id, "name": org.name,
        "plan": org.plan.name if org.plan else None, "plan_id": org.plan_id,
        "status": billing.effective_status(sub),
        "set_status": sub.status if sub else None,
        "expires_at": expires.isoformat() if expires else None,
        "days_left": billing.days_left(sub),
        "note": sub.note if sub else None,
    }


@router.put("/organizations/{org_id}/subscription")
def set_subscription(org_id: int, payload: SubscriptionIn, db: Session = Depends(get_db),
                     admin: User = Depends(require_super_admin)):
    """Record what really happened with the money. Marking `paid_till` is the
    common case — it activates the org and clears any grace/suspension."""
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    sub = billing.ensure_subscription(db, org)

    if payload.plan_id is not None:
        if not db.get(Plan, payload.plan_id):
            raise HTTPException(422, "plan not found")
        org.plan_id = payload.plan_id
        sub.plan_id = payload.plan_id

    if payload.paid_till is not None:
        # Store end-of-day so "paid till the 30th" includes the 30th.
        sub.current_period_end = datetime.combine(
            payload.paid_till, time.max, tzinfo=timezone.utc
        )
        sub.status = "active"
        sub.trial_ends_at = None

    if payload.trial_days is not None:
        if payload.trial_days < 1:
            raise HTTPException(422, "trial_days must be at least 1")
        sub.status = "trialing"
        sub.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=payload.trial_days)

    if payload.status is not None:
        s = payload.status.lower()
        if s not in billing.SETTABLE:
            raise HTTPException(422, f"status must be one of {sorted(billing.SETTABLE)}")
        sub.status = s

    if payload.note is not None:
        sub.note = payload.note.strip() or None

    record_audit(db, user_id=admin.id, action="UPDATE", entity="subscriptions",
                 entity_id=sub.id, after={
                     "org": org.name, "status": sub.status,
                     "paid_till": str(payload.paid_till) if payload.paid_till else None,
                     "note": sub.note,
                 })
    db.commit()
    db.refresh(org)
    return _sub_out(db, org)
