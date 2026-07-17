"""
Billing — does a tenant currently deserve what its plan promises?

The engine already enforces plan limits (employee cap in `api/v1/users.py`,
daily LLM quota in `orchestrator`). Everything here does is decide what those
limits ARE right now, given whether the org has paid. One resolver, so payment
state can never be enforced in one place and forgotten in another.

Two ideas worth keeping straight:

  * `Subscription.status` is an INTENT recorded by a human ("they paid").
  * `effective_status()` is the TRUTH, derived from the dates every time it is
    asked. An expiry therefore needs no cron job and cannot be missed — the
    moment `current_period_end` passes, grace starts on its own.

The failure ladder is deliberate: expiry does not slam a door. It opens a
GRACE_DAYS window where nothing changes but the warnings, and only then stops
the expensive part (LLM answers). Data, logins and leads are never withheld —
we are holding back our own running costs, not the customer's own information.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Organization, Payment, Plan, Subscription

logger = logging.getLogger(__name__)

# Days after `current_period_end` in which everything still works, so a late
# bank transfer or a forgotten invoice never breaks a live customer's website.
GRACE_DAYS = 7
# A new tenant's trial, when nobody has said otherwise.
TRIAL_DAYS = 14

# Statuses a human can set. `past_due` is never set by hand — it is derived.
SETTABLE = {"trialing", "active", "suspended", "cancelled"}
# The engine answers questions in these states.
SERVING = {"trialing", "active", "past_due"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """Postgres can hand back naive datetimes depending on the driver/column."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def effective_status(sub: Subscription | None, now: datetime | None = None) -> str:
    """The real state right now: trialing | active | past_due | suspended |
    cancelled | none. Derived from dates, so it is always current."""
    if sub is None:
        return "none"
    now = now or _now()
    status = (sub.status or "trialing").lower()

    # A human said stop — dates cannot revive it.
    if status in ("suspended", "cancelled"):
        return status

    if status == "trialing":
        ends = _aware(sub.trial_ends_at)
        if ends is None or now <= ends:
            return "trialing"
        # An expired trial gets the same grace as a lapsed payment.
        return "past_due" if now <= ends + timedelta(days=GRACE_DAYS) else "suspended"

    if status == "active":
        ends = _aware(sub.current_period_end)
        if ends is None:
            return "active"          # paid, no end date recorded = open-ended
        if now <= ends:
            return "active"
        return "past_due" if now <= ends + timedelta(days=GRACE_DAYS) else "suspended"

    return status


def paid_until(sub: Subscription | None) -> datetime | None:
    """How far the money currently reaches (ignores any trial)."""
    return _aware(sub.current_period_end) if sub else None


def expires_at(sub: Subscription | None) -> datetime | None:
    """When the current entitlement runs out (trial end or paid-till)."""
    if sub is None:
        return None
    status = (sub.status or "").lower()
    return _aware(sub.trial_ends_at if status == "trialing" else sub.current_period_end)


def days_left(sub: Subscription | None, now: datetime | None = None) -> int | None:
    """Whole days until expiry. Negative once inside grace. None = open-ended."""
    ends = expires_at(sub)
    if ends is None:
        return None
    delta = ends - (now or _now())
    return int(delta.total_seconds() // 86400)


@dataclass
class Entitlements:
    """What this org may do right now. The only source of truth for limits."""

    status: str                     # effective_status()
    plan_name: str | None
    max_employees: int | None       # None = unlimited
    daily_llm_quota: int | None     # None = unlimited, 0 = AI switched off
    ai_enabled: bool
    reason: str | None = None       # why AI is off, shown to the user


# Said to an employee whose org has stopped paying. Deliberately blames the
# account, not the person, and never sounds like the product is broken.
SUSPENDED_MSG = (
    "Your organisation's subscription is not active, so AI answers are paused. "
    "Your data and leads are safe — an admin can restore access by renewing the plan."
)


def entitlements(db: Session, org: Organization | None) -> Entitlements:
    """Resolve an org's live limits from its plan AND whether it has paid."""
    if org is None:
        return Entitlements(status="none", plan_name=None, max_employees=None,
                            daily_llm_quota=None, ai_enabled=True)

    plan: Plan | None = org.plan
    sub: Subscription | None = org.subscription
    status = effective_status(sub)

    plan_employees = plan.max_employees if plan else None
    plan_quota = plan.daily_llm_quota if plan else None
    plan_name = plan.name if plan else None

    # No subscription row: only a super-admin can create an org (there is no
    # public sign-up), so a missing row means "predates billing", not "sneaked
    # in without paying". Serve the plan. Revisit this the day self-serve
    # sign-up ships — then a missing row must mean `trialing`, not `active`.
    if status in ("none", *SERVING):
        return Entitlements(status=status, plan_name=plan_name,
                            max_employees=plan_employees, daily_llm_quota=plan_quota,
                            ai_enabled=True)

    # suspended / cancelled — stop the part that costs us money, keep the rest.
    return Entitlements(status=status, plan_name=plan_name,
                        max_employees=plan_employees, daily_llm_quota=0,
                        ai_enabled=False, reason=SUSPENDED_MSG)


def ensure_subscription(db: Session, org: Organization, *, trial: bool = True) -> Subscription:
    """Give a new org a subscription so its state is never undefined."""
    if org.subscription is not None:
        return org.subscription
    now = _now()
    sub = Subscription(
        organization_id=org.id,
        plan_id=org.plan_id,
        status="trialing" if trial else "active",
        trial_ends_at=now + timedelta(days=TRIAL_DAYS) if trial else None,
        current_period_end=None if trial else now + timedelta(days=30),
    )
    db.add(sub)
    db.flush()
    return sub


METHODS = {"bank", "upi", "cash", "card", "other"}


def payment_out(p: Payment) -> dict:
    return {
        "id": p.id,
        "receipt_no": p.receipt_no,
        "amount": float(p.amount or 0),
        "currency": p.currency or "INR",
        "plan": p.plan_name,
        "method": p.method,
        "reference": p.reference,
        "period_start": p.period_start.isoformat() if p.period_start else None,
        "period_end": p.period_end.isoformat() if p.period_end else None,
        "note": p.note,
        "paid_on": p.created_at.isoformat() if p.created_at else None,
    }


def record_payment(
    db: Session, org: Organization, *, amount: float, period_start, period_end,
    method: str | None = None, reference: str | None = None, note: str | None = None,
    recorded_by: int | None = None,
) -> Payment:
    """Write the money down. Called whenever a payment is recorded, so the
    history survives the next renewal overwriting `current_period_end`."""
    p = Payment(
        organization_id=org.id,
        plan_id=org.plan_id,
        plan_name=org.plan.name if org.plan else None,   # snapshot — see the model
        amount=amount or 0,
        period_start=period_start,
        period_end=period_end,
        method=(method or "").lower() if method else None,
        reference=(reference or "").strip() or None,
        note=(note or "").strip() or None,
        recorded_by=recorded_by,
    )
    db.add(p)
    db.flush()
    return p


def summary(db: Session, org: Organization | None) -> dict:
    """What an org admin sees on their Plan & Usage page."""
    ent = entitlements(db, org)
    sub = org.subscription if org else None
    ends = expires_at(sub)
    return {
        "status": ent.status,
        "plan": ent.plan_name,
        "price_monthly": float(org.plan.price_monthly) if org and org.plan else None,
        "max_employees": ent.max_employees,
        "daily_llm_quota": ent.daily_llm_quota,
        "ai_enabled": ent.ai_enabled,
        "reason": ent.reason,
        "expires_at": ends.isoformat() if ends else None,
        "days_left": days_left(sub),
        "grace_days": GRACE_DAYS,
        "note": sub.note if sub else None,
    }
