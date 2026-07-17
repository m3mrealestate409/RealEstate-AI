# Security Model

This describes the security controls built into the product. For production
network/ops hardening, see the checklist in [deployment.md](deployment.md).

## Authentication

- **Staff/admin:** JWT (HS256), issued by `POST /v1/auth/login`, sent as
  `Authorization: Bearer`. Tokens carry `sub` (email) and `role` and expire after
  `ACCESS_TOKEN_EXPIRE_MINUTES` (default 8h).
- **Role is never trusted from the token.** `get_current_user` re-loads the user
  from the database on every request and checks `is_active`, so deactivations and
  role changes take effect immediately — a stale token can't retain access.
- **Passwords** are bcrypt-hashed (input truncated to bcrypt's 72-byte limit
  consistently on both hash and verify).
- **JWT algorithm** is pinned to a single value (`algorithms=[HS256]`), so
  `alg=none` and RS256→HS256 confusion are not possible.
- **Production guard:** the app refuses to boot with a weak/default `SECRET_KEY`
  when `APP_ENV=production`; anyone who knew the default could otherwise forge a
  super-admin token.

## Authorization (RBAC + scoping)

- Role dependencies (`require_role`, `require_super_admin`, `require_live_chat`)
  gate every privileged route on the server.
- **No privilege-escalation path:** an org admin can create only `sales`/`manager`
  (not `admin`); there is no change-role endpoint; `is_super_admin` is never
  settable through any request body.
- **Super-admin** routes (`/v1/superadmin/*`) require `is_super_admin`.

## Tenant isolation

- Every tenant-owned row carries `organization_id`. Reads are scoped on the
  server via `core/tenancy.py`; an object id alone never crosses organizations.
- Cross-tenant access returns **404**, never a data leak.
- Project ids from user input are re-filtered to the caller's org before any
  SQL/RAG lookup (defence in depth).
- RAG retrieval and answer generation are org-scoped — a tenant's documents are
  never retrieved for another tenant.

## API keys

An API key acts as its creating admin and carries that admin's `organization_id`.
Only a hash + prefix are stored; the full key is shown once at creation. Two axes:

| Axis | Values | Meaning |
|---|---|---|
| **channel** | `website` \| `internal` | Website raises new-visitor alerts and appears in Live Chat; internal (CRM/bot) does not, and gets higher limits. |
| **scope** | `widget` \| `read_only` \| `full` | What the key may do. |

Scope is enforced centrally (`enforce_key_scope`), so a new endpoint can't
accidentally be left reachable by a weaker key:

- **`widget`** — an exact allow-list of the four widget calls (`POST /v1/query`,
  `POST /v1/leads`, `GET /v1/widget/config`, `GET /v1/widget/poll`) and nothing
  else. Safe to embed in a public web page.
- **`read_only`** — may ask questions and read (safe GETs + `POST /v1/query`),
  never modify. Right for a CRM.
- **`full`** — acts with its creator's admin rights. Server-side use only; never
  embed in a page.

## Abuse protection & quotas

Only **expensive** queries (LLM/RAG) are limited; plain SQL look-ups (price,
inventory) are always free.

- **Widget (public):** per-session and per-IP fixed-window rate limits
  (`services/ratelimit.py`), plus a per-org **daily** LLM budget scoped to the
  channel, so public widget abuse can never exhaust staff or CRM budgets.
- **Employees:** a per-user daily quota by tier, and a company-wide daily cap
  (`services/quota.py`).
- **Degrade, don't fail:** when a budget is spent the engine skips the LLM but
  still answers from the database.
- All limiters are **fail-open** — a Redis outage never blocks real users (it
  degrades enforcement, not correctness).

## Secrets

- No secret is exposed to the frontend; only `VITE_API_URL` reaches the browser
  bundle. LLM/provider keys live server-side (env or the `settings` table) and are
  never returned to the client (only a masked status).
- `.env` is git-ignored; only `.env.example` (placeholders) is tracked.

## Auditing

- `audit_log` records create/update/delete with actor, entity and before/after
  snapshots. Sensitive values (tokens, secrets) are not written to the log.

## Data lifecycle & privacy

- Website chat transcripts are retained ~15 days; the demand **intent** (which
  project, what they wanted) is kept for analytics after raw chats are purged —
  minimizing stored visitor data.
- Suspending a subscription pauses AI answers only; it never deletes data.

## Production network hardening

The application controls above are in place regardless of deployment. The
network/ops items — binding PostgreSQL/Redis to loopback, a Redis password,
strong DB password, TLS, non-root container, tight CORS — are your
responsibility at deploy time. See the checklist in
[deployment.md](deployment.md#production-checklist).
