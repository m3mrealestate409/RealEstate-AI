"""
CRM lead push — one place, so every lead reaches the customer's CRM with the
SAME shape, whether it came from the callback form or from a phone number the
visitor typed into the chat.

Delivery is best-effort but persistent: retries with backoff, and never blocks
the reply (a slow/down CRM must not slow the visitor's chat). The lead is always
saved in our own DB first, so a failed push only means the CRM missed it — the
CRM can reconcile any time via GET /v1/admin/leads.
"""
from __future__ import annotations

import logging
import threading
import time

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 8.0
_ATTEMPTS = 3
_BACKOFF = (2, 5)          # seconds to wait before retry 2 and 3
DEFAULT_SECRET_HEADER = "X-Webhook-Secret"
IDEMPOTENCY_HEADER = "X-Idempotency-Key"
IDEMPOTENCY_PREFIX = "rag-lead-"


def lead_payload(lead) -> dict:
    """The webhook contract. Keep this the single source of truth — every push
    path uses it, so the CRM always receives the same fields."""
    return {
        "id": lead.id,
        "name": lead.name,
        "phone": lead.phone,
        "email": lead.email,
        "message": lead.message,
        "project_interest": lead.project_interest,
        "source": lead.source,
        "page_url": lead.page_url,
        "status": lead.status,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
    }


def webhook_headers(org) -> dict:
    """Optional shared secret so the CRM can verify the call really came from us."""
    secret = (getattr(org, "crm_webhook_secret", None) or "").strip()
    if not secret:
        return {}
    name = (getattr(org, "crm_webhook_header", None) or "").strip() or DEFAULT_SECRET_HEADER
    return {name: secret}


def idempotency_key(lead_id) -> str:
    """Stable identity for a lead, so a CRM can de-duplicate it the same way
    whether it arrived via our push (incl. a retry) or was pulled later from
    GET /v1/admin/leads during a reconcile."""
    return f"{IDEMPOTENCY_PREFIX}{lead_id}"


def push_lead(url: str, payload: dict, headers: dict | None = None) -> bool:
    """POST the lead, retrying on network errors AND non-2xx. Returns success."""
    h = {
        "Content-Type": "application/json",
        # Same key on every attempt — a retry can never create a duplicate.
        IDEMPOTENCY_HEADER: idempotency_key(payload.get("id")),
        **(headers or {}),
    }
    detail = "unknown"
    for attempt in range(_ATTEMPTS):
        try:
            r = httpx.post(url, json=payload, headers=h, timeout=_TIMEOUT)
            if r.status_code < 300:
                return True
            detail = f"HTTP {r.status_code}: {r.text[:150]}"
        except Exception as exc:  # noqa: BLE001 — network hiccup, retry
            detail = str(exc)
        if attempt < _ATTEMPTS - 1:
            time.sleep(_BACKOFF[attempt])
    logger.warning("CRM webhook push failed after %s attempts (lead id=%s): %s",
                   _ATTEMPTS, payload.get("id"), detail)
    return False


def push_lead_async(url: str, payload: dict, headers: dict | None = None) -> None:
    """Fire the push on a background thread so retries never delay the caller."""
    if not url:
        return
    threading.Thread(target=push_lead, args=(url, payload, headers), daemon=True).start()
