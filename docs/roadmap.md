# Roadmap & Technical Debt

An honest register of known debt and planned work. This is a living document —
update it as items land.

## Known technical debt

| Item | Impact | Notes / direction |
|---|---|---|
| **Migrations via `init_db` `ADD COLUMN IF NOT EXISTS`** | Med | Works and is idempotent, but not versioned. `alembic` is already a dependency; adopt versioned migrations for auditable schema history. See [development.md](development.md). |
| **No API-level integration tests** | Med | The suite covers pure helpers; add `TestClient` tests for endpoint auth, RBAC and tenant isolation, plus a CI coverage gate. See [testing.md](testing.md). |
| **No frontend automated tests** | Low–Med | The SPA is verified manually. Add component/e2e tests for critical flows (login, ask, billing). |
| **JWT in `localStorage`** | Med (latent) | Exfiltratable by any future XSS. Move the session token to an HttpOnly, Secure, SameSite cookie; keep token lifetimes short. |
| **No server-side token revocation** | Med | An 8h JWT stays valid after "sign out" (no denylist / `jti` / token-version). Add a revocation check, or short access tokens + refresh. |
| **Widget `session_id` is a bearer capability** | Med | The poll endpoint returns a session's agent messages by id. Bind the id to the visitor (server-issued token / HttpOnly cookie) so a leaked id alone can't read a session. |
| **Shipped compose is dev-oriented** | High (if used as-is) | Publishes Postgres/Redis on all interfaces and Redis has no password. Bind to loopback + set a Redis/Postgres password in production (see [deployment.md](deployment.md#production-checklist)). |
| **CSV export formula injection** | Low | Project/payment fields are written raw; a cell beginning `= + - @` can execute in Excel. Neutralize on export. |
| **`/docs` exposed in production** | Low | Consider disabling the public OpenAPI UI. |
| **`pymupdf` parses untrusted PDFs** | Low–Med | Native code with recurring CVEs; keep it patched and sandbox ingestion. |
| **One CRM webhook per org** | Low | Only one outbound lead destination; fan-out needs a middleware (n8n) or a feature. |

## Security hardening in progress

A separate, **unmerged** branch — `security-sprint-1` — implements a set of
hardening fixes with regression tests (kept off `main` pending review):

- Fail-closed env defaults + strong `SECRET_KEY` entropy guard.
- SSRF guard on outbound webhooks (with DNS-rebind-safe IP pinning).
- Postgres/Redis bound to loopback + Redis auth in production.
- Login brute-force lockout (keyed on IP+account) + constant-time compare.
- Response security headers (nosniff, frame-ancestors, HSTS, …).
- Seat-cap race fixed with a Postgres advisory lock.
- CSPRNG widget session ids.

Until merged, `main` does **not** include these; the docs describe them as
production recommendations, not shipped behavior.

## Product roadmap

| Area | Plan |
|---|---|
| **Payments (Phase 2)** | Payment-provider integration (e.g. Razorpay): self-serve checkout, webhook signature verification + idempotency, auto-renew, invoices. |
| **Tax invoices / GST** | Current receipts are payment receipts, not GST tax invoices. Add GST-compliant invoicing (series, GSTIN, place of supply) after a registration decision. |
| **Per-company negotiated pricing** | Override a plan's list price for a specific tenant (a custom price on the subscription), reflected in "record payment" and the tenant's pricing page. |
| **WhatsApp / Voice channels** | First-class adapters over the existing provider-agnostic layer (webhook works today; add native channels + inbound). |
| **Self-serve onboarding** | Public sign-up + trials (today tenants are provisioned by the platform owner). |
| **Assistant answer-style controls** | Admin controls for answer length/verbosity (currently persona-prompt driven; deferred by design). |
| **Scale-out** | Connection pooling (PgBouncer), read replicas, a tuned pgvector index as chunk volume grows (see [operations.md](operations.md#scaling)). |

## How to use this document

- When you fix a debt item, remove it here and note it in `CHANGELOG.md`.
- When you plan new work, add it under **Product roadmap** with a one-line
  direction so the intent survives.
