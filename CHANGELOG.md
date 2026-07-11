# Changelog

All notable changes to the Chaahat Homes AI Knowledge Engine are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/); this
project uses [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH).

## [Unreleased]

## [1.13.0] — 2026-07-11

### Added — Project ↔ builder
- **Choose a builder per project** — the New Project and Project Details forms
  now have a Builder dropdown (org's builders + "None").
- The project page shows **"🏗️ by {builder}"** at the top.
- Project detail/list responses include `builder_id` and `builder_name`.

### Changed
- **Builders are now organization-scoped** — each tenant sees and picks only its
  own builders (previously global). Existing builders migrate to the default org.
  A project can only be assigned a builder from its own organization.

## [1.12.1] — 2026-07-11

### Fixed
- **Mobile & tablet navigation** — on narrow screens the sidebar was hidden with
  no way to navigate. Added a top bar with a hamburger that opens the sidebar as
  a slide-in drawer (with backdrop); tapping a link navigates and closes it.
  Desktop is unchanged.

## [1.12.0] — 2026-07-11

### Added — Cost sheet
- **Cost Sheet** (optional) — Admin → Manage Data → Cost Sheet lets an admin
  upload a project's cost-sheet PDF. It is stored for viewing/download only and
  is **not** indexed into RAG (pricing stays in SQL, §6).
- The project page now shows a **View Cost Sheet** button next to View Brochure
  (inline viewer + download), when a cost sheet exists.
- Endpoints: `POST /v1/admin/projects/{id}/cost-sheet` (upload) and
  `GET /v1/projects/{id}/cost-sheet(/info)` (serve/metadata), org-scoped.

## [1.11.0] — 2026-07-10

### Added — AI-assisted data entry
- **AI Import** (Admin → 🪄 AI Import) — upload a brochure/price-list PDF and
  Gemini extracts the structured data (type, land parcel, green area, status,
  possession, towers, configurations with pricing, payment plan) into an
  **editable preview**. Prices are highlighted for review. Nothing is saved until
  the admin confirms; on save it writes to the project's SQL tables.
- Endpoints: `POST /v1/admin/extract` (PDF → draft, nothing saved) and
  `POST /v1/admin/projects/{id}/apply` (reviewed draft → SQL). Org-scoped,
  audited; the AI never invents figures (unknown values come back blank).

## [1.10.0] — 2026-07-10

### Added — Richer project details
- New project fields: **Type** (Residential/Commercial/Industrial), **Land parcel**,
  **Green/open area**, and a **Delivered** status option.
- **Per-tower details** — a new towers table; each tower has a name, floors,
  height and units/floor. Managed under Admin → Manage Data → Towers.
- **Project Details** editor (Manage Data) to edit these attributes on existing
  projects; the New Project form includes them too.
- Project page now shows an **Overview** section (type, land, green area, total
  towers) and a **Towers** table.
- Query engine understands project overview questions ("land parcel", "how many
  towers", "project type") and answers from SQL.

## [1.9.1] — 2026-07-10

### Fixed
- **"View Brochure" always shows the newest** — the latest brochure is now chosen
  by most-recent upload time, and a Replace refreshes that timestamp. Previously,
  ordering by version could surface an older (higher-version) document over a
  newer separate upload.

## [1.9.0] — 2026-07-10

### Added
- **View Brochure** — the project detail page now shows a "View Brochure" button
  when a project has an uploaded brochure. It opens the latest brochure PDF in an
  inline viewer (modal iframe) with a Download option. Streamed via
  `GET /v1/projects/{id}/brochure` (+ `/brochure/info`), org-scoped so a tenant
  can only view its own project's brochure (cross-tenant access → 404). The PDF
  is fetched with the auth token as a blob, so the file stays access-controlled.

## [1.8.0] — 2026-07-10

### Changed — Branding: PropX Estate
- App rebranded to **PropX Estate** with a gold SVG wordmark + "PX" monogram
  (logo, sidebar, login, favicon, browser title).
- Product tagline is now **Knowledge Guru**; the main heading reads
  "Ask the Knowledge Guru".
- Replaced all emoji nav/action icons with professional line SVG icons.

## [1.7.0] — 2026-07-10

### Added
- **Response caching** — repeated expensive queries are served from a per-org
  Redis cache (≈17× faster, no LLM cost). A "⚡ cached" chip marks cached
  answers; cache hits don't consume quota. Freshness via a 10-min TTL plus a
  per-org cache version that is bumped on any data change (price/document/
  project edits). Follow-ups (context-dependent) are never cached.
- **Company-wide quota** — a plan's `daily_llm_quota` now caps the whole
  organization's daily AI queries (in addition to per-employee tier limits).
- **Usage dashboard** — Analytics now shows AI usage today per employee
  (used/limit bar, tier, over-limit in red) and the company total vs plan quota.

## [1.6.0] — 2026-07-10

### Added — Employee tiers + daily query quota (Phase 2)
- **Per-employee tiers** — org-admins assign each employee a **basic** or
  **advanced** tier from the Users panel (create-form field + per-row dropdown).
- **Per-tier daily limits** — org-admins set the daily AI-query limit for each
  tier for their company (`GET/PUT /v1/admin/users/tier-limits`).
- **Quota enforcement** — only expensive queries (LLM/RAG) count against the
  limit; cheap SQL look-ups (price, inventory…) are always free. When an
  employee hits their daily cap they get a clear "daily limit reached" message
  and a chip; counters live in Redis (24h TTL) and fail open if Redis is down.
- Super-admins are unlimited.

## [1.5.0] — 2026-07-10

### Added — Super-admin console (Phase 3)
- **Platform console** (super-admin only, new "🏛️ Platform" nav) to run the SaaS:
  - **Organizations** — list all tenants with plan, employees (used/max), queries
    today (used/quota), and active status; change a company's plan from a dropdown;
    suspend/reactivate; create a new company together with its first admin.
  - **Plans** — create plans and inline-edit their limits (max employees, daily
    query quota, monthly price).
- `is_super_admin` is now returned on login so the UI shows the right console.
- `require_super_admin` guard on all `/v1/superadmin/*` endpoints (org-admins get 403).

## [1.4.0] — 2026-07-10

### Added — Multi-tenant SaaS foundation
- **Organizations (tenants) + Plans** — every user and project belongs to an
  organization; plans (Basic/Advanced/Enterprise) are data-driven and carry
  limits (`max_employees`, `daily_llm_quota`).
- **Tenant isolation** — all reads (projects, query engine, RAG, knowledge,
  analytics, documents) are scoped to the caller's organization. One tenant can
  never see another's data; cross-tenant access returns 404.
- **Super-admin** role (the SaaS owner) — no organization, can operate across all
  tenants; seeded as `owner@engine.local`.
- **Employee cap enforcement** — creating a user beyond the plan's
  `max_employees` is rejected with an upgrade prompt.
- Query log now records `organization_id` for per-tenant usage analytics.

### Changed
- LLM project-disambiguation now only fires on a fuzzy near-miss, saving an API
  call (and avoiding latency) on clearly-unrelated queries.
- Existing data migrates into a default "Chaahat Homes" organization on upgrade.

## [1.3.0] — 2026-07-10

### Added
- **Real Gemini embeddings for RAG** — `gemini-embedding-001` at 768-dim (via
  `output_dimensionality`) so brochure search is truly semantic (e.g. "walk my
  dog" finds the pet zone). Embedding model is configurable and merged through
  runtime config.
- **Re-index all** — `POST /v1/admin/knowledge/reindex-all` re-embeds every
  document with the current provider (run after switching embeddings).
- **Model dropdowns in AI Settings** — LLM and embedding model pickers populated
  live from your Gemini account (`GET /v1/admin/settings/models`), with a
  "Custom…" escape hatch.

### Fixed
- **Expired-token handling** — an authenticated request that returns 401 now
  clears the session and redirects to login instead of hanging on "Loading…".

## [1.2.0] — 2026-07-10

### Added
- **Real Gemini support hardened** — the engine now works with current Gemini
  "thinking" models. Response parsing safely handles empty visible parts
  (falls back to candidate parts), and the default model is `gemini-flash-latest`
  (the old `gemini-1.5-flash` is retired).

### Changed
- **Smarter grounding prompt** — the LLM now presents whatever facts the context
  contains and marks only the specific missing detail as unavailable, instead of
  refusing the whole answer. It still never invents figures (Constitution §8).
- Connection-test token budget raised so thinking models can respond.

## [1.1.1] — 2026-07-10

### Fixed
- **Wrong-project answers via session memory** — asking about an unknown project
  (e.g. "gic price") no longer silently returns the *previous* project's data.
  The engine now says "Information not available — did you mean: …?" and lists
  the known projects (Constitution §8, no guessing).
- **Substring over-matching** — a "Palm Greens" query no longer also matches
  "Green Valley" ("green" inside "greens"). Project linking now uses whole-word
  matching.

### Added
- **Typo-tolerant project matching** — layered linking (exact → fuzzy → LLM).
  Misspellings like "gold hils" resolve to "Golf Hills"; the answer shows a
  "Showing results for Golf Hills" note and a "corrected spelling" chip. Fuzzy
  works offline; LLM disambiguation kicks in only with a real provider.
- Regression tests for entity linking (`tests/test_intent.py`).

## [1.1.0] — 2026-07-10

### Added
- **Price updates** — update an existing configuration's price from the admin
  panel. The old price is kept in history (versioned `effective_from`/`effective_to`)
  and the new one becomes current immediately (`PUT /v1/admin/configurations/{id}/price`).
- **Inventory updates** — change available/total units for a configuration
  (`PUT /v1/admin/configurations/{id}/inventory`).
- **Config editor UI** — Admin → Manage Data → "Update Price / Stock" lists every
  configuration with its current price and stock for inline editing.
- **Brochure replace** — upload a new PDF for an existing document; the old
  brochure's chunks are deactivated so RAG only serves the latest
  (`POST /v1/admin/knowledge/documents/{id}/replace`). Added "Replace" action to
  the Documents tab.
- `GET /v1/admin/projects/{id}/configurations` — list configs with current price + inventory.

## [1.0.0] — 2026-07-10

First complete version — the full hybrid engine, web client, and admin suite.

### Added
- **Hybrid query pipeline** — Intent → Database → Calculation → RAG → LLM → Renderer
  (Golden Rule: deterministic sources answer first; LLM only reasons over facts).
- **SQL-first schema** — builders, projects, configurations, versioned prices,
  payment plans, inventory, offers, documents, users, audit log.
- **RAG subsystem** — PDF ingestion → chunk → embed → pgvector; retrieval with
  page-level citations; provider-aware similarity threshold.
- **Deterministic calculation engine** — total cost, payment schedule, EMI, ROI,
  GST, PLC, rental yield, stamp duty.
- **LLM provider abstraction** — swap Gemini/Claude/OpenAI/Ollama by config only;
  runs fully offline in `mock` mode with no key.
- **Session memory** — follow-up questions keep project context.
- **Structured responses** — cards, tables, timelines, checklists + source
  citations (Project, Source, Page, Last Updated, Confidence).
- **AI Settings** — admins set provider/model/key from the UI (key stays server-side).
- **Smart features** — side-by-side comparison, budget/config recommendations,
  follow-up suggestion chips, voice input.
- **Admin & data** — project/config/payment-plan CRUD, CSV bulk import, users,
  builders, configurable document types, audit trail.
- **Monitoring** — analytics dashboard (queries, miss rate, latency, top intents),
  Knowledge/RAG health (chunks, embeddings, coverage), System Health page.
- **Web client** — React + Vite sales UI; minimal, fast, card/table based.
- **Deployment** — Docker Compose (FastAPI + PostgreSQL/pgvector + Redis).

[Unreleased]: https://github.com/OWNER/REPO/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/OWNER/REPO/releases/tag/v1.0.0
