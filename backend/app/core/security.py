"""
Authentication & RBAC (Constitution §19).

- Passwords hashed with bcrypt (never stored in plaintext).
- JWT bearer tokens; keys/secrets server-side only.
- Role hierarchy: admin > manager > sales.
"""
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

# auto_error=False so a request can authenticate with an API key INSTEAD of a
# bearer token (we decide which below).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)

ROLE_RANK = {"sales": 1, "manager": 2, "admin": 3}


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def resolve_api_key(db: Session, raw_key: str) -> User | None:
    """Map an X-API-Key value to the user it acts as (its org-admin creator).
    Returns None if the key is unknown/revoked or its user is inactive."""
    from app.models import ApiKey

    row = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == hash_api_key(raw_key), ApiKey.is_active.is_(True))
        .first()
    )
    if not row or not row.created_by:
        return None
    user = db.get(User, row.created_by)
    if not user or not user.is_active:
        return None
    row.last_used_at = datetime.now(timezone.utc)
    db.commit()
    # The key itself declares what it's plugged into (website vs internal tool)
    # and what it may do. Carrying them here means the caller can never spoof.
    user._api_key_channel = (row.channel or "website").lower()
    user._api_key_scope = (row.scope or "full").lower()
    return user


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Asking a question is a POST, but it only ever READS the knowledge base — so a
# read-only key is still allowed to use the engine.
READ_ONLY_POST_PATHS = {"/v1/query"}

# A widget key ships inside a public web page, so treat it as already leaked:
# an exact allowlist of the calls widget.js makes, and nothing else — not even
# the blanket GET access a read-only key is trusted with. Adding an endpoint to
# widget.js means adding it here too.
WIDGET_ALLOWED = {
    ("POST", "/v1/query"),
    ("POST", "/v1/leads"),
    ("GET", "/v1/widget/config"),
    ("GET", "/v1/widget/poll"),
}


def enforce_key_scope(user: User, request) -> None:
    """Least privilege for API keys, enforced centrally in get_current_user so a
    new endpoint can never accidentally be left reachable by a weaker key."""
    scope = getattr(user, "_api_key_scope", "full")
    path = request.url.path.rstrip("/") or "/"

    if scope == "widget":
        # Preflight carries no API key of its own; CORS middleware answers it.
        if request.method == "OPTIONS" or (request.method, path) in WIDGET_ALLOWED:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This API key is a website-widget key: it can only run the public chat widget.",
        )

    if scope != "read_only":
        return
    if request.method in SAFE_METHODS:
        return
    if request.method == "POST" and path in READ_ONLY_POST_PATHS:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This API key is read-only: it can ask questions and read data, but not modify anything.",
    )


def hash_password(password: str) -> str:
    # bcrypt limits input to 72 bytes; truncate defensively.
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1) API key (machine-to-machine integrations) takes precedence.
    if x_api_key:
        user = resolve_api_key(db, x_api_key)
        if user is None:
            raise cred_exc
        # Mark the request as coming from an external channel (widget/CRM/etc.),
        # not a logged-in employee — used to auto-capture prospect phone numbers.
        user._via_api_key = True
        enforce_key_scope(user, request)   # read-only keys can't modify anything
        return user

    # 2) Otherwise, a JWT bearer token (the web app).
    if not token:
        raise cred_exc
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email: str | None = payload.get("sub")
        if email is None:
            raise cred_exc
    except jwt.PyJWTError:
        raise cred_exc

    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if user is None:
        raise cred_exc
    return user


def require_role(minimum: str):
    """Dependency factory enforcing a minimum role (RBAC)."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if ROLE_RANK.get(user.role, 0) < ROLE_RANK.get(minimum, 99):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{minimum}' role or higher",
            )
        return user

    return checker


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    """Only the platform owner (SaaS super-admin) may manage tenants and plans."""
    if not user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super-admin only")
    return user


def require_live_chat(user: User = Depends(get_current_user)) -> User:
    """Access to the Live Chat console. Admins (and super-admins) always have it;
    other employees only if an admin has granted them access."""
    if user.role == "admin" or user.is_super_admin or getattr(user, "can_live_chat", False):
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No Live Chat access")
