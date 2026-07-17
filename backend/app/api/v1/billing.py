"""
Billing, as the tenant sees it.

An org admin may look at their plan, what it entitles them to, what they have
used, what they have paid, and what other plans cost. They cannot mark anything
paid — Phase 1 takes money by hand, so only a super-admin records it. The one
thing they can do is ASK to change plan, which lands on the platform owner's
list rather than charging anyone.

Everything here is scoped to the caller's own organization.
"""
import csv
import io
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.security import require_role
from app.database import get_db
from app.models import Organization, Payment, Plan, User
from app.services import billing, quota

router = APIRouter(prefix="/v1/billing", tags=["billing"])


def _my_org(db: Session, admin: User) -> Organization:
    org = db.get(Organization, admin.organization_id) if admin.organization_id else None
    if org is None:
        raise HTTPException(404, "Your account is not attached to an organization.")
    return org


@router.get("/me")
def my_billing(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    org = db.get(Organization, admin.organization_id) if admin.organization_id else None
    out = billing.summary(db, org)
    if org is None:
        return out
    out["employees"] = db.query(func.count(User.id)).filter(
        User.organization_id == org.id, User.is_active.is_(True)
    ).scalar() or 0
    out["queries_today"] = quota.org_used_today(org.id, date.today().isoformat())
    sub = org.subscription
    out["requested_plan"] = sub.requested_plan.name if sub and sub.requested_plan else None
    last = (
        db.query(Payment).filter(Payment.organization_id == org.id)
        .order_by(Payment.created_at.desc()).first()
    )
    out["last_payment"] = billing.payment_out(last) if last else None
    return out


# ------------------------------ Payments ----------------------------------
@router.get("/payments")
def my_payments(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    org = _my_org(db, admin)
    rows = (
        db.query(Payment).filter(Payment.organization_id == org.id)
        .order_by(Payment.created_at.desc()).all()
    )
    return {
        "total_paid": float(sum(float(p.amount or 0) for p in rows)),
        "count": len(rows),
        "payments": [billing.payment_out(p) for p in rows],
    }


def _payment_or_404(db: Session, admin: User, payment_id: int) -> Payment:
    p = db.get(Payment, payment_id)
    # Scope check, not just existence — a tenant must never read another's receipt.
    if not p or p.organization_id != admin.organization_id:
        raise HTTPException(404, "Payment not found")
    return p


@router.get("/payments.csv")
def payments_csv(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    """The whole history as a spreadsheet — what an accountant actually wants."""
    org = _my_org(db, admin)
    rows = (
        db.query(Payment).filter(Payment.organization_id == org.id)
        .order_by(Payment.created_at.asc()).all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Receipt no", "Paid on", "Plan", "Period from", "Period to",
                "Amount", "Currency", "Method", "Reference", "Note"])
    for p in rows:
        w.writerow([
            p.receipt_no,
            p.created_at.date().isoformat() if p.created_at else "",
            p.plan_name or "", p.period_start or "", p.period_end or "",
            f"{float(p.amount or 0):.2f}", p.currency or "INR",
            p.method or "", p.reference or "", p.note or "",
        ])
    buf.seek(0)
    fname = f"payments-{org.slug}-{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


def _esc(s) -> str:
    return (
        str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


@router.get("/payments/{payment_id}/receipt", response_class=HTMLResponse)
def receipt(payment_id: int, db: Session = Depends(get_db),
            admin: User = Depends(require_role("admin"))):
    """A printable receipt. Self-contained HTML rather than a PDF: the stack has
    no PDF engine, and every browser prints to PDF anyway — so this stays a
    dependency-free page that saves exactly as well.

    This is a PAYMENT RECEIPT, not a GST tax invoice: no invoice series, GSTIN
    or place of supply. Saying otherwise on a document someone may claim input
    credit against would be worse than useless.
    """
    p = _payment_or_404(db, admin, payment_id)
    org = _my_org(db, admin)
    period = ""
    if p.period_start or p.period_end:
        period = f"{p.period_start or '—'} to {p.period_end or '—'}"
    amount = f"{p.currency or 'INR'} {float(p.amount or 0):,.2f}"
    paid_on = p.created_at.strftime("%d %b %Y") if p.created_at else ""

    rows = [
        ("Receipt no", p.receipt_no),
        ("Paid on", paid_on),
        ("Billed to", org.name),
        ("Plan", p.plan_name or "—"),
        ("Service period", period or "—"),
        ("Method", (p.method or "—").upper()),
        ("Reference", p.reference or "—"),
    ]
    body = "".join(
        f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>" for k, v in rows
    )
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Receipt {_esc(p.receipt_no)}</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #1e2230;
         max-width: 640px; margin: 40px auto; padding: 0 20px; }}
  .head {{ display: flex; justify-content: space-between; align-items: flex-start;
           border-bottom: 2px solid #6b46ff; padding-bottom: 14px; margin-bottom: 22px; }}
  .brand {{ font-size: 22px; font-weight: 800; color: #6b46ff; }}
  .muted {{ color: #6b7280; font-size: 12px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 22px; }}
  th, td {{ text-align: left; padding: 9px 0; border-bottom: 1px solid #eceef3; font-size: 14px; }}
  th {{ color: #6b7280; font-weight: 600; width: 40%; }}
  .total {{ display: flex; justify-content: space-between; align-items: center;
            background: #f5f3ff; border-radius: 10px; padding: 14px 16px; font-size: 20px;
            font-weight: 800; }}
  .foot {{ margin-top: 26px; font-size: 11px; color: #6b7280; line-height: 1.6; }}
  .btn {{ background: #6b46ff; color: #fff; border: 0; border-radius: 8px; padding: 9px 16px;
          font-size: 13px; cursor: pointer; margin-top: 22px; }}
  @media print {{ .btn {{ display: none; }} body {{ margin: 0; }} }}
</style></head><body>
  <div class="head">
    <div><div class="brand">PropX Estate</div><div class="muted">Payment receipt</div></div>
    <div class="muted">{_esc(p.receipt_no)}<br>{_esc(paid_on)}</div>
  </div>
  <table>{body}</table>
  <div class="total"><span>Amount paid</span><span>{_esc(amount)}</span></div>
  <div class="foot">
    This is a receipt for a payment received, not a tax invoice — it carries no GST,
    invoice series or place of supply. Keep it for your records.
  </div>
  <button class="btn" onclick="window.print()">Print / Save as PDF</button>
</body></html>"""
    return HTMLResponse(html)


# ------------------------------ Pricing -----------------------------------
@router.get("/plans")
def pricing(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    """What every plan costs and includes — so an admin can see what moving up buys."""
    org = _my_org(db, admin)
    plans = db.query(Plan).filter(Plan.is_active.is_(True)).order_by(Plan.price_monthly).all()
    sub = org.subscription
    return {
        "current_plan_id": org.plan_id,
        "requested_plan_id": sub.requested_plan_id if sub else None,
        "plans": [{
            "id": p.id, "name": p.name,
            "price_monthly": float(p.price_monthly or 0),
            "max_employees": p.max_employees,
            "daily_llm_quota": p.daily_llm_quota,
        } for p in plans],
    }


class UpgradeIn(BaseModel):
    plan_id: int


@router.post("/upgrade-request")
def request_upgrade(payload: UpgradeIn, db: Session = Depends(get_db),
                    admin: User = Depends(require_role("admin"))):
    """Ask to move plan. Charges nothing and grants nothing — Phase 1 has no
    checkout, so this only raises a flag the platform owner acts on."""
    org = _my_org(db, admin)
    plan = db.get(Plan, payload.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(422, "plan not found")
    if plan.id == org.plan_id:
        raise HTTPException(422, "You are already on that plan.")
    sub = billing.ensure_subscription(db, org)
    sub.requested_plan_id = plan.id
    sub.requested_at = datetime.now(timezone.utc)
    record_audit(db, user_id=admin.id, action="UPDATE", entity="subscriptions",
                 entity_id=sub.id, after={"requested_plan": plan.name})
    db.commit()
    return {"requested_plan": plan.name,
            "message": f"Request noted — we'll contact you about moving to {plan.name}."}


@router.delete("/upgrade-request")
def cancel_upgrade(db: Session = Depends(get_db), admin: User = Depends(require_role("admin"))):
    org = _my_org(db, admin)
    sub = org.subscription
    if sub:
        sub.requested_plan_id = None
        sub.requested_at = None
        db.commit()
    return {"ok": True}
