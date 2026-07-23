"""
Permanent deletion of a tenant ("hard delete").

Payment records are deliberately KEPT: they are financial history, and losing a
customer's invoices when they leave is the kind of thing that hurts at audit
time. `payments.organization_id` is NOT NULL and cascades, so the organization
ROW has to survive for those payments to remain valid — it is kept as a
tombstone (`deleted_at` set, slug freed, secrets stripped) and is hidden and
unusable everywhere else.

Everything operational is destroyed and is NOT recoverable: users, projects and
their entire tree, leads, chat history, API keys, builders, usage logs, and the
uploaded files on disk.

Deletion order matters. Postgres only cascades where `ondelete="CASCADE"` is
declared (projects → their children, chat sessions → messages, org →
subscription/payments); everything else would raise a foreign-key error, so the
rows that point at users and projects are removed first.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ApiKey, AuditLog, Builder, ChatSession, Document, Lead, Organization,
    Payment, Project, QueryLog, Subscription, User,
)

logger = logging.getLogger(__name__)


def preview(db: Session, org: Organization) -> dict:
    """What a hard delete would destroy — shown before the operator confirms."""
    def count(model, *filters) -> int:
        return db.query(func.count(model.id)).filter(*filters).scalar() or 0

    return {
        "users": count(User, User.organization_id == org.id),
        "projects": count(Project, Project.organization_id == org.id),
        "leads": count(Lead, Lead.organization_id == org.id),
        "chats": count(ChatSession, ChatSession.organization_id == org.id),
        "api_keys": count(ApiKey, ApiKey.organization_id == org.id),
        "documents": db.query(func.count(Document.id))
                       .join(Project, Project.id == Document.project_id)
                       .filter(Project.organization_id == org.id).scalar() or 0,
        # Not destroyed — surfaced so the operator knows what is being retained.
        "payments_kept": count(Payment, Payment.organization_id == org.id),
    }


def _remove_files(paths: list[str]) -> int:
    """Best-effort: a file we cannot delete must not fail the whole purge (the
    database rows are already gone by then)."""
    removed = 0
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
                removed += 1
        except OSError as exc:  # noqa: PERF203 — per-file, keep going
            logger.warning("Could not remove uploaded file %s: %s", path, exc)
    return removed


def purge(db: Session, org: Organization) -> dict:
    """Destroy the tenant's data, keep its payments, tombstone the org.

    Caller commits. Everything here runs in the caller's transaction, so a
    failure part-way rolls the whole thing back rather than leaving a
    half-deleted tenant.
    """
    org_id = org.id

    # Collect before deleting — the rows carrying these paths are about to go.
    paths = [
        p for (p,) in db.query(Document.file_path)
        .join(Project, Project.id == Document.project_id)
        .filter(Project.organization_id == org_id, Document.file_path.isnot(None))
        .all()
    ]
    user_ids = [u for (u,) in db.query(User.id).filter(User.organization_id == org_id).all()]

    def wipe(model, *filters) -> int:
        return db.query(model).filter(*filters).delete(synchronize_session=False)

    removed: dict[str, int] = {}
    removed["query_logs"] = wipe(QueryLog, QueryLog.organization_id == org_id)
    # Chat messages go with their session (ON DELETE CASCADE).
    removed["chats"] = wipe(ChatSession, ChatSession.organization_id == org_id)
    removed["leads"] = wipe(Lead, Lead.organization_id == org_id)
    removed["api_keys"] = wipe(ApiKey, ApiKey.organization_id == org_id)
    # One delete takes the whole knowledge tree with it: amenities, towers,
    # configurations, prices, payment plans, inventory, offers, documents and
    # their RAG chunks are all ON DELETE CASCADE from projects.
    removed["projects"] = wipe(Project, Project.organization_id == org_id)
    removed["builders"] = wipe(Builder, Builder.organization_id == org_id)

    if user_ids:
        # Their own audit trail goes with them. Entries the PLATFORM owner made
        # about this tenant are keyed to the owner, so they survive — including
        # the record of this deletion.
        removed["audit_rows"] = wipe(AuditLog, AuditLog.user_id.in_(user_ids))
        # Payments outlive their staff, so unlink rather than cascade — this is
        # also what stops the users delete below from hitting an FK error.
        db.query(Payment).filter(Payment.recorded_by.in_(user_ids)).update(
            {Payment.recorded_by: None}, synchronize_session=False
        )

    removed["users"] = wipe(User, User.organization_id == org_id)
    removed["subscription"] = wipe(Subscription, Subscription.organization_id == org_id)
    removed["payments_kept"] = (
        db.query(func.count(Payment.id)).filter(Payment.organization_id == org_id).scalar() or 0
    )

    # Tombstone the org itself.
    org.deleted_at = datetime.now(timezone.utc)
    org.is_active = False
    org.plan_id = None
    # Free the slug so the same company name can be onboarded again.
    org.slug = f"deleted-{org_id}-{org.slug}"[:180]
    # Drop tenant configuration — some of it (webhook secret, bot token) is a
    # credential, and none of it means anything now.
    org.crm_webhook_url = None
    org.crm_webhook_header = None
    org.crm_webhook_secret = None
    org.notify_provider = "off"
    org.notify_config = None
    org.assistant_persona = None
    org.widget_greeting = None

    removed["files"] = _remove_files(paths)
    return removed
