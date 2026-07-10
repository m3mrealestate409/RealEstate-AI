# Product Requirements Document (PRD)
## AI Knowledge Engine — Chaahat Homes

**Version:** 1.0
**Status:** Draft for Approval
**Last Updated:** 2026-07-09
**Owner:** Product / Engineering
**Governing Document:** [Project Constitution v1.0](#appendix-a--project-constitution-reference)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Personas & Users](#4-personas--users)
5. [Scope](#5-scope)
6. [Core Principles (Non-Negotiable)](#6-core-principles-non-negotiable)
7. [System Architecture](#7-system-architecture)
8. [The Hybrid Query Pipeline](#8-the-hybrid-query-pipeline)
9. [Intent Detection & Routing](#9-intent-detection--routing)
10. [Data Model (SQL-First)](#10-data-model-sql-first)
11. [RAG Subsystem](#11-rag-subsystem)
12. [Calculation Engine](#12-calculation-engine)
13. [LLM Provider Abstraction Layer](#13-llm-provider-abstraction-layer)
14. [Response Rendering Layer](#14-response-rendering-layer)
15. [API Design (API-First)](#15-api-design-api-first)
16. [Module Breakdown](#16-module-breakdown)
17. [Security & Compliance](#17-security--compliance)
18. [Non-Functional Requirements](#18-non-functional-requirements)
19. [Recommended Technology Stack](#19-recommended-technology-stack)
20. [Delivery Roadmap](#20-delivery-roadmap)
21. [Risks & Mitigations](#21-risks--mitigations)
22. [Open Questions](#22-open-questions)
23. [Appendix A — Project Constitution Reference](#appendix-a--project-constitution-reference)

---

## 1. Executive Summary

The AI Knowledge Engine is an enterprise-grade, API-first knowledge retrieval system for the real estate industry. It allows employees (primarily sales staff) to ask natural-language questions about projects and receive accurate, structured, source-cited answers within 5 seconds.

**This is not a chatbot and not a plain RAG app.** It is a *hybrid reasoning engine* that combines a structured database, deterministic business logic, vector search, and an LLM reasoning layer to produce trustworthy answers. The guiding law is the **Golden Rule**:

> **Never use AI when deterministic software can provide a more accurate answer.**

The engine runs as an independent service exposed entirely through APIs, so future clients (CRM, Website, WhatsApp, Android, iOS) can consume the same intelligence without duplicating logic.

---

## 2. Problem Statement

Real estate sales teams need instant, correct answers to project questions (price, payment plan, possession, amenities, comparisons). Today this information lives across brochures, spreadsheets, and people's memory. Consequences:

- **Stale / wrong data** — prices quoted from old brochures.
- **Slow retrieval** — staff dig through PDFs during live client calls.
- **Inconsistent answers** — different employees give different figures.
- **No source of truth** — no citation, no confidence, no "last updated."

A naive "chatbot over PDFs" makes this *worse*: LLMs hallucinate prices and payment plans, and PDFs hold data that changes weekly. The solution must keep volatile structured facts in a database and reserve AI strictly for reasoning.

---

## 3. Goals & Success Metrics

### 3.1 Primary Goals
1. Accurate, source-cited answers to natural-language queries.
2. Sub-5-second response time for common queries.
3. Latest prices/payment plans/inventory always sourced from SQL, never PDFs.
4. Modular architecture where any module (incl. the LLM provider) is replaceable via config.
5. API-first so CRM/WhatsApp/mobile can integrate later.

### 3.2 Success Metrics (Definition of Success — V1)

| # | Metric | Target |
|---|--------|--------|
| 1 | Answer latency (P95, common queries) | ≤ 5 s |
| 2 | Source citation present on factual answers | 100% |
| 3 | Latest price served from SQL (not RAG/LLM) | 100% |
| 4 | Document knowledge served from RAG | 100% |
| 5 | Structured response format used when data is structured | 100% |
| 6 | Hallucinated facts (fabricated price/plan) | 0 |
| 7 | LLM provider swap without business-logic change | Config-only |
| 8 | CRM-consumable via public API | Yes |

### 3.3 Non-Goals (V1)
- Permanent per-user long-term memory (session memory only — see §6).
- Direct dependency on a single LLM vendor.
- Client-side AI or client-side DB access.
- Free-form creative chat behavior.

---

## 4. Personas & Users

| Persona | Description | Primary Need |
|---------|-------------|--------------|
| **Sales Executive** (primary) | On calls with clients; not technical | Fast, correct, structured answers; comparisons |
| **Sales Manager** | Oversees team; reviews projects | Comparisons, summaries, up-to-date inventory |
| **Admin / Data Manager** | Maintains projects, prices, documents | CRUD on structured data; upload/re-index brochures; audit trail |
| **Future API Consumer** | CRM / WhatsApp bot / mobile app | Programmatic access to the same engine |

**UI Philosophy:** Employees are sales professionals, not engineers. UI must be minimal, fast, simple, readable — tables, cards, badges, status chips over long paragraphs.

---

## 5. Scope

### 5.1 In Scope (V1)
- Hybrid query pipeline: Intent → DB → Calculation → RAG → LLM → Renderer.
- SQL schema for all structured/volatile fields.
- PDF ingestion + vector-based RAG for document-only knowledge.
- Deterministic calculation engine (cost, payment plan, EMI, ROI, etc.).
- LLM provider abstraction (Gemini/Claude/GPT/OpenRouter/Ollama/DeepSeek/Qwen/Llama).
- Session-scoped conversation memory.
- Structured response rendering (cards/tables/timeline/checklist).
- Role-based auth, audit logging, admin panel.
- Public REST/JSON API + one web client.
- Source citation on every factual answer.

### 5.2 Out of Scope (V1)
- Long-term user memory / personalization.
- WhatsApp / mobile / CRM clients (APIs designed for them, built later).
- Automated price scraping from external portals.
- Multi-language answering beyond the primary language (can be a fast-follow).

---

## 6. Core Principles (Non-Negotiable)

These derive directly from the Constitution and act as acceptance gates for every feature.

1. **Golden Rule** — Deterministic software beats AI whenever it can answer more accurately.
2. **SQL-First** — Volatile structured facts (price, payment plan, inventory, possession, RERA, builder, config, area, status, offer, launch date) live in SQL, never *only* in PDFs.
3. **RAG-Only-for-Documents** — Specifications, amenities, floor plan details, master plan, club facilities, legal/brochure text. Never for frequently-changing data.
4. **LLM = Reasoning Only** — Understand intent, merge SQL+RAG, compare, summarize, explain, converse. Never a database. Never invents facts.
5. **Hallucination Policy** — If not found: *"Information not available in the current knowledge base."* Never guess/estimate/fabricate.
6. **Citation Policy** — Every answer carries Project Name, Source, Page (if brochure), Last Updated, Confidence Score.
7. **Session Memory Only** — Context within a session; never replaces DB lookup; no permanent memory in V1.
8. **LLM Independence** — App talks to a Provider Layer, not a vendor SDK directly.
9. **API-First** — Every capability exposed via API; web app is just one client.
10. **Modularity** — Each module independently replaceable.
11. **Deterministic Calculation** — All math in backend functions; AI only *explains* results.
12. **Security** — No keys in frontend, no client DB access, RBAC everywhere, audit logging on admin changes.

---

## 7. System Architecture

### 7.1 Logical Architecture (Layered)

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                  │
│   Web App (V1)  │  CRM  │  Website  │  WhatsApp  │  Mobile        │
└───────────────────────────────┬─────────────────────────────────┘
                                 │  HTTPS / JSON (API-First)
┌───────────────────────────────▼─────────────────────────────────┐
│                        API GATEWAY LAYER                          │
│   AuthN/AuthZ (RBAC) · Rate Limiting · Request Validation ·       │
│   Audit Logging · Versioned Endpoints (/v1)                       │
└───────────────────────────────┬─────────────────────────────────┘
                                 │
┌───────────────────────────────▼─────────────────────────────────┐
│                     ORCHESTRATION CORE                            │
│                                                                   │
│   ┌──────────────┐   ┌──────────────┐   ┌────────────────────┐   │
│   │   Intent     │──▶│   Query      │──▶│  Response          │   │
│   │   Detection  │   │   Router     │   │  Renderer          │   │
│   └──────────────┘   └──────┬───────┘   └────────────────────┘   │
│                             │                                     │
│        ┌────────────┬───────┼────────┬─────────────┐             │
│        ▼            ▼       ▼        ▼             ▼              │
│  ┌──────────┐ ┌──────────┐ ┌──────┐ ┌───────┐ ┌────────────┐    │
│  │ Database │ │  Calc    │ │ RAG  │ │  LLM  │ │  Session   │    │
│  │ Service  │ │  Engine  │ │Service│ │ Layer │ │  Memory    │    │
│  └────┬─────┘ └──────────┘ └──┬───┘ └───┬───┘ └────────────┘    │
└───────┼──────────────────────┼─────────┼───────────────────────┘
        │                      │         │
   ┌────▼─────┐          ┌─────▼────┐ ┌──▼──────────────────┐
   │  SQL DB  │          │ Vector   │ │ LLM Provider Layer  │
   │(Postgres)│          │  Store   │ │ Gemini│Claude│GPT│  │
   │          │          │(pgvector)│ │ OpenRouter│Ollama│…│  │
   └──────────┘          └──────────┘ └─────────────────────┘
```

### 7.2 Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Deterministic-first routing | Intent → DB → Calc → RAG → LLM | Constitution Golden Rule; accuracy + cost |
| Structured store | Relational SQL (PostgreSQL) | ACID, joins, single source of truth for volatile data |
| Vector store | pgvector (in same Postgres) | One datastore, lower ops cost; swappable to Qdrant/Weaviate later |
| LLM access | Provider abstraction interface | Constitution LLM Independence Policy |
| Calculation | Pure backend functions | Constitution Calculation Policy — no LLM math |
| Interface | REST/JSON, versioned | API-First; easy multi-client integration |
| Memory | Session store (Redis) | Session-only policy; fast context |

---

## 8. The Hybrid Query Pipeline

Every query flows through a fixed decision order. AI is the *last* resort, not the first.

```
                    ┌──────────────────┐
   User Query  ───▶ │ Intent Detection │
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐   Structured fact?
                    │   Query Router   │───────────────┐
                    └────────┬─────────┘               │
                             │                          ▼
        ┌────────────────────┼──────────────┐   ┌──────────────┐
        │                    │              │   │  DATABASE    │ ✔ price, plan,
        ▼                    ▼              ▼   │  (SQL)       │   possession,
  ┌───────────┐      ┌─────────────┐  ┌────────┐└──────┬───────┘   inventory…
  │   RAG     │      │ Calculation │  │  LLM   │       │
  │ (docs)    │      │  Engine     │  │(reason)│       │
  └─────┬─────┘      └──────┬──────┘  └───┬────┘       │
        │                   │             │            │
        └───────────────────┴─────────────┴────────────┘
                             ▼
                   ┌───────────────────┐
                   │ Answer Composer   │  merge facts, attach citations,
                   │  + Citations      │  compute confidence score
                   └─────────┬─────────┘
                             ▼
                   ┌───────────────────┐
                   │ Response Renderer │  choose card/table/timeline/…
                   └─────────┬─────────┘
                             ▼
                        JSON Response
```

### 8.1 Routing Rules by Data Type (from Golden Rule)

| Query Type | Handler | Source of Truth |
|------------|---------|-----------------|
| Price | Database | SQL |
| Payment Plan | Database | SQL |
| Possession | Database | SQL |
| Builder Name | Database | SQL |
| Inventory | Database | SQL |
| RERA / Status / Offer / Launch Date | Database | SQL |
| Calculation (Cost, EMI, ROI, GST, PLC…) | Calculation Engine | Deterministic functions |
| Amenities | RAG | Documents |
| Specifications / Floor Plan / Master Plan | RAG | Documents |
| Legal / Brochure text | RAG | Documents |
| Comparison | LLM (over SQL+RAG) | Reasoning |
| Summary | LLM | Reasoning |
| Recommendation | LLM | Reasoning |

---

## 9. Intent Detection & Routing

### 9.1 Responsibilities
- Classify the query into one or more **intents** (price, payment_plan, amenities, comparison, calculation, summary, …).
- Extract **entities**: project name(s), configuration (e.g., 3BHK), area, budget, numbers for calculation.
- Resolve entities against SQL (canonical project IDs) and against **session memory** (e.g., "Payment Plan?" after "Golf Hills price" → project = Golf Hills).
- Emit a **routing plan**: ordered list of handlers to invoke.

### 9.2 Approach
- **Hybrid classifier:** deterministic rules + keyword/regex matching first (cheap, fast), fall back to a lightweight LLM classifier only when ambiguous.
- **Entity linking:** fuzzy match project names against the SQL `projects` table (handles typos/aliases).
- **Multi-intent:** "Compare Golf Hills and Palm Greens price and amenities" → {comparison, price(DB), amenities(RAG)} → merged by LLM.

### 9.3 Session Memory Contract
- Stores last N turns: resolved project(s), config, last intent.
- Used **only** to fill missing entities — never to answer from cache. Every factual answer re-queries SQL/RAG.

---

## 10. Data Model (SQL-First)

All volatile, structured fields live here. This is the authoritative source for price/plan/inventory/possession.

### 10.1 Core Entities (initial schema)

```sql
-- Builders / Developers
CREATE TABLE builders (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    rera_id         TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Projects
CREATE TABLE projects (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    slug            TEXT UNIQUE NOT NULL,
    builder_id      BIGINT REFERENCES builders(id),
    city            TEXT,
    locality        TEXT,
    rera_number     TEXT,
    project_status  TEXT,           -- Launched | Under Construction | Ready to Move
    launch_date     DATE,
    possession_date DATE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_projects_name_trgm ON projects USING gin (name gin_trgm_ops); -- fuzzy match

-- Configurations (unit types)
CREATE TABLE configurations (
    id              BIGSERIAL PRIMARY KEY,
    project_id      BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    type            TEXT,           -- 2BHK, 3BHK, Villa, Plot
    carpet_area     NUMERIC,        -- sq ft
    built_up_area   NUMERIC,
    super_area      NUMERIC,
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Prices (versioned — never overwrite history)
CREATE TABLE prices (
    id              BIGSERIAL PRIMARY KEY,
    configuration_id BIGINT REFERENCES configurations(id) ON DELETE CASCADE,
    base_price      NUMERIC NOT NULL,       -- per sq ft or total (define unit)
    price_unit      TEXT NOT NULL,          -- 'per_sqft' | 'total'
    plc             NUMERIC,                -- preferential location charge
    gst_percent     NUMERIC,
    effective_from  DATE NOT NULL,
    effective_to    DATE,                   -- null = current
    source          TEXT,                   -- e.g. 'Price List Jul-2026'
    created_by      BIGINT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Payment Plans
CREATE TABLE payment_plans (
    id              BIGSERIAL PRIMARY KEY,
    project_id      BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    name            TEXT,                   -- e.g. '10:80:10', 'CLP', 'Subvention'
    description     TEXT,
    is_active       BOOLEAN DEFAULT true,
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE payment_plan_milestones (
    id              BIGSERIAL PRIMARY KEY,
    payment_plan_id BIGINT REFERENCES payment_plans(id) ON DELETE CASCADE,
    sequence        INT,
    label           TEXT,                   -- 'On Booking', 'On Completion'
    percent         NUMERIC
);

-- Inventory
CREATE TABLE inventory (
    id              BIGSERIAL PRIMARY KEY,
    configuration_id BIGINT REFERENCES configurations(id) ON DELETE CASCADE,
    total_units     INT,
    available_units INT,
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Offers
CREATE TABLE offers (
    id              BIGSERIAL PRIMARY KEY,
    project_id      BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    title           TEXT,
    details         TEXT,
    valid_from      DATE,
    valid_to        DATE,
    is_active       BOOLEAN DEFAULT true
);

-- Documents (source registry for RAG)
CREATE TABLE documents (
    id              BIGSERIAL PRIMARY KEY,
    project_id      BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    title           TEXT,
    doc_type        TEXT,                   -- brochure | legal | floor_plan | master_plan
    file_path       TEXT,
    version         INT DEFAULT 1,
    uploaded_at     TIMESTAMPTZ DEFAULT now(),
    indexed_at      TIMESTAMPTZ
);

-- Users & Roles (RBAC)
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    name            TEXT,
    role            TEXT NOT NULL,          -- admin | manager | sales
    password_hash   TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Audit Log (all admin changes)
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(id),
    action          TEXT,                   -- CREATE | UPDATE | DELETE
    entity          TEXT,                   -- table name
    entity_id       BIGINT,
    before          JSONB,
    after           JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### 10.2 Design Notes
- **Prices are versioned** (`effective_from`/`effective_to`) — the engine always reads the current row, but history is preserved and citable ("Last Updated").
- **Every factual table has `updated_at`** to satisfy the Citation Policy's "Last Updated Date."
- **Fuzzy project matching** via `pg_trgm` for entity linking on typos/aliases.
- **`documents` table links RAG chunks back to a project and version** so citations resolve to Project + Source + Page.

---

## 11. RAG Subsystem

RAG answers **document-only** knowledge (amenities, specifications, floor plan details, master plan, club facilities, legal/brochure text). It must never serve volatile structured data.

### 11.1 Ingestion Pipeline

```
PDF Upload ──▶ Text + Layout Extraction ──▶ Chunking ──▶ Embedding ──▶ Vector Store
   │              (page numbers kept)       (semantic,     (provider    (pgvector)
   │                                         ~300–800 tok)  abstracted)
   └──▶ documents table row (project_id, version, page map)
```

- **Page numbers are preserved per chunk** → required for Citation Policy.
- **Chunk metadata:** `{ project_id, document_id, doc_type, page, version }`.
- **Re-index on new document version;** stale versions deactivated so old brochure text is never retrieved.

### 11.2 Retrieval
- Filter vector search by `project_id` (and `doc_type` if intent implies it).
- Top-k retrieval with a similarity threshold; if nothing above threshold → contributes "not found" (feeds Hallucination Policy).
- Retrieved chunks passed to LLM **only as grounding context**, with strict instruction: answer only from provided context; else return the not-available message.

### 11.3 RAG Chunk Table

```sql
CREATE TABLE rag_chunks (
    id            BIGSERIAL PRIMARY KEY,
    document_id   BIGINT REFERENCES documents(id) ON DELETE CASCADE,
    project_id    BIGINT REFERENCES projects(id),
    page          INT,
    content       TEXT,
    embedding     VECTOR(1536),      -- dimension depends on embedding model
    version       INT,
    is_active     BOOLEAN DEFAULT true
);
CREATE INDEX idx_rag_embedding ON rag_chunks USING ivfflat (embedding vector_cosine_ops);
```

---

## 12. Calculation Engine

All numeric computation is done by **pure, tested backend functions** — never by LLM language reasoning. The LLM may only *explain* the result.

### 12.1 Required Calculators (V1)
| Calculator | Inputs (from SQL/user) | Output |
|------------|------------------------|--------|
| Total Cost | base price, area, PLC, GST, charges | itemized total |
| Payment Plan Schedule | plan milestones %, total cost | amount per milestone |
| GST | taxable value, rate | tax amount |
| PLC | base, location premium | charge |
| EMI | principal, rate, tenure | monthly EMI |
| ROI | investment, projected value | % return |
| Rental Yield | annual rent, property value | % yield |
| Stamp Duty | value, state rate | duty amount |

### 12.2 Contract
- Deterministic, unit-tested, no side effects.
- Inputs pulled from SQL where possible (price, area, plan %) — user supplies only what SQL cannot (e.g., loan tenure).
- Returns structured, itemized breakdown → rendered as a table/card; LLM adds a plain-language explanation if asked.

---

## 13. LLM Provider Abstraction Layer

The application **never** imports a vendor SDK directly. It calls an internal `LLMProvider` interface; the concrete provider is chosen by configuration.

### 13.1 Interface (illustrative)

```
interface LLMProvider {
  complete(request: {
    system: string,
    messages: Message[],
    tools?: ToolSpec[],
    temperature?: number,
    maxTokens?: number,
  }): Promise<LLMResponse>;

  embed(texts: string[]): Promise<number[][]>;   // may be a separate EmbeddingProvider
}
```

- Supported providers: **Gemini, Claude, GPT, OpenRouter, Ollama, DeepSeek, Qwen, Llama**, future models.
- Provider selected via env/config (`LLM_PROVIDER=claude`, `LLM_MODEL=...`).
- **No business logic references a specific vendor.** Swapping providers = config change only.
- Keys live server-side only (Security Policy).
- Optional: routing by task (cheap model for intent classification, stronger model for comparison/summary) — still behind the abstraction.

### 13.2 Guardrails Enforced Around the LLM
- System prompt hard-codes: *answer only from provided SQL/RAG context; if absent, return the not-available message; never fabricate figures.*
- Structured-output mode where possible (JSON) to feed the renderer.
- All factual claims must trace to a supplied source object.

---

## 14. Response Rendering Layer

The engine returns **structured, render-ready JSON**; the client renders it. Format is chosen by an ease-of-understanding priority.

### 14.1 Format Priority (Constitution §17)
1. **Cards** (default for single-project facts)
2. **Tables** (multi-field / comparison)
3. **Timeline** (possession, launch, milestones)
4. **Checklist** (amenities, documents)
5. **Paragraph** (last resort — explanations only)

### 14.2 Response Envelope (all answers)

```json
{
  "answer_type": "card | table | timeline | checklist | paragraph",
  "content": { "...": "render-ready structured payload" },
  "citations": [
    {
      "project": "Golf Hills",
      "source": "Price List Jul-2026 (SQL)",
      "page": null,
      "last_updated": "2026-07-01",
      "confidence": 0.98
    }
  ],
  "handlers_used": ["database"],
  "session_id": "…",
  "not_available": false
}
```

- Every factual response carries **Project, Source, Page (if brochure), Last Updated, Confidence** — enforced at the composer, not left to the LLM.
- `not_available: true` with the standard message when data is missing.

---

## 15. API Design (API-First)

Versioned REST/JSON. The web app and all future clients use the **same** endpoints.

### 15.1 Core Endpoints (V1)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/v1/auth/login` | Authenticate, return token |
| `POST` | `/v1/query` | Main NL query → structured answer (the engine) |
| `GET`  | `/v1/projects` | List/search projects |
| `GET`  | `/v1/projects/{id}` | Project detail (structured) |
| `GET`  | `/v1/projects/{id}/price` | Current price (SQL) |
| `GET`  | `/v1/projects/{id}/payment-plan` | Payment plan (SQL) |
| `GET`  | `/v1/projects/{id}/inventory` | Inventory (SQL) |
| `POST` | `/v1/calculate/{type}` | Calculation engine (cost, emi, roi…) |
| `POST` | `/v1/admin/projects` | Create project (admin) |
| `PUT`  | `/v1/admin/projects/{id}` | Update project (admin, audited) |
| `POST` | `/v1/admin/documents` | Upload + index brochure |
| `GET`  | `/v1/admin/audit` | Audit log (admin) |
| `GET`  | `/v1/analytics/queries` | Query analytics |

### 15.2 `POST /v1/query` (heart of the system)

**Request:**
```json
{ "query": "Golf Hills 3BHK price and payment plan", "session_id": "abc-123" }
```

**Response:** the [Response Envelope](#142-response-envelope-all-answers) above.

### 15.3 API Conventions
- Bearer-token auth; RBAC enforced per endpoint.
- Consistent error shape `{ error: { code, message } }`.
- Idempotent GETs; audited mutations.
- Versioned under `/v1`; additive changes preferred.

---

## 16. Module Breakdown

Each module is independently replaceable (Modular Development Policy).

| Module | Responsibility | Key Dependencies |
|--------|----------------|------------------|
| **Authentication** | Login, tokens, RBAC | users table |
| **Project Management** | CRUD projects/config/price/plan/inventory | SQL, audit |
| **PDF Processing** | Extract, chunk, embed, version documents | Embedding provider, vector store |
| **RAG** | Retrieve document knowledge with citations | pgvector, documents |
| **Chat / Orchestration** | Intent → route → compose → render | all services |
| **Calculation Engine** | Deterministic financial math | SQL inputs |
| **LLM Provider Layer** | Vendor-agnostic completions/embeddings | external LLM APIs |
| **Admin Panel** | Manage data, upload docs, view audit | Project Mgmt, PDF |
| **Analytics** | Query volume, latency, intents, misses | logs |
| **API** | Public interface for all clients | all modules |

---

## 17. Security & Compliance

- **No API keys in the frontend.** All LLM/DB access is server-side only.
- **No direct DB access from clients.** Everything through APIs.
- **RBAC everywhere** — `admin` / `manager` / `sales` roles; endpoint-level enforcement.
- **Audit logging** on every admin mutation (before/after JSON in `audit_log`).
- **Transport:** HTTPS/TLS; tokens with expiry.
- **Secrets:** environment/secret manager, never in repo.
- **Input validation** and rate limiting at the gateway.
- **PII:** minimal; client data (if later added) access-controlled and logged.

---

## 18. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Performance** | P95 ≤ 5 s for common queries; DB-only answers ≪ 1 s |
| **Scalability** | Stateless API tier (horizontal scale); Postgres + read replicas as needed |
| **Cost** | Prefer deterministic paths (Golden Rule) to minimize LLM calls; cache embeddings; route cheap models for classification |
| **Maintainability** | Modular, documented, tested calculators, provider abstraction |
| **Reliability** | Graceful degradation: if LLM down, DB/calc/RAG factual answers still served |
| **Observability** | Structured logs, latency metrics, intent/miss analytics |
| **Portability** | Vector store swappable (pgvector → Qdrant/Weaviate); provider swappable |

---

## 19. Recommended Technology Stack

> Recommendations — open for confirmation in §22. Chosen for low ops cost, speed, and modularity.

| Layer | Recommendation | Alternatives |
|-------|----------------|--------------|
| Backend runtime | **Python (FastAPI)** — strong AI ecosystem | Node.js (NestJS) |
| Structured DB | **PostgreSQL** | — |
| Vector store | **pgvector** (same Postgres) | Qdrant, Weaviate |
| Session memory | **Redis** | In-DB table |
| LLM providers | Abstraction over Gemini/Claude/GPT/OpenRouter/Ollama/DeepSeek/Qwen/Llama | — |
| PDF extraction | PyMuPDF / pdfplumber (+ OCR fallback) | Unstructured.io |
| Web client | **React** (minimal, card/table UI) | Next.js |
| Auth | JWT + RBAC | Session cookies |
| Deployment | Docker containers | — |

**Why FastAPI + Postgres + pgvector:** single primary datastore (lower operating cost per Constitution), mature Python AI tooling, easy provider abstraction, and clean async APIs for the 5-second latency target.

---

## 20. Delivery Roadmap

### Phase 0 — Foundation (Week 1–2)
- Repo, Docker, Postgres + pgvector, config/secrets, LLM provider interface (1 provider wired).
- Auth + RBAC + audit log skeleton.

### Phase 1 — SQL-First Core (Week 2–4)
- Schema + admin CRUD for projects/config/price/plan/inventory/offers.
- Deterministic endpoints: price, payment plan, inventory, possession.
- Calculation engine (cost, payment schedule, EMI, ROI, GST, PLC, stamp duty, rental yield) + unit tests.

### Phase 2 — RAG (Week 4–6)
- PDF ingestion → chunk → embed → pgvector with page/version metadata.
- Retrieval with project filter + threshold + citation mapping.

### Phase 3 — Orchestration Engine (Week 6–8)
- Intent detection + entity linking + session memory (Redis).
- Query router (DB → Calc → RAG → LLM) + answer composer with citations & confidence.
- Response renderer (card/table/timeline/checklist).
- `POST /v1/query` end-to-end.

### Phase 4 — Web Client + Admin Panel (Week 8–10)
- Minimal sales UI (cards/tables/badges).
- Admin panel (data management, doc upload/index, audit view).

### Phase 5 — Analytics, Hardening, Launch (Week 10–12)
- Query analytics, latency dashboards, miss tracking.
- Load testing to 5-second SLA, security review, docs.
- **V1 acceptance against §3.2 metrics.**

---

## 21. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM hallucinates prices | Wrong quotes to clients | SQL-first routing; LLM never answers volatile facts; strict grounding prompts |
| Stale data in RAG | Outdated answers | Volatile data in SQL only; document versioning; deactivate old chunks |
| Vendor lock-in | Hard/expensive swaps | Provider abstraction; config-only switch |
| Latency > 5 s | Poor UX on calls | Deterministic fast paths; caching; cheap classifier; async |
| Entity mis-linking (wrong project) | Wrong answer | Fuzzy match + confirmation on low confidence; session context |
| Cost creep from LLM usage | Higher opex | Route deterministic first; small models for classification; caching |
| Ambiguous multi-intent queries | Incomplete answers | Multi-intent routing plan; ask-to-clarify on low confidence |

---

## 22. Decisions & Open Questions

### 22.1 Confirmed Decisions (2026-07-09)
1. **Backend language** — ✅ **Python + FastAPI**.
2. **Initial LLM provider** — ✅ **Gemini** (wired behind the LLM Provider Abstraction Layer; swappable by config).
3. **Vector store** — ✅ **pgvector** (in the same PostgreSQL instance).
4. **Primary answer language** — ✅ **English + Hindi/Hinglish** (structured data stays as-is; LLM explanations/summaries may respond in Hindi/Hinglish per user).

### 22.2 Still Open
1. **Embedding model** — hosted Gemini embeddings (dimension?) vs local via Ollama for cost? (affects `VECTOR(n)` size).
2. **Currency/number formatting & locale** — INR formatting, lakh/crore display?
3. **Price unit convention** — per sq ft vs total; standardize across projects?
4. **Hosting** — cloud provider / on-prem preference for cost target?

---

## Appendix A — Project Constitution Reference

This PRD implements **Project Constitution v1.0 (AI Knowledge Engine)**. Every requirement here traces to a Constitution policy: Mission (§1), Core Philosophy (§2), Golden Rule (§3), Hybrid Architecture (§4), SQL-First (§5), RAG (§6), AI (§7), Hallucination (§8), Citation (§9), Conversation Memory (§10), Long-Term Memory (§11), LLM Independence (§12), API-First (§13), Modular Development (§14), UI Philosophy (§16), Response Rendering (§17), Calculation (§18), Security (§19), Definition of Success (§20), Final Principle.

> **Final Principle:** The AI Engine must always behave like a reliable company knowledge expert, not a creative chatbot.
