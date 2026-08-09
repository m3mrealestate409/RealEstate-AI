"""User management (org admin). Create sales/manager accounts within the org,
enforce the plan's employee cap, toggle active. Scoped to the caller's org."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import hash_password, require_role
from app.core.tenancy import apply_viewing_tenant, org_scope_id, scope_by_org
from app.database import get_db
from app.models import Organization, User
from app.schemas import UserOut
from app.services import billing

router = APIRouter(prefix="/v1/admin/users", tags=["users"])

# Who may create whom:
#   super-admin  → organizations, each with its one admin (see superadmin.py)
#   org admin    → managers and sales, inside their own company
# An admin account is therefore provisioned WITH the tenant, never self-served.
# That keeps "who owns this company" a decision we make, not one an employee can
# grant themselves — and since role is only ever set at creation (there is no
# change-role endpoint), closing this closes the whole path.
ROLES = ["sales", "manager", "admin"]
ORG_ROLES = ["sales", "manager"]


class UserCreate(BaseModel):
    email: str
    name: str | None = None
    role: str = "sales"
    tier: str = "basic"           # basic | advanced (daily query limit)
    password: str


TIERS = ["basic", "advanced"]


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    return scope_by_org(db.query(User), User, admin).order_by(User.created_at.desc()).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    request: Request, payload: UserCreate, db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    allowed = ROLES if admin.is_super_admin else ORG_ROLES
    if payload.role not in allowed:
        if payload.role == "admin":
            raise HTTPException(
                403,
                "Admin accounts are set up with the organization itself, not from here. "
                "Contact us to add another admin to your company.",
            )
        raise HTTPException(422, f"role must be one of {allowed}")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(409, "email already exists")

    # Resolve the org this user belongs to: a tenant admin → their own org; a
    # super-admin → the tenant they've opened (Platform → View data). Refuse if
    # none is open, so we never mint an org-less account that org_scope_id would
    # otherwise treat as "see every tenant".
    apply_viewing_tenant(request, admin)
    oid = org_scope_id(admin)
    if oid is None:
        raise HTTPException(400, "Open a company first (Platform → View data), then add its user.")

    # Enforce the plan's employee cap (super-admins are exempt). The cap comes
    # from billing, not the plan directly, so payment state is resolved in one
    # place — see services/billing.py.
    if not admin.is_super_admin and admin.organization_id:
        # Serialize the cap check + insert per org with a transaction-scoped
        # advisory lock. Without it, count()+INSERT is a TOCTOU race: concurrent
        # requests all read the same count before any commits and blow past the
        # cap (proven: 6 parallel creates put 10 users on a 5-seat plan). The
        # lock (namespace 742, org id) is released automatically at commit.
        db.execute(
            text("SELECT pg_advisory_xact_lock(742, :org)"),
            {"org": admin.organization_id},
        )
        org = db.get(Organization, admin.organization_id)
        ent = billing.entitlements(db, org)
        cap = ent.max_employees
        current = db.query(User).filter(
            User.organization_id == admin.organization_id, User.is_active.is_(True)
        ).count()
        if cap is not None and current >= cap:
            raise HTTPException(
                403,
                f"Employee limit reached for your '{ent.plan_name}' plan ({cap} users). "
                "Upgrade the plan to add more employees.",
            )

    tier = payload.tier if payload.tier in TIERS else "basic"
    user = User(
        email=payload.email, name=payload.name, role=payload.role, tier=tier,
        password_hash=hash_password(payload.password),
        organization_id=oid,
    )
    db.add(user)
    db.flush()
    record_audit(db, user_id=admin.id, action="CREATE", entity="users",
                 entity_id=user.id, after={"email": payload.email, "role": payload.role})
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/toggle", response_model=UserOut)
def toggle_active(
    user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    user = db.get(User, user_id)
    if not user or (not admin.is_super_admin and user.organization_id != admin.organization_id):
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "You cannot deactivate yourself.")
    user.is_active = not user.is_active
    record_audit(db, user_id=admin.id, action="UPDATE", entity="users",
                 entity_id=user.id, after={"is_active": user.is_active})
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/livechat", response_model=UserOut)
def toggle_live_chat(
    user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    """Grant/revoke this employee's access to the Live Chat console."""
    user = db.get(User, user_id)
    if not user or (not admin.is_super_admin and user.organization_id != admin.organization_id):
        raise HTTPException(404, "User not found")
    user.can_live_chat = not user.can_live_chat
    record_audit(db, user_id=admin.id, action="UPDATE", entity="users",
                 entity_id=user.id, after={"can_live_chat": user.can_live_chat})
    db.commit()
    db.refresh(user)
    return user


class TierUpdate(BaseModel):
    tier: str


@router.post("/{user_id}/tier", response_model=UserOut)
def set_tier(user_id: int, payload: TierUpdate, db: Session = Depends(get_db),
             admin: User = Depends(require_role("admin"))):
    if payload.tier not in TIERS:
        raise HTTPException(422, f"tier must be one of {TIERS}")
    user = db.get(User, user_id)
    if not user or (not admin.is_super_admin and user.organization_id != admin.organization_id):
        raise HTTPException(404, "User not found")
    user.tier = payload.tier
    record_audit(db, user_id=admin.id, action="UPDATE", entity="users",
                 entity_id=user.id, after={"tier": payload.tier})
    db.commit()
    db.refresh(user)
    return user


# ---- Per-tier daily query limits (org-admin configures for their company) ----
class TierLimitsIn(BaseModel):
    basic_daily_limit: int | None = None
    advanced_daily_limit: int | None = None


@router.get("/tier-limits")
def get_tier_limits(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    if not admin.organization_id:
        return {"basic_daily_limit": None, "advanced_daily_limit": None}
    org = db.get(Organization, admin.organization_id)
    return {"basic_daily_limit": org.basic_daily_limit, "advanced_daily_limit": org.advanced_daily_limit}


@router.put("/tier-limits")
def set_tier_limits(payload: TierLimitsIn, db: Session = Depends(get_db),
                    admin: User = Depends(require_role("admin"))):
    if not admin.organization_id:
        raise HTTPException(400, "No organization")
    org = db.get(Organization, admin.organization_id)
    if payload.basic_daily_limit is not None:
        org.basic_daily_limit = payload.basic_daily_limit
    if payload.advanced_daily_limit is not None:
        org.advanced_daily_limit = payload.advanced_daily_limit
    record_audit(db, user_id=admin.id, action="UPDATE", entity="organizations",
                 entity_id=org.id, after=payload.model_dump(exclude_none=True))
    db.commit()
    return {"basic_daily_limit": org.basic_daily_limit, "advanced_daily_limit": org.advanced_daily_limit}
