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
from app.models import Organization, Plan, Project, QueryLog, Subscription, User
from app.services import billing, cache, notify, orgpurge, packs

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
    orgs = (db.query(Organization)
              .filter(Organization.deleted_at.is_(None))   # tombstones stay hidden
              .order_by(Organization.created_at.desc()).all())
    for org in orgs:
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
            # An upgrade the tenant asked for — Phase 1 has no self-serve
            # checkout, so this is the platform owner's to-do.
            "requested_plan": sub.requested_plan.name if sub and sub.requested_plan else None,
            "requested_plan_id": sub.requested_plan_id if sub else None,
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


# --------------------------- Deleting a tenant -----------------------------
# Two levels, because they answer different problems:
#   - Deactivate (PUT is_active=false) — reversible. Staff can't log in, the
#     widget and API keys stop, but every byte of data is still there.
#   - Delete (below) — irreversible. Wipes the tenant's data but KEEPS its
#     payment history, so the org row survives as a tombstone.
@router.get("/organizations/{org_id}/delete-preview")
def delete_org_preview(org_id: int, db: Session = Depends(get_db),
                       _: User = Depends(require_super_admin)):
    """Exact counts of what a delete would destroy — so the confirmation dialog
    states facts instead of a vague warning."""
    org = db.get(Organization, org_id)
    if not org or org.deleted_at is not None:
        raise HTTPException(404, "Organization not found")
    return {"id": org.id, "name": org.name, **orgpurge.preview(db, org)}


class OrgDeleteIn(BaseModel):
    # Must match the company name exactly. A destructive, irreversible action
    # should not be one stray click away.
    confirm_name: str


@router.post("/organizations/{org_id}/delete")
def delete_org(org_id: int, payload: OrgDeleteIn, db: Session = Depends(get_db),
               admin: User = Depends(require_super_admin)):
    org = db.get(Organization, org_id)
    if not org or org.deleted_at is not None:
        raise HTTPException(404, "Organization not found")
    if payload.confirm_name.strip() != org.name.strip():
        raise HTTPException(400, "The typed name does not match the company name.")

    name = org.name
    removed = orgpurge.purge(db, org)
    # Logged against the platform owner, so it survives the tenant's own audit
    # rows being deleted — this is the record that the company ever existed.
    record_audit(db, user_id=admin.id, action="DELETE", entity="organizations",
                 entity_id=org_id, before={"name": name}, after=removed)
    db.commit()
    return {"deleted": True, "name": name, "removed": removed}


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
    # The payment itself. Recorded as a permanent row, because `paid_till` gets
    # overwritten by the next renewal and would otherwise lose the history.
    amount: float | None = None
    method: str | None = None        # bank | upi | cash | card | other
    reference: str | None = None     # UPI ref / UTR
    # Drop a pending plan-change request without acting on it (they declined,
    # or it was handled off-system). Changing the plan clears it anyway.
    clear_request: bool = False


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
        "requested_plan": sub.requested_plan.name if sub and sub.requested_plan else None,
        "requested_plan_id": sub.requested_plan_id if sub else None,
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

    if payload.method is not None and payload.method.lower() not in billing.METHODS:
        raise HTTPException(422, f"method must be one of {sorted(billing.METHODS)}")

    if payload.plan_id is not None:
        if not db.get(Plan, payload.plan_id):
            raise HTTPException(422, "plan not found")
        org.plan_id = payload.plan_id
        sub.plan_id = payload.plan_id
        # Whatever they asked for, this answers it.
        sub.requested_plan_id = None
        sub.requested_at = None
        db.flush()
        db.refresh(org)

    payment = None
    if payload.paid_till is not None:
        # The period this money covers: from where they were paid up to (or
        # today for a first payment) to the new date.
        prev_end = billing.paid_until(sub)
        period_start = prev_end.date() if prev_end and prev_end.date() < payload.paid_till else date.today()

        # Store end-of-day so "paid till the 30th" includes the 30th.
        sub.current_period_end = datetime.combine(
            payload.paid_till, time.max, tzinfo=timezone.utc
        )
        sub.status = "active"
        sub.trial_ends_at = None

        payment = billing.record_payment(
            db, org,
            amount=payload.amount if payload.amount is not None
            else float(org.plan.price_monthly or 0) if org.plan else 0,
            period_start=period_start, period_end=payload.paid_till,
            method=payload.method, reference=payload.reference,
            note=payload.note, recorded_by=admin.id,
        )

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

    if payload.clear_request:
        sub.requested_plan_id = None
        sub.requested_at = None

    record_audit(db, user_id=admin.id, action="UPDATE", entity="subscriptions",
                 entity_id=sub.id, after={
                     "org": org.name, "status": sub.status,
                     "paid_till": str(payload.paid_till) if payload.paid_till else None,
                     "note": sub.note,
                     "receipt_no": payment.receipt_no if payment else None,
                     "amount": float(payment.amount) if payment else None,
                 })
    db.commit()
    db.refresh(org)
    out = _sub_out(db, org)
    if payment is not None:
        out["payment"] = billing.payment_out(payment)
    return out


# --------------------- Platform-owner notifications ------------------------
# Separate from a tenant's own notify config: these go to US, not to them.
class PlatformNotifyIn(BaseModel):
    provider: str          # off | telegram | webhook
    config: dict | None = None


@router.get("/notify-config")
def get_platform_notify(db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    return notify.get_platform_config(db)


@router.put("/notify-config")
def set_platform_notify(payload: PlatformNotifyIn, db: Session = Depends(get_db),
                        admin: User = Depends(require_super_admin)):
    if payload.provider not in ("off", "telegram", "webhook"):
        raise HTTPException(422, "provider must be off, telegram or webhook")
    val = notify.set_platform_config(db, payload.provider, payload.config)
    # Never audit the config itself — it holds a bot token.
    record_audit(db, user_id=admin.id, action="UPDATE", entity="settings",
                 entity_id=None, after={"platform_notify_provider": val["provider"]})
    db.commit()
    return val


@router.post("/notify-config/test")
def test_platform_notify(db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    cfg = notify.get_platform_config(db)
    if cfg["provider"] == "off":
        raise HTTPException(422, "Turn notifications on and save first.")
    ok, detail = notify.send(cfg["provider"], cfg["config"],
                             "✅ PropX platform alerts are working — you'll get a ping here when a "
                             "tenant asks to change plan.")
    if not ok:
        raise HTTPException(400, detail)
    return {"ok": True, "detail": detail}


# ------------------- Seed a tenant with starter projects -------------------
class SeedIn(BaseModel):
    source_org_id: int
    project_ids: list[int] | None = None    # None = every project in the source


@router.get("/organizations/{org_id}/projects")
def org_projects(org_id: int, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    """What's in a company — so you can pick what to copy into a new one."""
    rows = (
        db.query(Project).filter(Project.organization_id == org_id)
        .order_by(Project.name).all()
    )
    return [{
        "id": p.id, "name": p.name, "slug": p.slug, "city": p.city,
        "configurations": len(p.configurations),
        "amenities": len(p.amenities),
    } for p in rows]


@router.post("/organizations/{org_id}/seed-projects")
def seed_projects(org_id: int, payload: SeedIn, db: Session = Depends(get_db),
                  admin: User = Depends(require_super_admin)):
    """Copy projects from one company into another, so a new tenant doesn't
    start with an assistant that knows nothing. Runs through the same pack code
    as the file export/import — one way to copy a project, not two."""
    target = db.get(Organization, org_id)
    if not target:
        raise HTTPException(404, "Organization not found")
    if payload.source_org_id == org_id:
        raise HTTPException(422, "Source and target are the same company.")
    if not db.get(Organization, payload.source_org_id):
        raise HTTPException(404, "Source organization not found")

    pack = packs.export_org(db, payload.source_org_id, payload.project_ids)
    result = packs.import_pack(db, org_id, pack)
    record_audit(db, user_id=admin.id, action="CREATE", entity="projects", entity_id=None,
                 after={"seeded_into": target.name, "from_org": payload.source_org_id,
                        "created": result["created"], "skipped": result["skipped_existing"]})
    db.commit()
    cache.bump_org(org_id)
    return result


@router.get("/requests")
def pending_requests(db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    """Tenants waiting on a plan change — the platform owner's to-do list.
    In-app and always correct, regardless of whether a ping got through."""
    rows = (
        db.query(Subscription).filter(Subscription.requested_plan_id.isnot(None))
        .order_by(Subscription.requested_at.desc()).all()
    )
    return [{
        "organization_id": s.organization_id,
        "name": s.organization.name if s.organization else None,
        "current_plan": s.plan.name if s.plan else None,
        "requested_plan": s.requested_plan.name if s.requested_plan else None,
        "requested_plan_id": s.requested_plan_id,
        "requested_at": s.requested_at.isoformat() if s.requested_at else None,
    } for s in rows]
