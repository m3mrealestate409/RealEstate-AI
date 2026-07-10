"""
Multi-tenant scoping helpers.

Every data read must be limited to the caller's organization so tenants never
see each other's projects/documents. Super-admins (the SaaS owner) have no org
and can see across all tenants.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Project, User


def org_scope_id(user: User) -> int | None:
    """The org id to scope reads to. None → super-admin (unscoped, sees all)."""
    return None if user.is_super_admin else user.organization_id


def scope_by_org(query, model, user: User):
    """Apply an organization filter to a query unless the user is a super-admin."""
    oid = org_scope_id(user)
    if oid is not None:
        return query.filter(model.organization_id == oid)
    return query


def get_scoped_project(db: Session, project_id: int, user: User) -> Project:
    """Fetch a project only if it belongs to the caller's org (else 404 — we
    hide existence across tenants)."""
    p = db.get(Project, project_id)
    if not p or (not user.is_super_admin and p.organization_id != user.organization_id):
        raise HTTPException(404, "Project not found")
    return p
