"""
Multi-tenant scoping helpers.

Every data read must be limited to the caller's organization so tenants never
see each other's projects/documents. A tenant user is ALWAYS locked to their own
org. A super-admin (the SaaS owner) normally sees across all tenants — but can
"open" one company in the console (the Platform page), which sets a per-request
acting-as tenant (via the `X-As-Org` header). While that is set, the console's
read endpoints (Knowledge / Projects / Ask) return just that company's data
instead of everything mixed together.
"""
import contextvars

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models import Project, User

# The tenant a SUPER-ADMIN has opened for THIS request, or None (see all). It is
# set ONLY by apply_viewing_tenant(), and ONLY for super-admins — a tenant user
# can never move it, so it can never become a cross-tenant read. It defaults to
# None, so any code path that never calls apply_viewing_tenant() behaves exactly
# as before (super-admin unscoped).
_acting_org: contextvars.ContextVar[int | None] = contextvars.ContextVar("acting_org", default=None)


def org_scope_id(user: User) -> int | None:
    """The org id to scope reads to. A tenant user is ALWAYS their own org. A
    super-admin is scoped to the tenant they've opened (X-As-Org), or None
    (unscoped, sees all) when they haven't opened one."""
    if user.is_super_admin:
        return _acting_org.get()
    return user.organization_id


def apply_viewing_tenant(request: Request, user: User) -> None:
    """Call at the top of a console READ endpoint. If a SUPER-ADMIN has opened one
    company's view (sent the `X-As-Org` header), scope this request's reads to
    that tenant. A no-op for tenant users and for API-key callers — they can
    never widen or move their own scope, so this can never leak another tenant's
    data. Safe to call before the contextvar is read (same sync request execution)."""
    if not user.is_super_admin:
        return
    raw = request.headers.get("X-As-Org")
    if not raw:
        return
    try:
        _acting_org.set(int(raw))
    except (TypeError, ValueError):
        pass  # a malformed header simply leaves the super-admin unscoped


def scope_by_org(query, model, user: User):
    """Apply an organization filter to a query unless the user is an (unscoped)
    super-admin."""
    oid = org_scope_id(user)
    if oid is not None:
        return query.filter(model.organization_id == oid)
    return query


def get_scoped_project(db: Session, project_id: int, user: User) -> Project:
    """Fetch a project only if it belongs to the caller's org (else 404 — we
    hide existence across tenants). A super-admin may open any project."""
    p = db.get(Project, project_id)
    if not p or (not user.is_super_admin and p.organization_id != user.organization_id):
        raise HTTPException(404, "Project not found")
    return p
