"""User management (org admin). Create sales/manager accounts within the org,
enforce the plan's employee cap, toggle active. Scoped to the caller's org."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import hash_password, require_role
from app.core.tenancy import scope_by_org
from app.database import get_db
from app.models import Organization, User
from app.schemas import UserOut

router = APIRouter(prefix="/v1/admin/users", tags=["users"])

ROLES = ["sales", "manager", "admin"]


class UserCreate(BaseModel):
    email: str
    name: str | None = None
    role: str = "sales"
    password: str


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    return scope_by_org(db.query(User), User, admin).order_by(User.created_at.desc()).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_role("admin")),
):
    if payload.role not in ROLES:
        raise HTTPException(422, f"role must be one of {ROLES}")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(409, "email already exists")

    # Enforce the plan's employee cap (super-admins are exempt).
    if not admin.is_super_admin and admin.organization_id:
        org = db.get(Organization, admin.organization_id)
        cap = org.plan.max_employees if org and org.plan else None
        current = db.query(User).filter(
            User.organization_id == admin.organization_id, User.is_active.is_(True)
        ).count()
        if cap is not None and current >= cap:
            raise HTTPException(
                403,
                f"Employee limit reached for your '{org.plan.name}' plan ({cap} users). "
                "Upgrade the plan to add more employees.",
            )

    user = User(
        email=payload.email, name=payload.name, role=payload.role,
        password_hash=hash_password(payload.password),
        organization_id=admin.organization_id,
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
