# REST API Reference

Base URL (local): `http://localhost:8001`. The **authoritative, always-current**
reference is the live OpenAPI at **`/docs`** (Swagger) and **`/openapi.json`**.
This page is the human-oriented map, grouped by function.

## Authentication

Three mechanisms:

| Caller | Header | Notes |
|---|---|---|
| Staff / admin / super-admin (SPA) | `Authorization: Bearer <jwt>` | Obtained from `POST /v1/auth/login`. |
| Website widget | `X-API-Key: px_…` | A **widget-scope** key (safe to embed publicly). |
| CRM / bot / server integration | `X-API-Key: px_…` | An **internal** channel key, usually `read_only`. |

Login uses OAuth2 password form fields (`username` = email, `password`). Tokens
carry `sub` (email) and `role`; the server re-reads the user from the database
on every request, so deactivations and role changes take effect immediately.
API-key **scopes** are enforced centrally — see [security.md](security.md).

---

## Auth

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/auth/login` | none | Exchange email+password for a JWT. |
| GET | `/v1/auth/me` | Bearer | Current user profile. |

```bash
curl -X POST http://localhost:8001/v1/auth/login \
  -d 'username=admin@chaahat.local&password=admin123'
```

## Ask a question

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/query` | Bearer **or** X-API-Key | The main entry point. Body: `{query, session_id, format}` where `format` ∈ `text` \| `voice` \| `blocks`. Returns `answer_text` and/or `content.blocks`. |

```bash
curl -X POST http://localhost:8001/v1/query \
  -H "X-API-Key: px_YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"query":"Golf Hills 3BHK price","session_id":"crm-42","format":"text"}'
```

## Website widget

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/v1/widget/config` | X-API-Key (widget) | Greeting, assistant name/avatar, accent. |
| GET | `/v1/widget/poll?session_id=…&after=…` | X-API-Key (widget) | Agent/system messages + mode (ai/human). |
| POST | `/v1/leads` | X-API-Key (widget) | Capture a lead (requires phone or email). |

## Projects (read)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/v1/projects` | Bearer | List the org's projects (`?q=` search). |
| GET | `/v1/projects/{id}` | Bearer | Full project detail. |
| GET | `/v1/projects/{id}/price` · `/payment-plan` · `/inventory` · `/status` · `/amenities` · `/towers` · `/location` | Bearer | Individual fact groups. |
| GET | `/v1/projects/{id}/brochure` · `/cost-sheet` · `/cost-sheets` | Bearer | Protected document downloads. |

## Admin — projects & data (`/v1/admin`, role: admin)

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/admin/projects` | Create a project. |
| POST | `/v1/admin/projects/{id}/configurations` · `/towers` · `/location` · `/amenities` · `/payment-plans` · `/cost-sheet` | Add child facts. |
| POST | `/v1/admin/projects/{id}/apply` | Apply an AI-extracted draft. |
| POST/DELETE | `/v1/admin/builders` · `/builders/{id}` | Manage builders. |
| POST | `/v1/admin/extract` | AI-extract structured facts from an uploaded PDF. |
| GET | `/v1/admin/export/projects.json` · `/projects.csv` | Export projects (JSON pack carries the full tree). |
| POST | `/v1/admin/import/projects-json` · `/projects-csv` | Import projects (JSON pack or flat CSV shells). |
| GET/PUT | `/v1/admin/assistant-config` · `/widget-config` · `/crm-config` · `/notify-config` | Assistant identity, greeting, CRM webhook, notifications. |
| POST/DELETE | `/v1/admin/assistant-avatar` | Assistant avatar upload/remove. |

## Admin — knowledge (`/v1/admin/knowledge`, role: admin)

| Method | Path | Purpose |
|---|---|---|
| GET | `/documents` | List uploaded documents. |
| POST | `/documents` | Upload a document (brochure/cost sheet). |
| POST | `/documents/{id}/reindex` · `/replace` · `/reindex-all` | Re-embed content. |

## Admin — team (`/v1/admin/users`, role: admin)

| Method | Path | Purpose |
|---|---|---|
| GET / POST | `/v1/admin/users` | List / create teammates (an org admin may create `sales`/`manager` only). |
| POST | `/v1/admin/users/{id}/toggle` · `/tier` · `/livechat` | Activate, set tier, grant Live Chat. |
| GET / PUT | `/v1/admin/users/tier-limits` | Per-tier daily AI-query limits. |

## Admin — API keys (`/v1/admin/api-keys`, role: admin)

| Method | Path | Purpose |
|---|---|---|
| GET / POST | `/v1/admin/api-keys` | List / create (choose channel + scope; key shown once). |
| DELETE | `/v1/admin/api-keys/{id}` | Revoke. |
| POST | `/v1/admin/api-keys/{id}/scope` · `/channel` | Change scope / channel. |

## Billing (`/v1/billing`, role: admin)

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/billing/me` | Plan, status, usage vs caps, last payment. |
| GET | `/v1/billing/payments` · `/payments.csv` | Payment history / export. |
| GET | `/v1/billing/payments/{id}/receipt` | Printable HTML receipt. |
| GET | `/v1/billing/plans` | Available plans / pricing. |
| POST / DELETE | `/v1/billing/upgrade-request` | Request / withdraw a plan change. |

## Live Chat (`/v1/admin/live`, admins + granted staff)

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/admin/live/sessions` · `/sessions/{id}` | Active sessions / transcript. |
| POST | `/v1/admin/live/sessions/{id}/takeover` · `/message` · `/release` | Human takeover, reply, hand back to AI. |

## Leads (admin)

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/admin/leads` | List captured leads (also the CRM catch-up/sync endpoint). |
| PATCH / DELETE | `/v1/admin/leads/{id}` | Update status / delete. |

## Analytics (`/v1/analytics`, managers + admins)

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/analytics/dashboard` · `/usage` | Questions, top/unanswered projects, per-employee usage vs limits. |

## Super-admin (`/v1/superadmin`, super-admin only)

| Method | Path | Purpose |
|---|---|---|
| GET / POST / PUT | `/plans` · `/plans/{id}` | Manage plans and pricing. |
| GET / POST / PUT | `/organizations` · `/organizations/{id}` | Manage tenants. |
| PUT | `/organizations/{id}/subscription` | Record a payment / set status / start trial. |
| GET / POST | `/organizations/{id}/projects` · `/seed-projects` | Inspect / copy a starter project set into a tenant. |
| GET | `/requests` | Pending plan-change requests. |
| GET / PUT / POST | `/notify-config` · `/notify-config/test` | Platform-owner alert channel. |

## Platform settings (`/v1/admin/settings`, super-admin)

| Method | Path | Purpose |
|---|---|---|
| GET / POST / POST | `/llm` · `/llm` · `/llm/test` | View / set / test the active LLM provider + key. |
| GET | `/models` | Available models. |

## Calculators & health

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/calculate/…` | Bearer | EMI / cost-sheet calculators. |
| GET | `/v1/admin/system/…` | admin | Live service health (DB, Redis, pgvector, LLM). |
| GET | `/health` | none | Liveness probe. |

---

### Response conventions
- Errors use standard HTTP codes with `{"detail": "..."}`.
- `403` = insufficient role / key scope; `404` = not found **or** not yours
  (cross-tenant access is a 404, never a leak); `409` = conflict (duplicate);
  `422` = validation; `429` = rate-limited.
