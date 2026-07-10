# Changelog

All notable changes to the Chaahat Homes AI Knowledge Engine are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/); this
project uses [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH).

## [Unreleased]

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
