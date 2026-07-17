# Development Guide

How to work in this codebase: standards, the extension points, and step-by-step
recipes for the most common changes. Start with [architecture.md](architecture.md)
for the module map.

## Coding standards

### Python (backend)
- **Python 3.12**, type hints on public functions, modern `X | None` unions.
- **SQL-first, LLM-last** — never let the LLM produce a figure that could be read
  from the database. Facts flow through the renderer, not the model. This is the
  product's core rule (see [rag-pipeline.md](rag-pipeline.md)).
- **Thin routers, fat services.** `api/v1/*` validate + authorize + delegate;
  business logic lives in `services/*`.
- **Always scope to the tenant.** Any query on tenant-owned data must filter by
  `organization_id` (use `core/tenancy.py`). Cross-tenant access returns 404.
- **Fail-open for convenience infra** (Redis limits), **fail-closed for security**
  (auth, secret checks).
- **Audit mutations** with `core/audit.record_audit`; never log secrets/tokens.
- Comments explain *why*, matching the density of surrounding code.

### JavaScript (frontend)
- React function components + hooks; no class components.
- Server authorization is authoritative — client gating is cosmetic only.
- Render untrusted text safely (escape in the widget; `react-markdown` with raw
  HTML disabled in the SPA).

## Database changes & migrations

Schema is created by `init_db.py` (`Base.metadata.create_all`) plus **idempotent
lightweight migrations** — `ALTER TABLE … ADD COLUMN IF NOT EXISTS …` — that run
at container start. To add a column:

1. Add the field to the model in `models.py`.
2. Add a matching `ADD COLUMN IF NOT EXISTS` in `init_db.py` (and any backfill).
3. `docker compose restart api` so the migration runs (migrations run **only at
   start**, not on hot-reload).

> `alembic` is a dependency and available for heavier migrations, but the project
> currently relies on the `init_db` pattern above. See [roadmap.md](roadmap.md).

## Extension points

| Want to add… | Where |
|---|---|
| **A new LLM provider** | Implement the provider interface in `services/llm/`; select it via `LLM_PROVIDER`. No other code changes (Constitution §12). |
| **A new notification channel** | Usually none — the `webhook` provider in `services/notify.py` covers any HTTP endpoint via a body template + headers. Add a named provider only for a bespoke protocol. |
| **A new answer block type** | Add it to `services/renderer.py` and render it in the frontend `BlockRenderer.jsx`. |
| **A new embedding provider** | `services/rag/` + `EMBEDDING_PROVIDER`. |
| **An intent/keyword** | `services/intent.py` / `nlparse.py`. |

## Recipe: add an API endpoint

1. Pick or create the right router in `api/v1/` (one module per area).
2. Add the route with the correct dependency: `require_role("admin")`,
   `require_super_admin`, or `require_live_chat` — or `get_current_user` for
   API-key/JWT.
3. Scope any data access to `admin.organization_id` (or `get_scoped_project`).
4. Delegate logic to a `services/` function; keep the router thin.
5. Register the router in `main.py` if new.
6. Add a test for the pure logic (see [testing.md](testing.md)).

## Recipe: add a model

1. Add the class to `models.py` (include `organization_id` if tenant-owned; add
   `created_at`/`updated_at` if it's a fact-bearing row per the Citation Policy).
2. Add creation to `init_db.py` (create_all handles new tables; add columns for
   changes to existing tables).
3. Seed defaults in `seed.py` if needed.
4. Restart the API.

## Releasing

- Update `CHANGELOG.md` (Keep-a-Changelog style; SemVer).
- Bump `backend/app/__init__.py` `__version__`.
- Tag the release. History and the release workflow are in the repo.

## The "constitution"

`PRD.md` in the repo root is the non-negotiable design charter (SQL-first,
provider independence, citation policy, tenant isolation). Treat it as binding
when extending the engine.
