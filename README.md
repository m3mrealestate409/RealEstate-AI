# Chaahat Homes — AI Knowledge Engine

An enterprise-grade **hybrid AI Knowledge Engine** for real estate. Not a chatbot,
not a plain RAG app — it combines a **SQL database + deterministic business logic +
vector RAG + LLM reasoning** to answer natural-language questions accurately, fast,
and with sources.

> **Golden Rule:** Never use AI when deterministic software can answer more accurately.

Governed by the [Project Constitution](#) and the full [PRD.md](PRD.md).

---

## Architecture (the hybrid pipeline)

```
Query → Intent Detection → Database → Calculation Engine → RAG → LLM → Response Renderer
```

- **Price / payment plan / possession / inventory / builder / status / offer** → SQL (source of truth)
- **Calculations (cost, EMI, ROI, GST, PLC, stamp duty…)** → deterministic backend functions
- **Amenities / specs / floor plan / legal / brochure text** → RAG (documents only)
- **Comparison / summary / recommendation** → LLM (reasons over retrieved facts, never invents)

Every factual answer carries **Project, Source, Page, Last Updated, Confidence**.
If nothing is found: *"Information not available in the current knowledge base."*

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.12 · FastAPI |
| Structured DB | PostgreSQL 16 |
| Vector store | pgvector (same Postgres) |
| Session memory | Redis |
| LLM (V1) | Gemini — behind a provider abstraction (swap by config) |
| Embeddings | Gemini or deterministic local (mock) |

**Runs fully offline in `mock` mode** — no API key needed to boot, seed, and test the whole engine.

---

## Quick Start (Docker — recommended)

```bash
# 1. Copy env (defaults run in mock mode, no keys needed)
cp .env.example .env

# 2. Build & start everything (Postgres + pgvector + Redis + API)
docker compose up --build

# 3. Open the API docs
#    http://localhost:8001/docs
#    http://localhost:8001/health
```

On first boot the API auto-creates the schema and seeds an admin + two demo
projects (**Golf Hills**, **Palm Greens**) with full prices, payment plans,
inventory, and offers.

### Log in & query

```bash
# Login (default admin)
curl -X POST http://localhost:8001/v1/auth/login \
  -d "username=admin@chaahat.local&password=admin123"

# Ask the engine (use the token from above)
curl -X POST http://localhost:8001/v1/query \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"Golf Hills 3BHK price and payment plan","session_id":"demo"}'
```

Follow-up questions reuse context — ask `{"query":"possession?","session_id":"demo"}`
and it knows you still mean Golf Hills.

---

## Turning on real AI (Gemini)

1. Get a free key: https://aistudio.google.com/apikey
2. In `.env` set:
   ```
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_real_key_here
   EMBEDDING_PROVIDER=gemini    # optional: semantic RAG
   ```
3. `docker compose up --build`

Swapping to another provider later (Claude, OpenAI, Ollama…) is a **config change only** —
no business logic changes (Constitution §12).

---

## Project Layout

```
backend/
  app/
    main.py                 # FastAPI app + routers
    config.py               # env-driven settings
    database.py             # SQLAlchemy engine/session
    models.py               # SQL-first schema (source of truth)
    schemas.py              # API contracts
    init_db.py / seed.py    # bootstrap + demo data
    core/                   # security (JWT, RBAC), audit
    api/v1/                 # auth, query, projects, calculate, admin, analytics
    services/
      intent.py             # intent detection + entity linking
      orchestrator.py       # the hybrid pipeline
      database_service.py   # SQL lookups (+ citations)
      renderer.py           # card/table/timeline/checklist formatting
      session_memory.py     # Redis session context
      calculation/          # deterministic calculators
      rag/                  # ingest + retrieve (pgvector)
      llm/                  # provider abstraction (mock, gemini, …)
      embeddings/           # embedding abstraction (mock, gemini)
  tests/
docker-compose.yml
PRD.md                       # full product/architecture spec
```

---

## Tests

```bash
docker compose run --rm api pytest -q
```

---

## Key API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/v1/auth/login` | Authenticate |
| POST | `/v1/query` | **Main engine** — NL query → structured answer |
| GET | `/v1/projects` | List/search projects |
| GET | `/v1/projects/{id}/price` | Current price (SQL) |
| POST | `/v1/calculate/{type}` | EMI / ROI / total_cost / GST … |
| POST | `/v1/admin/projects` | Create project (admin, audited) |
| POST | `/v1/admin/documents` | Upload + index brochure (RAG) |
| GET | `/v1/admin/audit` | Audit trail |
| GET | `/health` | Liveness + active providers |

Full interactive docs at `/docs` when running.
