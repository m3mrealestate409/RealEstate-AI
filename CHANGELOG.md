# Changelog

All notable changes to the Chaahat Homes AI Knowledge Engine are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/); this
project uses [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH).

## [Unreleased]

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
