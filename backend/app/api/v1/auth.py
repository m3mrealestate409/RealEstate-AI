"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import (
    assert_org_allowed, create_access_token, get_current_user, hash_password, verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas import TokenResponse, UserOut
from app.services import ratelimit

router = APIRouter(prefix="/v1/auth", tags=["auth"])

# Precomputed once so a login for a NON-existent user still spends bcrypt time.
# Without this, missing emails returned in ~1ms and valid emails in ~80ms — a
# timing oracle that enumerates valid accounts before any password is guessed.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=TokenResponse)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    # OAuth2 form uses `username`; we treat it as email.
    ip = _client_ip(request)
    # Brute-force / credential-stuffing throttle: too many recent FAILED attempts
    # from this IP or against this account → refuse before touching the DB.
    if not ratelimit.login_allowed(ip, form.username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait a few minutes and try again.",
        )
    user = db.query(User).filter(User.email == form.username, User.is_active.is_(True)).first()
    # Constant time: always run exactly one bcrypt compare, real user or not.
    ok = verify_password(form.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        ratelimit.login_register_failure(ip, form.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    # Credentials are right, but the company itself may be suspended/deleted.
    # Checked AFTER the password so it can never be used to probe which emails
    # belong to a suspended tenant.
    assert_org_allowed(db, user)
    ratelimit.login_reset(ip, form.username)  # successful login clears the (ip, account) counter
    token = create_access_token(subject=user.email, role=user.role)
    return TokenResponse(
        access_token=token, role=user.role, name=user.name,
        is_super_admin=user.is_super_admin, organization_id=user.organization_id,
        can_live_chat=user.can_live_chat,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
